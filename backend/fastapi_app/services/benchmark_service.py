from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from backend.fastapi_app.models import models
from backend.fastapi_app.schemas import schemas
from backend.fastapi_app.services.impact_service import get_impact_propagation
from backend.fastapi_app.services.history_impact_service import get_historical_co_changes
from backend.fastapi_app.services.whatif_service import analyze_hypothetical_change

def calculate_metrics(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}

def get_metrics_for_set(actual: set, calculated: set) -> schemas.BenchmarkMethodMetrics:
    tp = len(actual.intersection(calculated))
    fp = len(calculated - actual)
    fn = len(actual - calculated)
    
    mets = calculate_metrics(tp, fp, fn)
    return schemas.BenchmarkMethodMetrics(
        predicted_count=len(calculated),
        tp=tp,
        fp=fp,
        fn=fn,
        precision=mets["precision"],
        recall=mets["recall"],
        f1=mets["f1"]
    )

def calculate_aggregates(cases: List[schemas.BenchmarkCase], method: str, case_count: int) -> schemas.BenchmarkAggregate:
    if case_count == 0:
        return schemas.BenchmarkAggregate(
            case_count=0,
            mean_precision=0.0, mean_recall=0.0, mean_f1=0.0,
            median_precision=0.0, median_recall=0.0, median_f1=0.0,
            min_precision=0.0, min_recall=0.0, min_f1=0.0,
            max_precision=0.0, max_recall=0.0, max_f1=0.0
        )
        
    precisions = sorted([getattr(c, method).precision for c in cases])
    recalls = sorted([getattr(c, method).recall for c in cases])
    f1s = sorted([getattr(c, method).f1 for c in cases])
    
    def median(lst):
        n = len(lst)
        if n % 2 == 1:
            return lst[n//2]
        else:
            return (lst[n//2 - 1] + lst[n//2]) / 2.0
            
    def mean(lst):
        return sum(lst) / len(lst)
        
    return schemas.BenchmarkAggregate(
        case_count=case_count,
        mean_precision=mean(precisions),
        mean_recall=mean(recalls),
        mean_f1=mean(f1s),
        median_precision=median(precisions),
        median_recall=median(recalls),
        median_f1=median(f1s),
        min_precision=precisions[0],
        min_recall=recalls[0],
        min_f1=f1s[0],
        max_precision=precisions[-1],
        max_recall=recalls[-1],
        max_f1=f1s[-1]
    )

def run_benchmark(db: Session, repository_id: int, request: schemas.BenchmarkRequest) -> schemas.BenchmarkResponse:
    # Deterministic commit selection
    commits = db.query(models.Commit).filter(
        models.Commit.repository_id == repository_id
    ).order_by(models.Commit.committed_at.asc(), models.Commit.id.asc()).all()
    
    cases: List[schemas.BenchmarkCase] = []
    
    for commit in commits:
        if len(cases) >= request.limit:
            break
            
        file_changes = db.query(models.CommitFileChange).filter(
            models.CommitFileChange.commit_id == commit.id
        ).all()
        
        if len(file_changes) < 2:
            continue
            
        changed_paths = set(c.file_path for c in file_changes)
        
        changed_files = db.query(models.File).filter(
            models.File.repository_id == repository_id,
            models.File.path.in_(changed_paths)
        ).all()
        
        if not changed_files:
            continue
            
        changed_file_ids = set(f.id for f in changed_files)
        
        allowed_extensions = {".py", ".js", ".jsx", ".ts", ".tsx"}
        valid_source_files = [f for f in changed_files if any(f.path.endswith(ext) for ext in allowed_extensions)]
        
        if not valid_source_files:
            continue
            
        changed_files_sorted = sorted(valid_source_files, key=lambda x: x.path)
        source_file = changed_files_sorted[0]
        source_file_id = source_file.id
        
        actual_impact_set = changed_file_ids - {source_file_id}
        
        if not actual_impact_set:
            continue
            
        structural_res = get_impact_propagation(repository_id, "file", source_file_id, db, request.max_depth)
        structural_calculated = set(res["node_id"] for res in structural_res if res["node_type"] == "file")
        structural_calculated.discard(source_file_id)
        
        historical_res = get_historical_co_changes(repository_id, "file", source_file_id, db, request.historical_limit)
        historical_calculated = set(h["node_id"] for h in historical_res.get("co_changes", []) if h["node_type"] == "file")
        historical_calculated.discard(source_file_id)
        
        combined_res = analyze_hypothetical_change(
            repository_id, "file", source_file_id, db, request.max_depth, request.historical_limit
        )
        combined_calculated = set(c["node_id"] for c in combined_res.get("affected_components", []) if c["node_type"] == "file")
        combined_calculated.discard(source_file_id)
        
        structural_metrics = get_metrics_for_set(actual_impact_set, structural_calculated)
        historical_metrics = get_metrics_for_set(actual_impact_set, historical_calculated)
        combined_metrics = get_metrics_for_set(actual_impact_set, combined_calculated)
        
        cases.append(schemas.BenchmarkCase(
            commit_id=commit.id,
            commit_hash=commit.commit_hash,
            source_file_id=source_file_id,
            source_file_path=source_file.path,
            actual_impact_count=len(actual_impact_set),
            structural=structural_metrics,
            historical=historical_metrics,
            combined=combined_metrics
        ))
        
    case_count = len(cases)
    
    return schemas.BenchmarkResponse(
        repository_id=repository_id,
        parameters={"limit": request.limit, "max_depth": request.max_depth, "historical_limit": request.historical_limit},
        case_count=case_count,
        structural=calculate_aggregates(cases, "structural", case_count),
        historical=calculate_aggregates(cases, "historical", case_count),
        combined=calculate_aggregates(cases, "combined", case_count),
        cases=cases
    )
