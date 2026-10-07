from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from backend.fastapi_app.schemas import schemas
from backend.fastapi_app.models import models
from backend.fastapi_app.core.database import get_db
from backend.fastapi_app.core.analyzer import run_analysis, get_language

router = APIRouter()

@router.post("/repositories", response_model=schemas.RepositoryResponse)
def create_repository(repo: schemas.RepositoryCreate, db: Session = Depends(get_db)):
    existing_repo = db.query(models.Repository).filter(models.Repository.url == repo.url).first()
    if existing_repo:
        return existing_repo

    db_repo = models.Repository(url=repo.url, name=repo.name)
    db.add(db_repo)
    db.commit()
    db.refresh(db_repo)
    return db_repo

@router.get("/repositories", response_model=List[schemas.RepositoryResponse])
def list_repositories(db: Session = Depends(get_db)):
    return db.query(models.Repository).all()

@router.post("/repositories/{repository_id}/analyze")
def start_analysis(repository_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo = db.query(models.Repository).filter(models.Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    run = models.AnalysisRun(repository_id=repository_id, status="pending")
    db.add(run)
    db.commit()

    background_tasks.add_task(run_analysis, repository_id, db)
    return {"message": "Analysis started", "analysis_id": run.id}

@router.get("/repositories/{repository_id}", response_model=schemas.RepositoryResponse)
def get_repository(repository_id: int, db: Session = Depends(get_db)):
    repo = db.query(models.Repository).filter(models.Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo

@router.get("/repositories/{repository_id}/files", response_model=List[schemas.FileResponse])
def get_repository_files(repository_id: int, db: Session = Depends(get_db)):
    return db.query(models.File).filter(models.File.repository_id == repository_id).all()

@router.get("/repositories/{repository_id}/dependencies", response_model=List[schemas.DependencyResponse])
def get_repository_dependencies(repository_id: int, db: Session = Depends(get_db)):
    return db.query(models.Dependency).filter(models.Dependency.repository_id == repository_id).all()

@router.get("/analysis/{analysis_id}", response_model=schemas.AnalysisRunResponse)
def get_analysis_status(analysis_id: int, db: Session = Depends(get_db)):
    run = db.query(models.AnalysisRun).filter(models.AnalysisRun.id == analysis_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return run

from sqlalchemy import func, case
from typing import Optional
from datetime import datetime

@router.get("/repositories/{repository_id}/commits", response_model=List[schemas.CommitResponse])
def get_repository_commits(
    repository_id: int,
    page: int = 1,
    page_size: int = 20,
    author: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Commit).filter(models.Commit.repository_id == repository_id)
    if author:
        query = query.filter(models.Commit.author_name.ilike(f"%{author}%"))
    if date_from:
        query = query.filter(models.Commit.committed_at >= date_from)
    if date_to:
        query = query.filter(models.Commit.committed_at <= date_to)

    # Order by committed_at descending
    query = query.order_by(models.Commit.committed_at.desc())

    offset = (page - 1) * page_size
    return query.offset(offset).limit(page_size).all()

@router.get("/commits/{commit_id}", response_model=schemas.CommitResponse)
def get_commit_by_id(commit_id: int, db: Session = Depends(get_db)):
    commit = db.query(models.Commit).filter(models.Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    return commit

@router.get("/repositories/{repository_id}/commits/{commit_hash}", response_model=schemas.CommitResponse)
def get_commit_by_hash(repository_id: int, commit_hash: str, db: Session = Depends(get_db)):
    commit = db.query(models.Commit).filter(
        models.Commit.repository_id == repository_id,
        models.Commit.commit_hash == commit_hash
    ).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    return commit

@router.get("/repositories/{repository_id}/history/stats", response_model=schemas.HistoryStatsResponse)
def get_history_stats(repository_id: int, db: Session = Depends(get_db)):
    total_commits = db.query(models.Commit).filter(models.Commit.repository_id == repository_id).count()

    stats = db.query(
        func.sum(models.CommitFileChange.additions).label('total_additions'),
        func.sum(models.CommitFileChange.deletions).label('total_deletions'),
        func.sum(case((models.CommitFileChange.change_type == 'modified', 1), else_=0)).label('total_modified'),
        func.sum(case((models.CommitFileChange.change_type == 'added', 1), else_=0)).label('total_added'),
        func.sum(case((models.CommitFileChange.change_type == 'deleted', 1), else_=0)).label('total_deleted'),
        func.sum(case((models.CommitFileChange.change_type == 'renamed', 1), else_=0)).label('total_renamed')
    ).join(models.Commit).filter(models.Commit.repository_id == repository_id).first()

    # Most frequently changed files
    freq_files = db.query(
        models.CommitFileChange.file_path,
        func.count(models.CommitFileChange.id).label('change_count')
    ).join(models.Commit).filter(models.Commit.repository_id == repository_id)\
    .group_by(models.CommitFileChange.file_path)\
    .order_by(func.count(models.CommitFileChange.id).desc())\
    .limit(10).all()

    freq_files_list = [{"file_path": f.file_path, "change_count": f.change_count} for f in freq_files]

    return {
        "total_commits": total_commits,
        "total_additions": stats.total_additions or 0,
        "total_deletions": stats.total_deletions or 0,
        "total_modified_files": stats.total_modified or 0,
        "total_added_files": stats.total_added or 0,
        "total_deleted_files": stats.total_deleted or 0,
        "total_renamed_files": stats.total_renamed or 0,
        "most_frequently_changed_files": freq_files_list
    }

@router.get("/commits/{commit_id}/changes", response_model=schemas.CommitChangesResponse)
def get_commit_changes(commit_id: int, db: Session = Depends(get_db)):
    commit = db.query(models.Commit).filter(models.Commit.id == commit_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    files_out = []
    for fc in commit.file_changes:
        symbols_out = []
        for sc in fc.symbol_changes:
            symbols_out.append({
                "id": sc.id,
                "symbol_name": sc.symbol_name,
                "symbol_type": sc.symbol_type,
                "change_type": sc.change_type,
                "old_start_line": sc.old_start_line,
                "old_end_line": sc.old_end_line,
                "new_start_line": sc.new_start_line,
                "new_end_line": sc.new_end_line
            })
        lang = get_language(fc.file_path)
        files_out.append({
            "path": fc.file_path,
            "language": lang,
            "change_type": fc.change_type,
            "symbols": symbols_out
        })

    return {
        "commit": commit.commit_hash,
        "files": files_out
    }

@router.get("/repositories/{repository_id}/symbols/{symbol_id}/history")
def get_symbol_history(repository_id: int, symbol_id: int, db: Session = Depends(get_db)):
    # Assuming symbol_id refers to a record in `commit_symbol_changes` or `symbols`
    # The spec asks to show commits in which the symbol was added, modified, or deleted.
    # We find the symbol_name for the current symbol:
    symbol = db.query(models.Symbol).filter(models.Symbol.id == symbol_id).first()
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")

    # Find all symbol changes matching this symbol_name and file in this repo
    # This requires joining CommitFileChange -> Commit to filter by repo
    changes = db.query(models.CommitSymbolChange)\
        .join(models.CommitFileChange)\
        .join(models.Commit)\
        .filter(
            models.Commit.repository_id == repository_id,
            models.CommitSymbolChange.symbol_name == symbol.name,
            models.CommitFileChange.file_path == symbol.file.path
        )\
        .order_by(models.Commit.committed_at.desc()).all()

    out = []
    for sc in changes:
        out.append({
            "commit": sc.file_change.commit.commit_hash,
            "change_type": sc.change_type,
            "date": sc.file_change.commit.committed_at
        })
    return out

@router.get("/repositories/{repository_id}/change-map", response_model=List[schemas.ChangeMapCommitResponse])
def get_change_map(repository_id: int, db: Session = Depends(get_db)):
    commits = db.query(models.Commit).filter(models.Commit.repository_id == repository_id).order_by(models.Commit.committed_at.desc()).all()

    # Pre-fetch file dependencies for the repository
    all_deps = db.query(models.Dependency).filter(models.Dependency.repository_id == repository_id).all()
    dep_map = {} # path -> list of target_names
    for dep in all_deps:
        source_path = dep.source_file.path if dep.source_file else None
        if source_path:
            target = dep.target_file.path if dep.target_file else dep.target_name
            if source_path not in dep_map:
                dep_map[source_path] = []
            if target and target not in dep_map[source_path]:
                dep_map[source_path].append(target)

    result = []
    for commit in commits:
        files_out = []
        for fc in commit.file_changes:
            file_deps = dep_map.get(fc.file_path, [])
            symbols_out = []
            for sc in fc.symbol_changes:
                symbols_out.append({
                    "name": sc.symbol_name,
                    "change_type": sc.change_type,
                    "dependencies": file_deps
                })

            # If no symbols are tracked for this file (e.g., non-python), just return the file
            if not symbols_out:
                symbols_out.append({
                    "name": "<file-level-only>",
                    "change_type": fc.change_type,
                    "dependencies": file_deps
                })

            files_out.append({
                "path": fc.file_path,
                "symbols": symbols_out
            })
        if files_out:
            result.append({
                "commit": commit.commit_hash,
                "files": files_out
            })

    return result

from backend.fastapi_app.services.graph_service import build_repository_graph

@router.post("/repositories/{repository_id}/graph/build", response_model=schemas.GraphBuildResponse)
def build_graph(repository_id: int, db: Session = Depends(get_db)):
    repo = db.query(models.Repository).filter(models.Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    result = build_repository_graph(repository_id, db)
    return result

@router.get("/repositories/{repository_id}/graph")
def get_graph(repository_id: int, db: Session = Depends(get_db)):
    edges = db.query(models.GraphEdge).filter(models.GraphEdge.repository_id == repository_id).all()

    # Practical deterministic response
    nodes_set = set()
    edges_list = []

    for e in edges:
        nodes_set.add((e.source_type, e.source_id))
        nodes_set.add((e.target_type, e.target_id))
        edges_list.append({
            "id": e.id,
            "source": f"{e.source_type}:{e.source_id}",
            "target": f"{e.target_type}:{e.target_id}",
            "edge_type": e.edge_type
        })

    nodes_list = [{"id": f"{ntype}:{nid}", "type": ntype, "ref_id": nid} for ntype, nid in nodes_set]

    return {
        "nodes": nodes_list,
        "edges": edges_list
    }

def get_node_data(node_type: str, node_id: int, db: Session):
    if node_type == "repository":
        node = db.query(models.Repository).filter(models.Repository.id == node_id).first()
    elif node_type == "file":
        node = db.query(models.File).filter(models.File.id == node_id).first()
    elif node_type == "symbol":
        node = db.query(models.Symbol).filter(models.Symbol.id == node_id).first()
    elif node_type == "commit":
        node = db.query(models.Commit).filter(models.Commit.id == node_id).first()
    else:
        raise HTTPException(status_code=400, detail="Unsupported node_type")

    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Serialize practically by dropping non-JSON attributes
    return {k: v for k, v in node.__dict__.items() if not k.startswith("_")}

@router.get("/repositories/{repository_id}/graph/{node_type}/{node_id}", response_model=schemas.GraphNodeDetailResponse)
def get_graph_node(repository_id: int, node_type: str, node_id: int, db: Session = Depends(get_db)):
    if node_type not in ["repository", "file", "symbol", "commit"]:
        raise HTTPException(status_code=400, detail="Unsupported node_type")

    node_data = get_node_data(node_type, node_id, db)

    outgoing = db.query(models.GraphEdge).filter(
        models.GraphEdge.repository_id == repository_id,
        models.GraphEdge.source_type == node_type,
        models.GraphEdge.source_id == node_id
    ).all()

    incoming = db.query(models.GraphEdge).filter(
        models.GraphEdge.repository_id == repository_id,
        models.GraphEdge.target_type == node_type,
        models.GraphEdge.target_id == node_id
    ).all()

    return {
        "node": node_data,
        "outgoing": outgoing,
        "incoming": incoming
    }

from backend.fastapi_app.services.impact_service import get_impact_propagation

@router.get("/repositories/{repository_id}/impact/{node_type}/{node_id}", response_model=schemas.ImpactResponse)
def get_impact(repository_id: int, node_type: str, node_id: int, max_depth: int = 10, db: Session = Depends(get_db)):
    if node_type not in ["repository", "file", "symbol", "commit"]:
        raise HTTPException(status_code=400, detail="Unsupported node_type")

    repo = db.query(models.Repository).filter(models.Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    node_data = get_node_data(node_type, node_id, db)

    affected = get_impact_propagation(repository_id, node_type, node_id, db, max_depth=max_depth)

    return {
        "source": {
            "node_type": node_type,
            "node_id": node_id
        },
        "affected": affected
    }

from backend.fastapi_app.services.history_impact_service import get_historical_co_changes

@router.get("/repositories/{repository_id}/history/co-change/file/{file_id}", response_model=schemas.HistoricalCoChangeResponse)
def get_historical_co_change(repository_id: int, file_id: int, limit: int = 100, db: Session = Depends(get_db)):
    repo = db.query(models.Repository).filter(models.Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    file_record = db.query(models.File).filter(models.File.id == file_id, models.File.repository_id == repository_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in this repository")

    result = get_historical_co_changes(repository_id, "file", file_id, db, limit=limit)

    return result

from backend.fastapi_app.services.whatif_service import analyze_hypothetical_change

@router.post("/repositories/{repository_id}/whatif", response_model=schemas.WhatIfResponse)
def compute_whatif_scenario(repository_id: int, request: schemas.WhatIfRequest, db: Session = Depends(get_db)):
    repo = db.query(models.Repository).filter(models.Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if request.node_type not in ["file", "symbol"]:
        raise HTTPException(status_code=400, detail="Unsupported node_type")

    # Validate the source node exists in this repository
    if request.node_type == "file":
        node = db.query(models.File).filter_by(id=request.node_id, repository_id=repository_id).first()
    else:
        # For symbols, we'd join with files, but for M8 we're mostly testing file
        node = db.query(models.Symbol).join(models.File).filter(
            models.Symbol.id == request.node_id,
            models.File.repository_id == repository_id
        ).first()

    if not node:
        raise HTTPException(status_code=404, detail="Node not found in this repository")

    result = analyze_hypothetical_change(
        repository_id,
        request.node_type,
        request.node_id,
        db,
        max_depth=request.max_depth,
        historical_limit=request.historical_limit
    )

    return result

from backend.fastapi_app.services.evaluation_service import evaluate_commit

@router.post("/repositories/{repository_id}/evaluate", response_model=schemas.EvaluationResponse)
def compute_evaluation(repository_id: int, request: schemas.EvaluationRequest, db: Session = Depends(get_db)):
    return evaluate_commit(db, repository_id, request)
