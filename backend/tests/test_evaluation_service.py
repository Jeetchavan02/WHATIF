import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from backend.fastapi_app.models import models
from backend.fastapi_app.schemas import schemas
from backend.fastapi_app.services.evaluation_service import evaluate_commit
from datetime import datetime, UTC

def setup_db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

def setup_test_data(db):
    repo = models.Repository(id=1, name="test_repo", url="http://test")
    other_repo = models.Repository(id=2, name="other_repo", url="http://other")
    db.add(repo)
    db.add(other_repo)

    fA = models.File(id=1, repository_id=1, path="A.js", created_at=datetime.now(UTC))
    fB = models.File(id=2, repository_id=1, path="B.js", created_at=datetime.now(UTC))
    fC = models.File(id=3, repository_id=1, path="C.js", created_at=datetime.now(UTC))
    fD = models.File(id=4, repository_id=1, path="D.js", created_at=datetime.now(UTC))
    fE = models.File(id=5, repository_id=1, path="E.js", created_at=datetime.now(UTC))
    fF = models.File(id=6, repository_id=1, path="F.js", created_at=datetime.now(UTC))
    
    fOther = models.File(id=10, repository_id=2, path="Other.js", created_at=datetime.now(UTC))
    
    db.add_all([fA, fB, fC, fD, fE, fF, fOther])

    c1 = models.Commit(id=1, repository_id=1, commit_hash="c1", author_name="A", author_email="e", message="m", committed_at=datetime.now(UTC), created_at=datetime.now(UTC))
    db.add(c1)
    
    c_other = models.Commit(id=2, repository_id=2, commit_hash="c2", author_name="A", author_email="e", message="m", committed_at=datetime.now(UTC), created_at=datetime.now(UTC))
    db.add(c_other)
    
    db.commit()
    return repo.id

