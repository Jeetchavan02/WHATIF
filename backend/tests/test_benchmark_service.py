import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.fastapi_app.models import models
from backend.fastapi_app.schemas import schemas
from backend.fastapi_app.services.benchmark_service import run_benchmark, calculate_metrics
from datetime import datetime, UTC
from fastapi.testclient import TestClient
from backend.fastapi_app.main import app
from backend.fastapi_app.core.database import get_db

def setup_db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

def setup_test_data(db):
    repo = models.Repository(id=1, name="repo1", url="http://r1")
    other_repo = models.Repository(id=2, name="repo2", url="http://r2")
    db.add(repo)
    db.add(other_repo)
    
    # Files
    files = [
        models.File(id=1, repository_id=1, path="A.js", created_at=datetime.now(UTC)),
        models.File(id=2, repository_id=1, path="B.js", created_at=datetime.now(UTC)),
        models.File(id=3, repository_id=1, path="C.js", created_at=datetime.now(UTC)),
        models.File(id=4, repository_id=1, path="D.js", created_at=datetime.now(UTC)),
        models.File(id=5, repository_id=1, path="E.js", created_at=datetime.now(UTC)),
        models.File(id=10, repository_id=2, path="Other.js", created_at=datetime.now(UTC)),
    ]
    db.add_all(files)
    db.commit()
    return repo.id

def create_commit(db, repo_id, c_id, file_paths):
    c = models.Commit(id=c_id, repository_id=repo_id, commit_hash=f"c{c_id}", author_name="A", author_email="e", message="m", committed_at=datetime.now(UTC), created_at=datetime.now(UTC))
    db.add(c)
    for p in file_paths:
        cf = models.CommitFileChange(commit_id=c_id, file_path=p, change_type="modified")
        db.add(cf)
    db.commit()

@patch("backend.fastapi_app.services.benchmark_service.get_impact_propagation")
@patch("backend.fastapi_app.services.benchmark_service.get_historical_co_changes")
@patch("backend.fastapi_app.services.benchmark_service.analyze_hypothetical_change")
def test_example_unit_data(mock_whatif, mock_hist, mock_struct):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # A is source. Actual changed: A, B, C, D (so impact is B, C, D)
    create_commit(db, repo_id, 1, ["A.js", "B.js", "C.js", "D.js"])
    
    # Structural calculated: B, C
    mock_struct.return_value = [
        {"node_type": "file", "node_id": 2},
        {"node_type": "file", "node_id": 3}
    ]
    
    # Historical calculated: B, D, E
    mock_hist.return_value = {
        "co_changes": [
            {"node_type": "file", "node_id": 2},
            {"node_type": "file", "node_id": 4},
            {"node_type": "file", "node_id": 5}
        ]
    }
    
    # Combined calculated: B, C, D
    mock_whatif.return_value = {
        "affected_components": [
            {"node_type": "file", "node_id": 2},
            {"node_type": "file", "node_id": 3},
            {"node_type": "file", "node_id": 4}
        ]
    }
    
    req = schemas.BenchmarkRequest(limit=10)
    res = run_benchmark(db, repo_id, req)
    
    assert res.case_count == 1
    c = res.cases[0]
    
    # Structural
    assert c.structural.tp == 2
    assert c.structural.fp == 0
    assert c.structural.fn == 1
    
    # Historical
    assert c.historical.tp == 2
    assert c.historical.fp == 1
    assert c.historical.fn == 1
    
    # Combined
    assert c.combined.tp == 3
    assert c.combined.fp == 0
    assert c.combined.fn == 0
    
    db.close()

def test_metrics_math():
    res = calculate_metrics(2, 0, 1)
    assert res["precision"] == 1.0
    assert abs(res["recall"] - 2/3) < 1e-6
    
    res2 = calculate_metrics(0, 0, 0)
    assert res2["precision"] == 0.0
    assert res2["recall"] == 0.0
    assert res2["f1"] == 0.0

@patch("backend.fastapi_app.services.benchmark_service.get_impact_propagation")
@patch("backend.fastapi_app.services.benchmark_service.get_historical_co_changes")
@patch("backend.fastapi_app.services.benchmark_service.analyze_hypothetical_change")
def test_exclusions_and_limits(mock_whatif, mock_hist, mock_struct):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # Excluded because only 1 file
    create_commit(db, repo_id, 1, ["A.js"])
    
    # Included
    create_commit(db, repo_id, 2, ["A.js", "B.js"])
    create_commit(db, repo_id, 3, ["B.js", "C.js"])
    create_commit(db, repo_id, 4, ["C.js", "D.js"])
    
    # Repository isolation
    create_commit(db, 2, 5, ["Other.js", "A.js"]) # Different repo
    
    mock_struct.return_value = []
    mock_hist.return_value = {}
    mock_whatif.return_value = {}
    
    # Test limit=2
    req = schemas.BenchmarkRequest(limit=2)
    res = run_benchmark(db, repo_id, req)
    
    assert res.case_count == 2
    assert [c.commit_id for c in res.cases] == [2, 3]
    
    db.close()

