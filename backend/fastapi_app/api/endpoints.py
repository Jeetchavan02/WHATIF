from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from backend.fastapi_app.schemas import schemas
from backend.fastapi_app.models import models
from backend.fastapi_app.core.database import get_db
from backend.fastapi_app.core.analyzer import run_analysis

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