def create_commit_file_changes(db, commit_id, file_paths):
    for path in file_paths:
        cf = models.CommitFileChange(commit_id=commit_id, file_path=path, change_type="modified")
        db.add(cf)
    db.commit()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_basic_evaluation(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # actual = {B, C}, calculated = {B, C}
    create_commit_file_changes(db, 1, ["A.js", "B.js", "C.js"])
    
    mock_impact.return_value = [
        {"node_type": "file", "node_id": 2, "depth": 1, "reason": "depends_on"},
        {"node_type": "file", "node_id": 3, "depth": 1, "reason": "depends_on"}
    ]
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert res.true_positives.count == 2
    assert res.false_positives.count == 0
    assert res.false_negatives.count == 0
    assert res.metrics.precision == 1.0
    assert res.metrics.recall == 1.0
    assert res.metrics.f1 == 1.0
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_mixed_result(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # actual = {B, C, D}, calculated = {B, C, E, F}
    create_commit_file_changes(db, 1, ["A.js", "B.js", "C.js", "D.js"])
    
    mock_impact.return_value = [
        {"node_type": "file", "node_id": 2, "depth": 1, "reason": "depends_on"},
        {"node_type": "file", "node_id": 3, "depth": 1, "reason": "depends_on"},
        {"node_type": "file", "node_id": 5, "depth": 1, "reason": "depends_on"},
        {"node_type": "file", "node_id": 6, "depth": 1, "reason": "depends_on"}
    ]
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert res.true_positives.count == 2
    assert res.false_positives.count == 2
    assert res.false_negatives.count == 1
    assert res.metrics.precision == 0.5
    assert abs(res.metrics.recall - 2/3) < 1e-6
    assert abs(res.metrics.f1 - 0.5714285714285715) < 1e-6
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_all_false_positives(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # actual = {B}, calculated = {C, D}
    create_commit_file_changes(db, 1, ["A.js", "B.js"])
    
    mock_impact.return_value = [
        {"node_type": "file", "node_id": 3, "depth": 1, "reason": "depends_on"},
        {"node_type": "file", "node_id": 4, "depth": 1, "reason": "depends_on"}
    ]
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert res.true_positives.count == 0
    assert res.false_positives.count == 2
    assert res.false_negatives.count == 1
    assert res.metrics.precision == 0.0
    assert res.metrics.recall == 0.0
    assert res.metrics.f1 == 0.0
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_all_false_negatives(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # actual = {B, C}, calculated = empty
    create_commit_file_changes(db, 1, ["A.js", "B.js", "C.js"])
    
    mock_impact.return_value = []
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert res.true_positives.count == 0
    assert res.false_positives.count == 0
    assert res.false_negatives.count == 2
    assert res.metrics.precision == 0.0
    assert res.metrics.recall == 0.0
    assert res.metrics.f1 == 0.0
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_perfect_recall_imperfect_precision(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # actual = {B}, calculated = {B, C}
    create_commit_file_changes(db, 1, ["A.js", "B.js"])
    
    mock_impact.return_value = [
        {"node_type": "file", "node_id": 2, "depth": 1, "reason": "depends_on"},
        {"node_type": "file", "node_id": 3, "depth": 1, "reason": "depends_on"}
    ]
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert res.true_positives.count == 1
    assert res.false_positives.count == 1
    assert res.false_negatives.count == 0
    assert res.metrics.precision == 0.5
    assert res.metrics.recall == 1.0
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_empty_actual_impact(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    # actual = empty
    create_commit_file_changes(db, 1, ["A.js"])
    
    mock_impact.return_value = [
        {"node_type": "file", "node_id": 2, "depth": 1, "reason": "depends_on"}
    ]
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert res.true_positives.count == 0
    assert res.false_positives.count == 1
    assert res.false_negatives.count == 0
    assert res.metrics.precision == 0.0
    assert res.metrics.recall == 0.0
    assert res.metrics.f1 == 0.0
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_source_exclusion(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    create_commit_file_changes(db, 1, ["A.js", "B.js"])
    
    # calculated somehow includes source file (should be excluded)
    mock_impact.return_value = [
        {"node_type": "file", "node_id": 1, "depth": 0, "reason": "depends_on"},
        {"node_type": "file", "node_id": 2, "depth": 1, "reason": "depends_on"}
    ]
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert 1 not in res.true_positives.file_ids
    assert 1 not in res.false_positives.file_ids
    assert 1 not in res.false_negatives.file_ids
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_repository_isolation(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    create_commit_file_changes(db, 1, ["A.js", "B.js", "Other.js"])
    
    mock_impact.return_value = [
        {"node_type": "file", "node_id": 2, "depth": 1, "reason": "depends_on"}
    ]
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert 10 not in res.actual_impact.file_ids
    db.close()

def test_invalid_commit():
    db = setup_db()
    repo_id = setup_test_data(db)
    
    req = schemas.EvaluationRequest(commit_id=999, source_file_id=1)
    with pytest.raises(HTTPException) as excinfo:
        evaluate_commit(db, repo_id, req)
    assert excinfo.value.status_code == 404
    db.close()

def test_invalid_source_file():
    db = setup_db()
    repo_id = setup_test_data(db)
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=999)
    with pytest.raises(HTTPException) as excinfo:
        evaluate_commit(db, repo_id, req)
    assert excinfo.value.status_code == 404
    db.close()

def test_source_file_not_changed_in_commit():
    db = setup_db()
    repo_id = setup_test_data(db)
    
    create_commit_file_changes(db, 1, ["B.js", "C.js"])
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    with pytest.raises(HTTPException) as excinfo:
        evaluate_commit(db, repo_id, req)
    assert excinfo.value.status_code == 400
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_max_depth_behavior(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    create_commit_file_changes(db, 1, ["A.js", "B.js"])
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1, max_depth=2)
    evaluate_commit(db, repo_id, req)
    
    mock_impact.assert_called_once_with(repo_id=repo_id, node_type="file", node_id=1, db=db, max_depth=2)
    db.close()

@patch("backend.fastapi_app.services.evaluation_service.get_impact_propagation")
def test_deterministic_ordering(mock_impact):
    db = setup_db()
    repo_id = setup_test_data(db)
    
    create_commit_file_changes(db, 1, ["A.js", "C.js", "B.js"])
    
    mock_impact.return_value = [
        {"node_type": "file", "node_id": 3, "depth": 1, "reason": "depends_on"},
        {"node_type": "file", "node_id": 2, "depth": 1, "reason": "depends_on"}
    ]
    
    req = schemas.EvaluationRequest(commit_id=1, source_file_id=1)
    res = evaluate_commit(db, repo_id, req)
    
    assert res.actual_impact.file_ids == sorted(res.actual_impact.file_ids)
    assert res.calculated_impact.file_ids == sorted(res.calculated_impact.file_ids)
    assert res.true_positives.file_ids == sorted(res.true_positives.file_ids)
    db.close()
