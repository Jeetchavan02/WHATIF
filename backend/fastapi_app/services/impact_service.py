from collections import deque
from sqlalchemy.orm import Session
from backend.fastapi_app.models import models

def get_impact_propagation(
    repo_id: int, 
    node_type: str, 
    node_id: int, 
    db: Session, 
    max_depth: int = 10
) -> list[dict]:
    # 1. Load relevant edges into memory to avoid N+1 queries.
    # We only care about edges that represent dependencies.
    # In our model, we use "depends_on" (file->file). 
    # If a component relies on this node, we traverse backwards (target -> source).
    
    # We'll load all "depends_on" edges for this repo.
    # We could also include "defined_in" (symbol->file) if we want symbol changes to affect files,
    # but the prompt specifically says "focus on dependency relationships such as: depends_on"
    valid_edge_types = {"depends_on"}
    
    edges = db.query(models.GraphEdge).filter(
        models.GraphEdge.repository_id == repo_id,
        models.GraphEdge.edge_type.in_(valid_edge_types)
    ).all()
    
    # 2. Build reverse adjacency map: target -> list of sources (dependents)
    # Map structure: (target_type, target_id) -> list of (source_type, source_id, edge_type)
    adjacency_map = {}
    for edge in edges:
        tgt_key = (edge.target_type, edge.target_id)
        if tgt_key not in adjacency_map:
            adjacency_map[tgt_key] = []
        adjacency_map[tgt_key].append((edge.source_type, edge.source_id, edge.edge_type))
    
    # Sort adjacency lists for deterministic traversal
    for key in adjacency_map:
        adjacency_map[key].sort()

    # 3. Iterative BFS
    start_key = (node_type, node_id)
    visited = set()
    visited.add(start_key)
    
    # Queue stores: (current_node_type, current_node_id, current_depth)
    queue = deque([(node_type, node_id, 0)])
    
    affected = []
    
    while queue:
        curr_type, curr_id, curr_depth = queue.popleft()
        
        # If we reached max_depth, we don't explore further from this node
        if curr_depth >= max_depth:
            continue
            
        curr_key = (curr_type, curr_id)
        dependents = adjacency_map.get(curr_key, [])
        
        for dep_type, dep_id, edge_type in dependents:
            dep_key = (dep_type, dep_id)
            if dep_key not in visited:
                visited.add(dep_key)
                next_depth = curr_depth + 1
                affected.append({
                    "node_type": dep_type,
                    "node_id": dep_id,
                    "depth": next_depth,
                    "reason": edge_type
                })
                # We sort affected just to be extremely deterministic over the whole output?
                # Actually, BFS traversal order is already deterministic because adjacency_map is sorted,
                # but appending in BFS order is fine.
                queue.append((dep_type, dep_id, next_depth))

    return affected
