import logging
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from git import Repo, Commit as GitCommit
import os
from datetime import datetime, timezone

from backend.fastapi_app.models import models

logger = logging.getLogger(__name__)

import ast

def get_blob_content(blob):
    if not blob: return ""
    try:
        return blob.data_stream.read().decode('utf-8', errors='ignore')
    except Exception:
        return ""

def extract_git_history(repo_path: str, repo_id: int, db: Session):
    try:
        git_repo = Repo(repo_path)
    except Exception as e:
        logger.error(f"Failed to open git repo at {repo_path}: {e}")
        return

    # Check for empty repo
    if not git_repo.heads or not git_repo.active_branch.is_valid():
        logger.warning(f"Repository {repo_path} is empty or has no valid branch.")
        return

    # Pre-fetch existing commit hashes to avoid N SQL queries
    existing_hashes = set(
        h[0] for h in db.query(models.Commit.commit_hash).filter_by(repository_id=repo_id).all()
    )

    # Iterate through commits
    for commit in git_repo.iter_commits('HEAD'):
        try:
            if commit.hexsha in existing_hashes:
                continue # Skip already processed commits
            existing_hashes.add(commit.hexsha)

            # Prepare Commit DB model
            parent_hash = commit.parents[0].hexsha if commit.parents else None
            committed_dt = commit.committed_datetime
            if committed_dt.tzinfo is None:
                committed_dt = committed_dt.replace(tzinfo=timezone.utc)

            new_commit = models.Commit(
                repository_id=repo_id,
                commit_hash=commit.hexsha,
                author_name=commit.author.name,
                author_email=commit.author.email,
                message=commit.message,
                committed_at=committed_dt,
                parent_hash=parent_hash
            )
            db.add(new_commit)
            db.flush() # flush to get the new_commit.id

            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit, create_patch=True)
            else:
                # Initial commit: diff against empty tree
                diffs = commit.diff(git_repo.tree('4b825dc642cb6eb9a060e54bf8d69288fbee4904'), create_patch=True, R=True)

            symbol_changes = []

            for diff in diffs:
                change_type = "modified"
                old_path = None
                new_path = None

                if diff.new_file:
                    change_type = "added"
                elif diff.deleted_file:
                    change_type = "deleted"
                elif diff.renamed_file:
                    change_type = "renamed"
                    old_path = diff.a_path
                    new_path = diff.b_path

                file_path = diff.b_path or diff.a_path
                if not file_path: continue
                
                from backend.fastapi_app.core.analyzer import IGNORED_DIRS
                if any(ignored in file_path.split('/') for ignored in IGNORED_DIRS):
                    continue

                # Calculate additions and deletions from the patch
                additions = 0
                deletions = 0
                if diff.diff:
                    patch = diff.diff.decode('utf-8', errors='ignore')
                    for line in patch.splitlines():
                        if line.startswith('+') and not line.startswith('+++'):
                            additions += 1
                        elif line.startswith('-') and not line.startswith('---'):
                            deletions += 1

                file_change = models.CommitFileChange(
                    commit_id=new_commit.id,
                    file_path=file_path,
                    change_type=change_type,
                    additions=additions,
                    deletions=deletions,
                    old_path=old_path,
                    new_path=new_path
                )
                db.add(file_change)
                db.flush()

                lang = "unknown"
                if file_path:
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext == ".py": lang = "python"
                    elif ext == ".js": lang = "javascript"
                    elif ext == ".jsx": lang = "jsx"
                    elif ext == ".ts": lang = "typescript"
                    elif ext == ".tsx": lang = "tsx"

                if lang in ("python", "javascript", "typescript", "tsx", "jsx"):
                    from backend.fastapi_app.services.parsers import extract_symbols
                    old_code = get_blob_content(diff.a_blob)
                    new_code = get_blob_content(diff.b_blob)

                    old_symbols = extract_symbols(old_code, lang)
                    new_symbols = extract_symbols(new_code, lang)

                    all_symbol_names = set(old_symbols.keys()).union(set(new_symbols.keys()))

                    for sym_name in all_symbol_names:
                        old_sym = old_symbols.get(sym_name)
                        new_sym = new_symbols.get(sym_name)

                        sym_change_type = "unchanged"
                        if not old_sym and new_sym:
                            sym_change_type = "added"
                        elif old_sym and not new_sym:
                            sym_change_type = "deleted"
                        elif old_sym and new_sym:
                            if old_sym["body_dump"] != new_sym["body_dump"]:
                                sym_change_type = "modified"
                        
                        sym_data = new_sym or old_sym

                        symbol_change = models.CommitSymbolChange(
                            commit_file_change_id=file_change.id,
                            symbol_name=sym_name,
                            symbol_type=sym_data["type"],
                            change_type=sym_change_type,
                            old_start_line=old_sym["start_line"] if old_sym else None,
                            old_end_line=old_sym["end_line"] if old_sym else None,
                            new_start_line=new_sym["start_line"] if new_sym else None,
                            new_end_line=new_sym["end_line"] if new_sym else None
                        )
                        symbol_changes.append(symbol_change)
                else:
                    # Unsupported file
                    symbol_change = models.CommitSymbolChange(
                        commit_file_change_id=file_change.id,
                        symbol_name="<file-level-only>",
                        symbol_type="unsupported",
                        change_type="unsupported"
                    )
                    symbol_changes.append(symbol_change)

            if symbol_changes:
                db.bulk_save_objects(symbol_changes)
            
            # Commit changes periodically per commit to save progress and memory
            db.commit()
            
        except Exception as e:
            logger.error(f"Error processing commit {commit.hexsha}: {e}")
            db.rollback() # rollback the current failed commit only
