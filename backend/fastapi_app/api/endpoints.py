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
