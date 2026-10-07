import argparse
import sys
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.fastapi_app.models import models

def get_engine():
    return create_engine("postgresql://whatif_user:whatif_pass@localhost:5433/whatif_db")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    stats = {
        "duplicate_paths_found": 0,
        "files_to_delete": 0,
        "symbols_remapped": 0,
        "symbols_deleted": 0,
        "commit_symbol_changes_remapped": 0,
        "deps_remapped": 0,
        "deps_deleted": 0,
        "edges_remapped": 0,
        "edges_deleted": 0
    }

    try:
        duplicates_all = db.query(
            models.File.repository_id,
            models.File.path, 
            func.count(models.File.id).label('count')
        ).group_by(models.File.repository_id, models.File.path).having(func.count(models.File.id) > 1).all()

        stats["duplicate_paths_found"] = len(duplicates_all)

        for repo_id, path, count in duplicates_all:
            files = db.query(models.File).filter_by(repository_id=repo_id, path=path).order_by(models.File.id).all()
            if not files:
                continue

            canonical = files[0]
            duplicates = files[1:]

            for dup in duplicates:
                stats["files_to_delete"] += 1
                
                # 1. Symbols
                dup_symbols = db.query(models.Symbol).filter_by(file_id=dup.id).all()
                for d_sym in dup_symbols:
                    c_sym = db.query(models.Symbol).filter_by(
                        file_id=canonical.id,
                        name=d_sym.name,
                        symbol_type=d_sym.symbol_type,
                        start_line=d_sym.start_line
                    ).first()

                    if c_sym:
                        # Remap CommitSymbolChange
                        cscs = db.query(models.CommitSymbolChange).filter_by(symbol_id=d_sym.id).all()
                        for csc in cscs:
                            if args.execute:
                                csc.symbol_id = c_sym.id
                            stats["commit_symbol_changes_remapped"] += 1

                        # Remap GraphEdge (source_type='symbol')
                        sym_edges_src = db.query(models.GraphEdge).filter_by(source_type='symbol', source_id=d_sym.id).all()
                        for s_edge in sym_edges_src:
                            c_edge = db.query(models.GraphEdge).filter_by(
                                repository_id=repo_id,
                                source_type='symbol', source_id=c_sym.id,
                                target_type=s_edge.target_type, target_id=s_edge.target_id,
                                edge_type=s_edge.edge_type
                            ).first()
                            if c_edge:
                                if args.execute: db.delete(s_edge)
                                stats["edges_deleted"] += 1
                            else:
                                if args.execute: s_edge.source_id = c_sym.id
                                stats["edges_remapped"] += 1

                        # Remap GraphEdge (target_type='symbol')
                        sym_edges_tgt = db.query(models.GraphEdge).filter_by(target_type='symbol', target_id=d_sym.id).all()
                        for s_edge in sym_edges_tgt:
                            c_edge = db.query(models.GraphEdge).filter_by(
                                repository_id=repo_id,
                                source_type=s_edge.source_type, source_id=s_edge.source_id,
                                target_type='symbol', target_id=c_sym.id,
                                edge_type=s_edge.edge_type
                            ).first()
                            if c_edge:
                                if args.execute: db.delete(s_edge)
                                stats["edges_deleted"] += 1
                            else:
                                if args.execute: s_edge.target_id = c_sym.id
                                stats["edges_remapped"] += 1
                        
                        if args.execute:
                            db.delete(d_sym)
                        stats["symbols_deleted"] += 1
                    else:
                        if args.execute:
                            d_sym.file_id = canonical.id
                        stats["symbols_remapped"] += 1

                # 2. Dependencies (as source)
                dup_deps_src = db.query(models.Dependency).filter_by(source_file_id=dup.id).all()
                for d_dep in dup_deps_src:
                    c_dep = db.query(models.Dependency).filter_by(
                        source_file_id=canonical.id,
                        target_file_id=d_dep.target_file_id,
                        dependency_type=d_dep.dependency_type,
                        target_name=d_dep.target_name
                    ).first()

                    if c_dep:
                        if args.execute:
                            db.delete(d_dep)
                        stats["deps_deleted"] += 1
                    else:
                        if args.execute:
                            d_dep.source_file_id = canonical.id
                        stats["deps_remapped"] += 1

                # 3. Dependencies (as target)
                dup_deps_tgt = db.query(models.Dependency).filter_by(target_file_id=dup.id).all()
                for d_dep in dup_deps_tgt:
                    c_dep = db.query(models.Dependency).filter_by(
                        source_file_id=d_dep.source_file_id,
                        target_file_id=canonical.id,
                        dependency_type=d_dep.dependency_type,
                        target_name=d_dep.target_name
                    ).first()

                    if c_dep:
                        if args.execute:
                            db.delete(d_dep)
                        stats["deps_deleted"] += 1
                    else:
                        if args.execute:
                            d_dep.target_file_id = canonical.id
                        stats["deps_remapped"] += 1

                # 4. GraphEdge (as source)
                dup_edges_src = db.query(models.GraphEdge).filter_by(source_type='file', source_id=dup.id).all()
                for d_edge in dup_edges_src:
                    c_edge = db.query(models.GraphEdge).filter_by(
                        repository_id=repo_id,
                        source_type='file',
                        source_id=canonical.id,
                        target_type=d_edge.target_type,
                        target_id=d_edge.target_id,
                        edge_type=d_edge.edge_type
                    ).first()

                    if c_edge:
                        if args.execute:
                            db.delete(d_edge)
                        stats["edges_deleted"] += 1
                    else:
                        if args.execute:
                            d_edge.source_id = canonical.id
                        stats["edges_remapped"] += 1

                # 5. GraphEdge (as target)
                dup_edges_tgt = db.query(models.GraphEdge).filter_by(target_type='file', target_id=dup.id).all()
                for d_edge in dup_edges_tgt:
                    c_edge = db.query(models.GraphEdge).filter_by(
                        repository_id=repo_id,
                        source_type=d_edge.source_type,
                        source_id=d_edge.source_id,
                        target_type='file',
                        target_id=canonical.id,
                        edge_type=d_edge.edge_type
                    ).first()

                    if c_edge:
                        if args.execute:
                            db.delete(d_edge)
                        stats["edges_deleted"] += 1
                    else:
                        if args.execute:
                            d_edge.target_id = canonical.id
                        stats["edges_remapped"] += 1

                # 6. Finally, delete the duplicate file itself
                if args.execute:
                    db.delete(dup)

        if args.execute:
            db.commit()
            print("EXECUTION COMPLETED. Transaction committed.")
        else:
            db.rollback()
            print("DRY RUN COMPLETED. No changes made.")

    except Exception as e:
        db.rollback()
        print(f"Error occurred: {e}")
        print("Transaction rolled back.")
        sys.exit(1)
    finally:
        db.close()

    print("\n--- Summary ---")
    print(f"Duplicate paths found: {stats['duplicate_paths_found']}")
    print(f"Files to delete: {stats['files_to_delete']}")
    print(f"Symbols remapped: {stats['symbols_remapped']}")
    print(f"Symbols deleted (merged): {stats['symbols_deleted']}")
    print(f"CommitSymbolChanges remapped: {stats['commit_symbol_changes_remapped']}")
    print(f"Dependencies remapped: {stats['deps_remapped']}")
    print(f"Dependencies deleted (merged): {stats['deps_deleted']}")
    print(f"GraphEdges remapped: {stats['edges_remapped']}")
    print(f"GraphEdges deleted (merged): {stats['edges_deleted']}")


if __name__ == "__main__":
    main()
