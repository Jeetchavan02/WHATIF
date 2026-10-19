import os
from sqlalchemy.orm import Session
from sqlalchemy import and_
from backend.fastapi_app.models import models

def resolve_local_dependency(repo_id: int, source_path: str, target_name: str, db: Session) -> models.File | None:
    if target_name.startswith("node_modules") or "/node_modules/" in target_name:
        return None

    # Handle relative imports
    if target_name.startswith("./") or target_name.startswith("../"):
        source_dir = os.path.dirname(source_path)
        # Normalize path
        resolved_path = os.path.normpath(os.path.join(source_dir, target_name))
        if resolved_path.startswith("./"):
            resolved_path = resolved_path[2:]
        elif resolved_path == ".":
            resolved_path = ""
    else:
        # Python imports could be a.b.c or absolute paths if it's JS (not starting with .)
        # For simplicity, if it doesn't start with . we can treat it as a direct path or python module path
        if "/" in target_name:
            resolved_path = target_name
        else:
            resolved_path = target_name.replace(".", "/")

    # Check the exact path, extensions, and index files
    extensions = ["", ".js", ".jsx", ".ts", ".tsx", ".py"]
    index_files = ["/index.js", "/index.jsx", "/index.ts", "/index.tsx", "/__init__.py"]

    candidate_paths = []
    for ext in extensions:
        candidate_paths.append(resolved_path + ext)
    for idx in index_files:
        candidate_paths.append(resolved_path + idx)

    # Search the DB for any of these paths
    file_record = db.query(models.File).filter(
        models.File.repository_id == repo_id,
        models.File.path.in_(candidate_paths)
    ).first()

    return file_record

def build_repository_graph(repo_id: int, db: Session) -> dict:
    # Rebuild: wipe existing edges for this repository first
    db.query(models.GraphEdge).filter(models.GraphEdge.repository_id == repo_id).delete()
    db.commit()

    edges_created = 0
    nodes_created = 0 # In our model, nodes are implicit (existing rows). We just count edges.
    seen_edges = set()

    def add_edge(s_type, s_id, t_type, t_id, e_type):
        nonlocal edges_created
        if not (s_id and t_id):
            return
        
        edge_key = (s_type, s_id, t_type, t_id, e_type)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            new_edge = models.GraphEdge(
                repository_id=repo_id,
                source_type=s_type,
                source_id=s_id,
                target_type=t_type,
                target_id=t_id,
                edge_type=e_type
            )
            db.add(new_edge)
            edges_created += 1

    # Preload files for this repo into a path -> File mapping to avoid N+1 queries
    files = db.query(models.File).filter(models.File.repository_id == repo_id).all()
    file_by_path = {f.path: f for f in files}
    file_by_id = {f.id: f for f in files}

    # Preload symbols for this repo into a (file_id, name) -> Symbol mapping
    symbols = db.query(models.Symbol).join(models.File).filter(models.File.repository_id == repo_id).all()
    symbol_by_file_and_name = {(s.file_id, s.name): s for s in symbols}

    # 1. Symbol -> File (defined_in)
    for sym in symbols:
        add_edge("symbol", sym.id, "file", sym.file_id, "defined_in")

    # 2. File -> File (depends_on)
    dependencies = db.query(models.Dependency).filter(models.Dependency.repository_id == repo_id).all()
    for dep in dependencies:
        target_id = dep.target_file_id
        if not target_id and dep.target_name:
            source_file = file_by_id.get(dep.source_file_id)
            if source_file:
                resolved_file = resolve_local_dependency(repo_id, source_file.path, dep.target_name, db)
                if resolved_file:
                    target_id = resolved_file.id
                    dep.target_file_id = target_id
                    
        if target_id:
            add_edge("file", dep.source_file_id, "file", target_id, "depends_on")

    # 3. Commit -> File (changed) & Commit -> Symbol (changed)
    commits = db.query(models.Commit).filter(models.Commit.repository_id == repo_id).all()
    commit_ids = [c.id for c in commits]
    
    if commit_ids:
        file_changes = db.query(models.CommitFileChange).filter(models.CommitFileChange.commit_id.in_(commit_ids)).all()
        fc_ids = [fc.id for fc in file_changes]
        
        # Group file changes by commit
        fc_by_commit = {}
        for fc in file_changes:
            fc_by_commit.setdefault(fc.commit_id, []).append(fc)
            
        symbol_changes = []
        if fc_ids:
            symbol_changes = db.query(models.CommitSymbolChange).filter(models.CommitSymbolChange.commit_file_change_id.in_(fc_ids)).all()
        sc_by_fc = {}
        for sc in symbol_changes:
            sc_by_fc.setdefault(sc.commit_file_change_id, []).append(sc)

        for commit in commits:
            for fc in fc_by_commit.get(commit.id, []):
                file_record = file_by_path.get(fc.file_path)
                if file_record:
                    add_edge("commit", commit.id, "file", file_record.id, "changed")

                for sc in sc_by_fc.get(fc.id, []):
                    if sc.symbol_id:
                        add_edge("commit", commit.id, "symbol", sc.symbol_id, "changed")
                    elif file_record:
                        sym_record = symbol_by_file_and_name.get((file_record.id, sc.symbol_name))
                        if sym_record:
                            sc.symbol_id = sym_record.id
                            add_edge("commit", commit.id, "symbol", sym_record.id, "changed")

    db.commit()

    return {
        "repository_id": repo_id,
        "nodes_created": 0,
        "edges_created": edges_created
    }
