from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.fastapi_app.models import models

engine = create_engine("postgresql://whatif_user:whatif_pass@localhost:5433/whatif_db")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def verify():
    repo_id = 11
    errors = []
    
    # 1. Duplicate count
    duplicates = db.query(
        models.File.repository_id,
        models.File.path, 
        func.count(models.File.id).label('count')
    ).group_by(models.File.repository_id, models.File.path).having(func.count(models.File.id) > 1).all()
    
    print(f"1. Duplicate paths in all repos: {len(duplicates)}")
    if duplicates:
        errors.append(f"Found {len(duplicates)} duplicate paths!")

    # 3. Symbol.file_id -> File
    orphaned_syms = db.query(models.Symbol).outerjoin(models.File, models.Symbol.file_id == models.File.id).filter(models.File.id == None).count()
    print(f"3. Orphaned Symbols: {orphaned_syms}")
    if orphaned_syms > 0: errors.append(f"Found {orphaned_syms} orphaned Symbols")

    # 4. Dependency.source_file_id -> File
    orphaned_dep_src = db.query(models.Dependency).outerjoin(models.File, models.Dependency.source_file_id == models.File.id).filter(models.File.id == None).count()
    print(f"4. Orphaned Dependency (source): {orphaned_dep_src}")
    if orphaned_dep_src > 0: errors.append(f"Found {orphaned_dep_src} orphaned Dependency sources")

    # 5. Dependency.target_file_id -> File
    orphaned_dep_tgt = db.query(models.Dependency).filter(models.Dependency.target_file_id != None).outerjoin(models.File, models.Dependency.target_file_id == models.File.id).filter(models.File.id == None).count()
    print(f"5. Orphaned Dependency (target): {orphaned_dep_tgt}")
    if orphaned_dep_tgt > 0: errors.append(f"Found {orphaned_dep_tgt} orphaned Dependency targets")

    # 6. GraphEdge source_type='file' -> File
    orphaned_edge_src_file = db.query(models.GraphEdge).filter(models.GraphEdge.source_type == 'file').outerjoin(models.File, models.GraphEdge.source_id == models.File.id).filter(models.File.id == None).count()
    print(f"6. Orphaned GraphEdge (source=file): {orphaned_edge_src_file}")
    if orphaned_edge_src_file > 0: errors.append(f"Found {orphaned_edge_src_file} orphaned GraphEdges (source file)")

    # 7. GraphEdge target_type='file' -> File
    orphaned_edge_tgt_file = db.query(models.GraphEdge).filter(models.GraphEdge.target_type == 'file').outerjoin(models.File, models.GraphEdge.target_id == models.File.id).filter(models.File.id == None).count()
    print(f"7. Orphaned GraphEdge (target=file): {orphaned_edge_tgt_file}")
    if orphaned_edge_tgt_file > 0: errors.append(f"Found {orphaned_edge_tgt_file} orphaned GraphEdges (target file)")

    # 8. GraphEdge source_type='symbol' -> Symbol
    orphaned_edge_src_sym = db.query(models.GraphEdge).filter(models.GraphEdge.source_type == 'symbol').outerjoin(models.Symbol, models.GraphEdge.source_id == models.Symbol.id).filter(models.Symbol.id == None).count()
    print(f"8. Orphaned GraphEdge (source=symbol): {orphaned_edge_src_sym}")
    if orphaned_edge_src_sym > 0: errors.append(f"Found {orphaned_edge_src_sym} orphaned GraphEdges (source symbol)")

    # 9. GraphEdge target_type='symbol' -> Symbol
    orphaned_edge_tgt_sym = db.query(models.GraphEdge).filter(models.GraphEdge.target_type == 'symbol').outerjoin(models.Symbol, models.GraphEdge.target_id == models.Symbol.id).filter(models.Symbol.id == None).count()
    print(f"9. Orphaned GraphEdge (target=symbol): {orphaned_edge_tgt_sym}")
    if orphaned_edge_tgt_sym > 0: errors.append(f"Found {orphaned_edge_tgt_sym} orphaned GraphEdges (target symbol)")

    # 10 & 11. Specific files
    ocr_files = db.query(models.File).filter_by(repository_id=repo_id, path="backend/routes/ocr.js").all()
    server_files = db.query(models.File).filter_by(repository_id=repo_id, path="backend/server.js").all()
    
    print(f"10/11. backend/routes/ocr.js count: {len(ocr_files)}")
    if len(ocr_files) == 1:
        print(f"       -> Surviving ID: {ocr_files[0].id}")
    else:
        errors.append(f"Expected 1 ocr.js, found {len(ocr_files)}")

    print(f"10/11. backend/server.js count: {len(server_files)}")
    if len(server_files) == 1:
        print(f"       -> Surviving ID: {server_files[0].id}")
    else:
        errors.append(f"Expected 1 server.js, found {len(server_files)}")

    # 13. Verify no duplicate GraphEdge rows violate uq_graph_edge
    dup_edges = db.query(
        models.GraphEdge.repository_id,
        models.GraphEdge.source_type,
        models.GraphEdge.source_id,
        models.GraphEdge.target_type,
        models.GraphEdge.target_id,
        models.GraphEdge.edge_type,
        func.count(models.GraphEdge.id).label('count')
    ).group_by(
        models.GraphEdge.repository_id,
        models.GraphEdge.source_type,
        models.GraphEdge.source_id,
        models.GraphEdge.target_type,
        models.GraphEdge.target_id,
        models.GraphEdge.edge_type
    ).having(func.count(models.GraphEdge.id) > 1).all()
    
    print(f"13. Duplicate GraphEdge rows violating unique constraint: {len(dup_edges)}")
    if dup_edges:
        errors.append(f"Found {len(dup_edges)} duplicate GraphEdges!")

    if errors:
        print("\nVERIFICATION FAILED:")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)
    else:
        print("\nVERIFICATION PASSED! All invariants satisfied.")

if __name__ == "__main__":
    verify()
