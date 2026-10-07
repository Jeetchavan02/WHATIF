import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from backend.fastapi_app.models import models
from backend.fastapi_app.models.base import Base
from backend.fastapi_app.services.whatif_service import analyze_hypothetical_change

engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def whatif_data(db_session):
    repo_id = 99
    other_repo = 100
    r1 = models.Repository(id=repo_id, name="R1", url="http://r1")
    r2 = models.Repository(id=other_repo, name="R2", url="http://r2")
    db_session.add_all([r1, r2])
    db_session.flush()

    # Files
    fA = models.File(id=1, repository_id=repo_id, path="A.js", created_at=datetime.utcnow())
    fB = models.File(id=2, repository_id=repo_id, path="B.js", created_at=datetime.utcnow())
    fC = models.File(id=3, repository_id=repo_id, path="C.js", created_at=datetime.utcnow())
    fD = models.File(id=4, repository_id=repo_id, path="D.js", created_at=datetime.utcnow())
    fE = models.File(id=5, repository_id=other_repo, path="E.js", created_at=datetime.utcnow())
    db_session.add_all([fA, fB, fC, fD, fE])
    db_session.flush()

    # Structural Graph (M6)
    # A -> B structurally (B depends on A) -> traverse backwards from A -> hit B
    e1 = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=2, target_type="file", target_id=1, edge_type="depends_on")
    # A -> B structurally again just in case (we only use one)
    db_session.add(e1)
    
    # Historical Commits (M7)
    # Commit 1: A + C (A+C historically)
    c1 = models.Commit(id=1, repository_id=repo_id, commit_hash="c1", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    db_session.add(c1)
    
    # Commit 2: A + B (A+B historically and structurally)
    c2 = models.Commit(id=2, repository_id=repo_id, commit_hash="c2", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    db_session.add(c2)
    
    # Unrelated repo commit
    c3 = models.Commit(id=3, repository_id=other_repo, commit_hash="c3", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    db_session.add(c3)
    
    db_session.flush()
    
    db_session.add(models.CommitFileChange(commit_id=1, file_path="A.js", change_type="modified", additions=1, deletions=1))
    db_session.add(models.CommitFileChange(commit_id=1, file_path="C.js", change_type="modified", additions=1, deletions=1))
    
    db_session.add(models.CommitFileChange(commit_id=2, file_path="A.js", change_type="modified", additions=1, deletions=1))
    db_session.add(models.CommitFileChange(commit_id=2, file_path="B.js", change_type="modified", additions=1, deletions=1))
    
    # Unrelated repo
    db_session.add(models.CommitFileChange(commit_id=3, file_path="E.js", change_type="modified", additions=1, deletions=1))
    
    db_session.commit()
    
    return repo_id


def test_whatif_scenario(db_session, whatif_data):
    repo_id = whatif_data
    
    # A (id 1)
    # - B (id 2) depends on A structurally. B changed with A in c2. -> BOTH
    # - C (id 3) changed with A in c1. Not connected structurally. -> HISTORICAL_ONLY
    # Let's say D depends on C.
    e_d = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=4, target_type="file", target_id=1, edge_type="depends_on")
    db_session.add(e_d)
    db_session.commit()
    # Now D depends on A structurally, but never changed with A -> STRUCTURAL_ONLY
    
    res = analyze_hypothetical_change(repo_id, "file", 1, db_session)
    
    assert res["source"]["node_id"] == 1
    
    comps = res["affected_components"]
    assert len(comps) == 3
    
    # Check BOTH
    b = next(c for c in comps if c["node_id"] == 2)
    assert b["classification"] == "BOTH"
    assert b["structural"]["depth"] == 1
    assert b["historical"]["co_change_count"] == 1
    assert b["historical"]["co_change_rate"] == 0.5
    
    # Check HISTORICAL_ONLY
    c_node = next(c for c in comps if c["node_id"] == 3)
    assert c_node["classification"] == "HISTORICAL_ONLY"
    assert c_node["structural"] is None
    assert c_node["historical"]["co_change_count"] == 1
    assert c_node["historical"]["co_change_rate"] == 0.5
    
    # Check STRUCTURAL_ONLY
    d = next(c for c in comps if c["node_id"] == 4)
    assert d["classification"] == "STRUCTURAL_ONLY"
    assert d["historical"] is None
    assert d["structural"]["depth"] == 1
    
    # Deterministic Ordering check
    # Priority: BOTH (2), STRUCTURAL_ONLY (4), HISTORICAL_ONLY (3)
    assert comps[0]["node_id"] == 2
    assert comps[1]["node_id"] == 4
    assert comps[2]["node_id"] == 3

def test_no_history_source(db_session, whatif_data):
    # E.js (5) in other repo
    res = analyze_hypothetical_change(100, "file", 5, db_session)
    assert res["historical_impact"]["source_change_count"] == 1 # Has 1 commit (c3)
    # But no co-changes
    assert len(res["affected_components"]) == 0

def test_empty_result(db_session, whatif_data):
    f_new = models.File(id=10, repository_id=99, path="New.js", created_at=datetime.utcnow())
    db_session.add(f_new)
    db_session.commit()
    
    res = analyze_hypothetical_change(99, "file", 10, db_session)
    assert res["structural_impact"]["total_affected"] == 0
    assert res["historical_impact"]["source_change_count"] == 0
    assert len(res["affected_components"]) == 0
