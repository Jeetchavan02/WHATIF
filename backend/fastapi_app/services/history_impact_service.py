from typing import List, Dict, Any
from collections import defaultdict
from sqlalchemy.orm import Session
from backend.fastapi_app.models import models

def get_historical_co_changes(
    repo_id: int,
    node_type: str,
    node_id: int,
    db: Session,
    limit: int = 100
) -> dict:
    if node_type != "file":
        # M7 focuses on FILE-level historical co-change initially.
        return {
            "source": {"node_type": node_type, "node_id": node_id},
            "source_change_count": 0,
            "co_changes": []
        }
        
    # 1. Fetch the source file
    source_file = db.query(models.File).filter_by(repository_id=repo_id, id=node_id).first()
    if not source_file:
        return {
            "source": {"node_type": node_type, "node_id": node_id},
            "source_change_count": 0,
            "co_changes": []
        }
        
    source_path = source_file.path
    
    # 2. Find all commits in this repository where this file changed
    # Join Commit to ensure repository isolation
    source_changes = db.query(models.CommitFileChange.commit_id).join(
        models.Commit, models.CommitFileChange.commit_id == models.Commit.id
    ).filter(
        models.Commit.repository_id == repo_id,
        models.CommitFileChange.file_path == source_path
    ).all()
    
    commit_ids = [row[0] for row in source_changes]
    source_change_count = len(commit_ids)
    
    if source_change_count == 0:
        return {
            "source": {"node_type": "file", "node_id": node_id},
            "source_change_count": 0,
            "co_changes": []
        }
        
    # 3. Fetch all file changes for those specific commits
    # This avoids N+1 queries by grabbing everything in one go
    all_co_changes = db.query(models.CommitFileChange.file_path).filter(
        models.CommitFileChange.commit_id.in_(commit_ids)
    ).all()
    
    # 4. Aggregate co-changes
    co_change_counts = defaultdict(int)
    for row in all_co_changes:
        fp = row[0]
        # Self-change exclusion
        if fp != source_path:
            co_change_counts[fp] += 1
            
    # 5. Resolve file paths to node IDs and build response
    # Fetch all relevant files in one query
    co_change_paths = list(co_change_counts.keys())
    if not co_change_paths:
        return {
            "source": {"node_type": "file", "node_id": node_id},
            "source_change_count": source_change_count,
            "co_changes": []
        }
        
    target_files = db.query(models.File).filter(
        models.File.repository_id == repo_id,
        models.File.path.in_(co_change_paths)
    ).all()
    
    path_to_id = {f.path: f.id for f in target_files}
    
    co_changes_list = []
    for path, count in co_change_counts.items():
        # Only include it if it exists in the File table 
        # (it might be a deleted file or ignored file, but we only want trackable files)
        if path in path_to_id:
            co_changes_list.append({
                "node_type": "file",
                "node_id": path_to_id[path],
                "co_change_count": count,
                "probability": count / source_change_count
            })
            
    # 6. Deterministic ordering: co_change_count descending, node_id ascending
    co_changes_list.sort(key=lambda x: (-x["co_change_count"], x["node_id"]))
    
    if limit > 0:
        co_changes_list = co_changes_list[:limit]
        
    return {
        "source": {"node_type": "file", "node_id": node_id},
        "source_change_count": source_change_count,
        "co_changes": co_changes_list
    }
