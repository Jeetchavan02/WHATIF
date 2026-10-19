import os
from sqlalchemy.orm import Session
from backend.fastapi_app.models import models

# ── Bulk batch size for edge inserts ─────────────────────────────────────────
EDGE_BATCH = 500


def resolve_local_dependency(repo_id: int, source_path: str, target_name: str, db: Session):
    if target_name.startswith("node_modules") or "/node_modules/" in target_name:
        return None

    if target_name.startswith("./") or target_name.startswith("../"):
        source_dir = os.path.dirname(source_path)
        resolved_path = os.path.normpath(os.path.join(source_dir, target_name))
        if resolved_path.startswith("./"):
            resolved_path = resolved_path[2:]
        elif resolved_path == ".":
            resolved_path = ""
    else:
        if "/" in target_name:
            resolved_path = target_name
        else:
            resolved_path = target_name.replace(".", "/")

    extensions  = ["", ".js", ".jsx", ".ts", ".tsx", ".py"]
    index_files = ["/index.js", "/index.jsx", "/index.ts", "/index.tsx", "/__init__.py"]
    candidate_paths = [resolved_path + ext for ext in extensions] + \
                      [resolved_path + idx for idx in index_files]

    return db.query(models.File).filter(
        models.File.repository_id == repo_id,
        models.File.path.in_(candidate_paths)
    ).first()


def build_repository_graph(repo_id: int, db: Session) -> dict:
    # Wipe existing edges
    db.query(models.GraphEdge).filter(models.GraphEdge.repository_id == repo_id).delete()
    db.commit()

    seen_edges: set = set()
    pending_edges: list[dict] = []

    def flush_edges():
        if not pending_edges:
            return
        db.bulk_insert_mappings(models.GraphEdge, pending_edges)
        db.commit()
        pending_edges.clear()

    def add_edge(s_type, s_id, t_type, t_id, e_type):
        if not (s_id and t_id):
            return
        key = (s_type, s_id, t_type, t_id, e_type)
        if key in seen_edges:
            return
        seen_edges.add(key)
        pending_edges.append(dict(
            repository_id=repo_id,
            source_type=s_type,
            source_id=s_id,
            target_type=t_type,
            target_id=t_id,
            edge_type=e_type,
        ))
        if len(pending_edges) >= EDGE_BATCH:
            flush_edges()

    # ── Load all data up front (single queries) ───────────────────────────
    files   = db.query(models.File).filter(models.File.repository_id == repo_id).all()
    file_by_path = {f.path: f for f in files}
    file_by_id   = {f.id:   f for f in files}

    symbols = (db.query(models.Symbol)
                 .join(models.File)
                 .filter(models.File.repository_id == repo_id)
                 .all())
    symbol_by_file_name = {(s.file_id, s.name): s for s in symbols}

    # 1. Symbol → File (defined_in)
    for sym in symbols:
        add_edge("symbol", sym.id, "file", sym.file_id, "defined_in")

    # 2. File → File (depends_on)
    dependencies = (db.query(models.Dependency)
                      .filter(models.Dependency.repository_id == repo_id)
                      .all())
    for dep in dependencies:
        target_id = dep.target_file_id
        if not target_id and dep.target_name:
            source_file = file_by_id.get(dep.source_file_id)
            if source_file:
                resolved = resolve_local_dependency(repo_id, source_file.path, dep.target_name, db)
                if resolved:
                    target_id = resolved.id
                    dep.target_file_id = target_id
        if target_id:
            add_edge("file", dep.source_file_id, "file", target_id, "depends_on")

    # 3. Commit → File (changed) — skip symbol-level to avoid huge query on
    #    potentially millions of CommitSymbolChange rows
    commits = (db.query(models.Commit)
                 .filter(models.Commit.repository_id == repo_id)
                 .all())
    commit_ids = [c.id for c in commits]

    if commit_ids:
        # Load file changes in one query, group by commit
        file_changes = (db.query(models.CommitFileChange)
                          .filter(models.CommitFileChange.commit_id.in_(commit_ids))
                          .all())
        fc_by_commit: dict = {}
        for fc in file_changes:
            fc_by_commit.setdefault(fc.commit_id, []).append(fc)

        for commit in commits:
            for fc in fc_by_commit.get(commit.id, []):
                file_record = file_by_path.get(fc.file_path)
                if file_record:
                    add_edge("commit", commit.id, "file", file_record.id, "changed")

    flush_edges()

    return {
        "repository_id": repo_id,
        "nodes_created": 0,
        "edges_created": len(seen_edges),
    }