@patch("backend.fastapi_app.services.benchmark_service.get_impact_propagation")
@patch("backend.fastapi_app.services.benchmark_service.get_historical_co_changes")
@patch("backend.fastapi_app.services.benchmark_service.analyze_hypothetical_change")
def test_aggregates(mock_whatif, mock_hist, mock_struct):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    create_commit(db, repo_id, 1, ["A.js", "B.js"])
    create_commit(db, repo_id, 2, ["B.js", "C.js"])
    create_commit(db, repo_id, 3, ["C.js", "D.js"])
    
    # Provide distinct results to test min/max/mean/median
    # Case 1: TP=1, FP=0, FN=0 -> P=1, R=1, F1=1
    # Case 2: TP=0, FP=1, FN=1 -> P=0, R=0, F1=0
    # Case 3: TP=1, FP=1, FN=0 -> P=0.5, R=1, F1=0.666
    
    mock_struct.side_effect = [
        [{"node_type": "file", "node_id": 2}], # Case 1: B is predicted. Actual is B.
        [{"node_type": "file", "node_id": 4}], # Case 2: D is predicted. Actual is C (source B).
        [{"node_type": "file", "node_id": 4}, {"node_type": "file", "node_id": 5}] # Case 3: D, E predicted. Actual is D (source C).
    ]
    mock_hist.return_value = {}
    mock_whatif.return_value = {}
    
    req = schemas.BenchmarkRequest(limit=10)
    res = run_benchmark(db, repo_id, req)
    
    assert res.case_count == 3
    
    s = res.structural
    assert s.case_count == 3
    assert s.min_precision == 0.0
    assert s.max_precision == 1.0
    assert s.median_precision == 0.5
    assert s.mean_precision == (0.0 + 0.5 + 1.0) / 3
    
    db.close()

@patch("backend.fastapi_app.services.benchmark_service.get_impact_propagation")
@patch("backend.fastapi_app.services.benchmark_service.get_historical_co_changes")
@patch("backend.fastapi_app.services.benchmark_service.analyze_hypothetical_change")
def test_source_file_filtering(mock_whatif, mock_hist, mock_struct):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # Add non-source files to DB
    extra_files = [
        models.File(id=20, repository_id=repo_id, path=".env", created_at=datetime.now(UTC)),
        models.File(id=21, repository_id=repo_id, path=".gitignore", created_at=datetime.now(UTC)),
        models.File(id=22, repository_id=repo_id, path="README.md", created_at=datetime.now(UTC)),
        models.File(id=23, repository_id=repo_id, path="package.json", created_at=datetime.now(UTC)),
        models.File(id=24, repository_id=repo_id, path="valid.py", created_at=datetime.now(UTC)),
        models.File(id=25, repository_id=repo_id, path="valid.tsx", created_at=datetime.now(UTC)),
    ]
    db.add_all(extra_files)
    db.commit()
    
    # Commit with only non-source files -> should be skipped
    create_commit(db, repo_id, 10, [".env", ".gitignore", "README.md", "package.json"])
    
    # Commit with non-source files and ONE valid source file -> valid source is chosen
    create_commit(db, repo_id, 11, [".env", ".gitignore", "README.md", "valid.py"])
    
    # Commit with multiple valid source files and non-source files -> deterministic valid source is chosen
    create_commit(db, repo_id, 12, [".env", "valid.tsx", "valid.py"])
    
    mock_struct.return_value = []
    mock_hist.return_value = {}
    mock_whatif.return_value = {}
    
    req = schemas.BenchmarkRequest(limit=10)
    res = run_benchmark(db, repo_id, req)
    
    # Commit 10 is skipped. Only 11 and 12 are included.
    assert res.case_count == 2
    
    c11 = next(c for c in res.cases if c.commit_id == 11)
    assert c11.source_file_path == "valid.py"
    assert c11.actual_impact_count == 3  # .env, .gitignore, README.md
    
    c12 = next(c for c in res.cases if c.commit_id == 12)
    assert c12.source_file_path == "valid.py"  # valid.py comes before valid.tsx alphabetically
    assert c12.actual_impact_count == 2  # .env, valid.tsx
    
    db.close()

@patch("backend.fastapi_app.services.benchmark_service.run_benchmark")
def test_api_endpoint(mock_run):
    mock_run.return_value = schemas.BenchmarkResponse(
        repository_id=1,
        parameters={"limit": 50, "max_depth": 5, "historical_limit": 50},
        case_count=0,
        structural=schemas.BenchmarkAggregate(case_count=0, mean_precision=0, mean_recall=0, mean_f1=0, median_precision=0, median_recall=0, median_f1=0, min_precision=0, min_recall=0, min_f1=0, max_precision=0, max_recall=0, max_f1=0),
        historical=schemas.BenchmarkAggregate(case_count=0, mean_precision=0, mean_recall=0, mean_f1=0, median_precision=0, median_recall=0, median_f1=0, min_precision=0, min_recall=0, min_f1=0, max_precision=0, max_recall=0, max_f1=0),
        combined=schemas.BenchmarkAggregate(case_count=0, mean_precision=0, mean_recall=0, mean_f1=0, median_precision=0, median_recall=0, median_f1=0, min_precision=0, min_recall=0, min_f1=0, max_precision=0, max_recall=0, max_f1=0),
        cases=[]
    )
    
    client = TestClient(app)
    response = client.post("/api/repositories/1/benchmark", json={"limit": 50})
    assert response.status_code == 200
    assert response.json()["repository_id"] == 1
    assert response.json()["case_count"] == 0
