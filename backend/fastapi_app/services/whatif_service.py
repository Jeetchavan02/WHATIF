from sqlalchemy.orm import Session
from backend.fastapi_app.services.impact_service import get_impact_propagation
from backend.fastapi_app.services.history_impact_service import get_historical_co_changes
from backend.fastapi_app.models import models

def analyze_hypothetical_change(
    repo_id: int,
    node_type: str,
    node_id: int,
    db: Session,
    max_depth: int = 10,
    historical_limit: int = 100
) -> dict:
    
    # 1. Structural Impact (M6)
    structural_affected = get_impact_propagation(repo_id, node_type, node_id, db, max_depth=max_depth)
    
    # 2. Historical Impact (M7)
    historical_data = get_historical_co_changes(repo_id, node_type, node_id, db, limit=historical_limit)
    historical_affected = historical_data.get("co_changes", [])
    source_change_count = historical_data.get("source_change_count", 0)
    
    # 3. Merge evidence
    merged = {}
    
    # Process structural results
    for s_node in structural_affected:
        key = (s_node["node_type"], s_node["node_id"])
        merged[key] = {
            "node_type": s_node["node_type"],
            "node_id": s_node["node_id"],
            "structural": {
                "depth": s_node["depth"],
                "reason": s_node["reason"]
            },
            "historical": None
        }
        
    # Process historical results
    for h_node in historical_affected:
        key = (h_node["node_type"], h_node["node_id"])
        if key not in merged:
            merged[key] = {
                "node_type": h_node["node_type"],
                "node_id": h_node["node_id"],
                "structural": None,
                "historical": {
                    "co_change_count": h_node["co_change_count"],
                    "co_change_rate": h_node["probability"]
                }
            }
        else:
            merged[key]["historical"] = {
                "co_change_count": h_node["co_change_count"],
                "co_change_rate": h_node["probability"]
            }
            
    # 4. Classify and format results
    affected_components = []
    structural_total = len(structural_affected)
    structural_direct = sum(1 for s in structural_affected if s["depth"] == 1)
    structural_transitive = structural_total - structural_direct
    
    for key, data in merged.items():
        if data["structural"] and data["historical"]:
            classification = "BOTH"
        elif data["structural"]:
            classification = "STRUCTURAL_ONLY"
        else:
            classification = "HISTORICAL_ONLY"
            
        data["classification"] = classification
        
        # We also want to surface the path if it is a file
        # To avoid N+1, we can fetch all node_ids later, but since this is file-level right now,
        # we can just fetch the file path directly for context.
        # Actually, let's fetch paths for all file nodes to be efficient.
        affected_components.append(data)
        
    # Fetch paths
    file_ids = [c["node_id"] for c in affected_components if c["node_type"] == "file"]
    if file_ids:
        files = db.query(models.File.id, models.File.path).filter(models.File.id.in_(file_ids)).all()
        id_to_path = {f.id: f.path for f in files}
        for comp in affected_components:
            if comp["node_type"] == "file":
                comp["path"] = id_to_path.get(comp["node_id"])
                
    # 5. Deterministic sorting
    def sort_key(x):
        # 1. Classification Priority
        cls_priority = {"BOTH": 1, "STRUCTURAL_ONLY": 2, "HISTORICAL_ONLY": 3}
        prio = cls_priority[x["classification"]]
        
        # 2. Structural depth ascending (None -> inf)
        depth = x["structural"]["depth"] if x["structural"] else float('inf')
        
        # 3. Historical co_change_count descending (None -> 0)
        co_change_count = x["historical"]["co_change_count"] if x["historical"] else 0
        
        # 4. Node ID ascending
        node_id = x["node_id"]
        
        return (prio, depth, -co_change_count, node_id)
        
    affected_components.sort(key=sort_key)
    
    return {
        "source": {
            "node_type": node_type,
            "node_id": node_id
        },
        "structural_impact": {
            "total_affected": structural_total,
            "direct_affected": structural_direct,
            "transitive_affected": structural_transitive
        },
        "historical_impact": {
            "source_change_count": source_change_count,
            "distinct_co_changed_files": len(historical_affected)
        },
        "affected_components": affected_components
    }
