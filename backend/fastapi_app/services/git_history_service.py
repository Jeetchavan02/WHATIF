import logging
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from git import Repo

from backend.fastapi_app.models import models

logger = logging.getLogger(__name__)

# ── Tunable limits ──────────────────────────────────────────────────────────
# Cap how many commits we process. Full AST diff of 2,000+ commits can take
# 5+ minutes; 400 covers virtually all "recent" history you'd care about.
MAX_COMMITS   = int(os.environ.get("WHATIF_MAX_COMMITS", "400"))
DB_BATCH_SIZE = int(os.environ.get("WHATIF_DB_BATCH", "50"))   # commits per db.commit()

SUPPORTED_LANGS = {".py", ".js", ".jsx", ".ts", ".tsx"}

# Dirs to skip when checking file paths
IGNORED_DIRS_SET = {".git", "node_modules", "__pycache__", ".venv",
                    "virtualenv", "build", "dist", "assets",
                    ".pytest_cache", ".gemini"}


def _is_ignored(path: str) -> bool:
    return any(part in IGNORED_DIRS_SET for part in path.split("/"))


def _count_lines(patch_bytes: bytes) -> tuple[int, int]:
    """Fast line-diff counter — avoids decoding the whole patch twice."""
    adds = dels = 0
    for line in patch_bytes.splitlines():
        if line and line[0] == ord(b"+") and not line.startswith(b"+++"):
            adds += 1
        elif line and line[0] == ord(b"-") and not line.startswith(b"---"):
            dels += 1
    return adds, dels


def extract_git_history(repo_path: str, repo_id: int, db: Session):
    try:
        git_repo = Repo(repo_path)
    except Exception as e:
        logger.error(f"Failed to open git repo at {repo_path}: {e}")
        return

    if not git_repo.heads or not git_repo.active_branch.is_valid():
        logger.warning(f"Repository {repo_path} is empty or has no valid branch.")
        return

    # ── Pre-fetch existing commit hashes to skip already-stored commits ────
    existing_hashes: set[str] = set(
        h for (h,) in db.query(models.Commit.commit_hash)
                        .filter_by(repository_id=repo_id)
                        .all()
    )

    commits_to_process = []
    for commit in git_repo.iter_commits("HEAD", max_count=MAX_COMMITS):
        if commit.hexsha not in existing_hashes:
            commits_to_process.append(commit)

    if not commits_to_process:
        logger.info(f"[git_history] No new commits to process for repo {repo_id}.")
        return

    logger.info(f"[git_history] Processing {len(commits_to_process)} new commits (cap={MAX_COMMITS}).")

    batch_symbol_changes: list[models.CommitSymbolChange] = []
    processed = 0

    for commit in commits_to_process:
        try:
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
                parent_hash=parent_hash,
            )
            db.add(new_commit)
            db.flush()  # need new_commit.id

            # ── Compute diffs ──────────────────────────────────────────────
            if commit.parents:
                parent = commit.parents[0]
                # create_patch only for supported code files — avoids loading
                # binary/asset blobs which is a major speed killer
                diffs = parent.diff(commit, create_patch=False)
            else:
                diffs = commit.diff(
                    git_repo.tree("4b825dc642cb6eb9a060e54bf8d69288fbee4904"),
                    create_patch=False,
                    R=True,
                )

            for diff in diffs:
                file_path = diff.b_path or diff.a_path
                if not file_path or _is_ignored(file_path):
                    continue

                change_type = "modified"
                old_path = new_path = None
                if diff.new_file:
                    change_type = "added"
                elif diff.deleted_file:
                    change_type = "deleted"
                elif diff.renamed_file:
                    change_type = "renamed"
                    old_path, new_path = diff.a_path, diff.b_path

                # ── Line-count stats ─────────────────────────────────────
                # Re-fetch patch only for small code files (skip for binaries
                # and assets which cause most of the slowness)
                additions = deletions = 0
                ext = os.path.splitext(file_path)[1].lower()
                if ext in SUPPORTED_LANGS:
                    try:
                        patch_bytes = diff.diff  # bytes; None if create_patch=False
                        if patch_bytes is None:
                            # fetch diff with patch for this file only
                            if commit.parents:
                                patch_diffs = commit.parents[0].diff(
                                    commit,
                                    paths=[file_path],
                                    create_patch=True,
                                )
                            else:
                                patch_diffs = []
                            for pd in patch_diffs:
                                if pd.diff:
                                    additions, deletions = _count_lines(pd.diff)
                        else:
                            additions, deletions = _count_lines(patch_bytes)
                    except Exception:
                        pass

                file_change = models.CommitFileChange(
                    commit_id=new_commit.id,
                    file_path=file_path,
                    change_type=change_type,
                    additions=additions,
                    deletions=deletions,
                    old_path=old_path,
                    new_path=new_path,
                )
                db.add(file_change)
                db.flush()  # need file_change.id

                # ── Symbol-level tracking: FILE-LEVEL ONLY ────────────────
                # We intentionally skip per-commit AST blob parsing here —
                # it was the single biggest bottleneck (2-4 min for large
                # repos). The current-state symbol table is built in
                # analyzer.py via the full file walk, which is sufficient
                # for blast-radius and graph queries.
                sym_change = models.CommitSymbolChange(
                    commit_file_change_id=file_change.id,
                    symbol_name="<file-level>",
                    symbol_type=ext.lstrip(".") if ext else "unknown",
                    change_type=change_type,
                )
                batch_symbol_changes.append(sym_change)

            processed += 1

            # ── Batch commit every DB_BATCH_SIZE commits ──────────────────
            if processed % DB_BATCH_SIZE == 0:
                if batch_symbol_changes:
                    db.bulk_save_objects(batch_symbol_changes)
                    batch_symbol_changes = []
                db.commit()
                logger.info(f"[git_history] Saved {processed}/{len(commits_to_process)} commits.")

        except Exception as e:
            logger.error(f"[git_history] Error processing commit {commit.hexsha}: {e}")
            db.rollback()
            batch_symbol_changes = []  # discard unsaved symbols for this batch

    # ── Final flush ────────────────────────────────────────────────────────
    try:
        if batch_symbol_changes:
            db.bulk_save_objects(batch_symbol_changes)
        db.commit()
        logger.info(f"[git_history] Done — {processed} commits saved for repo {repo_id}.")
    except Exception as e:
        logger.error(f"[git_history] Final flush failed: {e}")
        db.rollback()
