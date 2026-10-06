import logging
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from git import Repo, Commit as GitCommit
import os
from datetime import datetime, timezone

from backend.fastapi_app.models import models

logger = logging.getLogger(__name__)

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

    # Iterate through commits
    for commit in git_repo.iter_commits('HEAD'):
        try:
            # Idempotency check: see if commit already exists
            existing_commit = db.query(models.Commit).filter_by(
                repository_id=repo_id, commit_hash=commit.hexsha
            ).first()

            if existing_commit:
                continue # Skip already processed commits

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

            file_changes = []

            # Determine file changes
            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit, create_patch=True)
            else:
                # Initial commit: diff against empty tree
                diffs = commit.diff(git_repo.tree('4b825dc642cb6eb9a060e54bf8d69288fbee4904'), create_patch=True, R=True)

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
                    file_path=diff.b_path or diff.a_path,
                    change_type=change_type,
                    additions=additions,
                    deletions=deletions,
                    old_path=old_path,
                    new_path=new_path
                )
                file_changes.append(file_change)
            
            if file_changes:
                db.bulk_save_objects(file_changes)
            
            # Commit changes periodically per commit to save progress and memory
            db.commit()
            
        except Exception as e:
            logger.error(f"Error processing commit {commit.hexsha}: {e}")
            db.rollback() # rollback the current failed commit only
