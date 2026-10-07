import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from backend.fastapi_app.models import models
from backend.fastapi_app.models.base import Base
from backend.fastapi_app.services.history_impact_service import get_historical_co_changes

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
def history_data(db_session):
    r1 = models.Repository(id=1, name="R1", url="http://r1")
    r2 = models.Repository(id=2, name="R2", url="http://r2")
    db_session.add_all([r1, r2])
    db_session.flush()

    # Files
    fA = models.File(id=1, repository_id=1, path="A.js", created_at=datetime.utcnow())
    fB = models.File(id=2, repository_id=1, path="B.js", created_at=datetime.utcnow())
    fC = models.File(id=3, repository_id=1, path="C.js", created_at=datetime.utcnow())
    fD = models.File(id=4, repository_id=1, path="D.js", created_at=datetime.utcnow())
    fE = models.File(id=5, repository_id=1, path="E.js", created_at=datetime.utcnow())
    fA2 = models.File(id=6, repository_id=2, path="A.js", created_at=datetime.utcnow())
    fC2 = models.File(id=7, repository_id=2, path="C.js", created_at=datetime.utcnow())
    db_session.add_all([fA, fB, fC, fD, fE, fA2, fC2])
    db_session.flush()

    # Commits Repo 1
    c1 = models.Commit(id=1, repository_id=1, commit_hash="c1", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    c2 = models.Commit(id=2, repository_id=1, commit_hash="c2", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    c3 = models.Commit(id=3, repository_id=1, commit_hash="c3", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    c4 = models.Commit(id=4, repository_id=1, commit_hash="c4", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    c5 = models.Commit(id=5, repository_id=1, commit_hash="c5", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    
    # Commits Repo 2
    c6 = models.Commit(id=6, repository_id=2, commit_hash="c6", author_name="A", author_email="e", message="m", committed_at=datetime.utcnow(), created_at=datetime.utcnow())
    
    db_session.add_all([c1, c2, c3, c4, c5, c6])
    db_session.flush()

    def add_fc(cid, path):
        fc = models.CommitFileChange(commit_id=cid, file_path=path, change_type="modified", additions=1, deletions=1)
        db_session.add(fc)

    # 1. Basic co-change (c1: A + B)
    add_fc(1, "A.js")
    add_fc(1, "B.js")
    
    # 2. Multiple commits (c2: A + B, c3: A + C)
    add_fc(2, "A.js")
    add_fc(2, "B.js")
    
    add_fc(3, "A.js")
    add_fc(3, "C.js")
    
    # Unrelated commits (c4: D + E)
    add_fc(4, "D.js")
    add_fc(4, "E.js")
    
    # Multiple targets same commit (c5: A + B + C + D)
    add_fc(5, "A.js")
    add_fc(5, "B.js")
    add_fc(5, "C.js")
    add_fc(5, "D.js")
    
    # Repository isolation (c6 in repo 2: A + C)
    add_fc(6, "A.js")
    add_fc(6, "C.js")

    db_session.commit()

def test_basic_and_multiple_co_change(db_session, history_data):
    # A.js (node_id=1) changed in c1, c2, c3, c5 -> total 4 times
    res = get_historical_co_changes(1, "file", 1, db_session)
    assert res["source"]["node_id"] == 1
    assert res["source_change_count"] == 4
    
    # B.js changed with A in c1, c2, c5 -> 3 times
    # C.js changed with A in c3, c5 -> 2 times
    # D.js changed with A in c5 -> 1 time
    # E.js never changed with A
    
    co_changes = res["co_changes"]
    assert len(co_changes) == 3
    
    b_node = next(c for c in co_changes if c["node_id"] == 2)
    assert b_node["co_change_count"] == 3
    assert b_node["probability"] == 3.0 / 4.0
    
    c_node = next(c for c in co_changes if c["node_id"] == 3)
    assert c_node["co_change_count"] == 2
    assert c_node["probability"] == 2.0 / 4.0
    
    d_node = next(c for c in co_changes if c["node_id"] == 4)
    assert d_node["co_change_count"] == 1

def test_self_exclusion(db_session, history_data):
    res = get_historical_co_changes(1, "file", 1, db_session)
    ids = [c["node_id"] for c in res["co_changes"]]
    assert 1 not in ids

def test_unrelated_commits(db_session, history_data):
    res = get_historical_co_changes(1, "file", 1, db_session)
    ids = [c["node_id"] for c in res["co_changes"]]
    assert 5 not in ids # E.js changed in c4, but A.js did not

def test_repository_isolation(db_session, history_data):
    res = get_historical_co_changes(1, "file", 1, db_session)
    # Repo 2 has A+C, but C in repo 2 is node 7. A is node 6.
    # It should not bleed into Repo 1.
    ids = [c["node_id"] for c in res["co_changes"]]
    assert 7 not in ids

def test_deterministic_ordering(db_session, history_data):
    res1 = get_historical_co_changes(1, "file", 1, db_session)
    res2 = get_historical_co_changes(1, "file", 1, db_session)
    assert [c["node_id"] for c in res1["co_changes"]] == [c["node_id"] for c in res2["co_changes"]]
    # Count descending, so B (3) then C (2) then D (1)
    assert [c["node_id"] for c in res1["co_changes"]] == [2, 3, 4]

def test_source_with_no_history(db_session, history_data):
    # E.js (5) changed in c4, but let's test a fake file
    res = get_historical_co_changes(1, "file", 999, db_session)
    assert res["source_change_count"] == 0
    assert len(res["co_changes"]) == 0

def test_limit_behavior(db_session, history_data):
    res = get_historical_co_changes(1, "file", 1, db_session, limit=2)
    assert len(res["co_changes"]) == 2
    # Should be the top 2
    assert res["co_changes"][0]["node_id"] == 2
    assert res["co_changes"][1]["node_id"] == 3
