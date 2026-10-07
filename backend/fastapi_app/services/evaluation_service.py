from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.fastapi_app.models import models
from backend.fastapi_app.schemas import schemas
from backend.fastapi_app.services.impact_service import get_impact_propagation

def evaluate_commit(db: Session, repository_id: int, request: schemas.EvaluationRequest) -> schemas.EvaluationResponse:
    # 1. Validate Repository exists
    repo = db.query(models.Repository).filter(models.Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    # 2. Validate Commit exists and belongs to repository
    commit = db.query(models.Commit).filter(
        models.Commit.id == request.commit_id,
        models.Commit.repository_id == repository_id
    ).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found or does not belong to repository")
        
    # 3. Validate Source File exists and belongs to repository
    source_file = db.query(models.File).filter(
        models.File.id == request.source_file_id,
        models.File.repository_id == repository_id
    ).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found or does not belong to repository")
        
    # 4. Determine Actual Impact
    commit_file_changes = db.query(models.CommitFileChange).filter(
        models.CommitFileChange.commit_id == commit.id
    ).all()
    
    changed_paths = set(c.file_path for c in commit_file_changes)
    
    changed_files = db.query(models.File).filter(
        models.File.repository_id == repository_id,
        models.File.path.in_(changed_paths)
    ).all()
    
    changed_file_ids = set(f.id for f in changed_files)
    
    if request.source_file_id not in changed_file_ids:
        raise HTTPException(status_code=400, detail="Source file was not changed in the specified commit")
        
    actual_impact_set = changed_file_ids - {request.source_file_id}
    
    # 5. Calculate WHATIF Impact (Structural)
    structural_results = get_impact_propagation(
        repo_id=repository_id,
        node_type="file",
        node_id=request.source_file_id,
        db=db,
        max_depth=request.max_depth
    )
    
    calculated_impact_set = set(
        res["node_id"] for res in structural_results 
        if res["node_type"] == "file"
    )
    calculated_impact_set.discard(request.source_file_id)
    
    # 6. Normalize and Compare Sets
    true_positives = actual_impact_set.intersection(calculated_impact_set)
    false_positives = calculated_impact_set - actual_impact_set
    false_negatives = actual_impact_set - calculated_impact_set
    
    # 7. Metrics
    tp = len(true_positives)
    fp = len(false_positives)
    fn = len(false_negatives)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    actual_list = sorted(list(actual_impact_set))
    calculated_list = sorted(list(calculated_impact_set))
    tp_list = sorted(list(true_positives))
    fp_list = sorted(list(false_positives))
    fn_list = sorted(list(false_negatives))
    
    return schemas.EvaluationResponse(
        repository_id=repository_id,
        commit_id=request.commit_id,
        source_file_id=request.source_file_id,
        actual_impact=schemas.EvaluationSet(count=len(actual_list), file_ids=actual_list),
        calculated_impact=schemas.EvaluationSet(count=len(calculated_list), file_ids=calculated_list),
        true_positives=schemas.EvaluationSet(count=len(tp_list), file_ids=tp_list),
        false_positives=schemas.EvaluationSet(count=len(fp_list), file_ids=fp_list),
        false_negatives=schemas.EvaluationSet(count=len(fn_list), file_ids=fn_list),
        metrics=schemas.EvaluationMetrics(
            precision=precision,
            recall=recall,
            f1=f1
        )
    )
