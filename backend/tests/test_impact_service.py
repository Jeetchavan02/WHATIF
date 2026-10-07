import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.fastapi_app.models import models
from backend.fastapi_app.models.base import Base
from backend.fastapi_app.services.impact_service import get_impact_propagation

# Use in-memory SQLite database for testing
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
def graph_data(db_session):
    repo_id = 99
    other_repo_id = 100
    repo = models.Repository(id=repo_id, name="Test Repo", url="http://test.com")
    db_session.add(repo)
    
    other_repo = models.Repository(id=other_repo_id, name="Other", url="http://other.com")
    db_session.add(other_repo)
    
    # 1. Direct dependency: B depends on A (A -> B backwards)
    # File 1 (A), File 2 (B)
    e1 = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=2, target_type="file", target_id=1, edge_type="depends_on")
    
    # 2. Transitive dependency: C depends on B (B -> C backwards)
    # File 3 (C)
    e2 = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=3, target_type="file", target_id=2, edge_type="depends_on")
    
    # 3. Transitive dependency: D depends on C (C -> D backwards)
    e3 = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=4, target_type="file", target_id=3, edge_type="depends_on")
    
    # 4. Cycle protection: D depends on B
    e_cycle = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=2, target_type="file", target_id=4, edge_type="depends_on")
    
    # 5. Unrelated node: E depends on F
    e_unrelated = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=6, target_type="file", target_id=5, edge_type="depends_on")
    
    # 7. Multiple parents: C depends on B, C also depends on X (File 10)
    e_multi = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=3, target_type="file", target_id=10, edge_type="depends_on")
    
    # 8. Repository isolation: Other repo edge
    e_other = models.GraphEdge(repository_id=other_repo_id, source_type="file", source_id=99, target_type="file", target_id=1, edge_type="depends_on")
    
    # 9. Unsupported edge type: Should not be traversed
    e_unsupported = models.GraphEdge(repository_id=repo_id, source_type="file", source_id=7, target_type="file", target_id=1, edge_type="changed")
    
    db_session.add_all([e1, e2, e3, e_cycle, e_unrelated, e_multi, e_other, e_unsupported])
    db_session.commit()
    
    return repo_id

def test_direct_dependency(db_session, graph_data):
    # File 2 depends on File 1. So if File 1 changes, File 2 is affected (depth 1)
    affected = get_impact_propagation(graph_data, "file", 1, db_session)
    assert len(affected) >= 1
    assert any(a["node_id"] == 2 and a["depth"] == 1 for a in affected)

def test_transitive_dependency(db_session, graph_data):
    # A (1) <- B (2) <- C (3) <- D (4)
    # Starting from 2 (B), affected should be 3 (depth 1) and 4 (depth 2)
    affected = get_impact_propagation(graph_data, "file", 2, db_session)
    ids = [a["node_id"] for a in affected]
    assert 3 in ids
    assert 4 in ids
    assert not any(a["node_id"] == 1 for a in affected) # 1 does not depend on 2
    
def test_max_depth(db_session, graph_data):
    # 1 <- 2 <- 3 <- 4
    # With max_depth 1 from 1, we should only see 2.
    affected = get_impact_propagation(graph_data, "file", 1, db_session, max_depth=1)
    ids = [a["node_id"] for a in affected]
    assert 2 in ids
    assert 3 not in ids
    assert 4 not in ids

def test_cycle_protection(db_session, graph_data):
    # 2 depends on 4, 4 depends on 3, 3 depends on 2
    affected = get_impact_propagation(graph_data, "file", 2, db_session, max_depth=10)
    # It should not loop infinitely, and should return finite results
    assert isinstance(affected, list)

def test_unrelated_node(db_session, graph_data):
    # 5 <- 6 is unrelated to 1
    affected = get_impact_propagation(graph_data, "file", 1, db_session)
    ids = [a["node_id"] for a in affected]
    assert 5 not in ids
    assert 6 not in ids

def test_deterministic_ordering(db_session, graph_data):
    affected1 = get_impact_propagation(graph_data, "file", 1, db_session)
    affected2 = get_impact_propagation(graph_data, "file", 1, db_session)
    assert [a["node_id"] for a in affected1] == [a["node_id"] for a in affected2]

def test_multiple_parents(db_session, graph_data):
    # 3 depends on 10
    affected = get_impact_propagation(graph_data, "file", 10, db_session)
    ids = [a["node_id"] for a in affected]
    assert 3 in ids

def test_repository_isolation(db_session, graph_data):
    # Edge in repo 100 targets file 1, but we query repo 99
    affected = get_impact_propagation(graph_data, "file", 1, db_session)
    ids = [a["node_id"] for a in affected]
    assert 99 not in ids

def test_unsupported_edge_types(db_session, graph_data):
    # File 7 targets File 1 with "changed" edge.
    affected = get_impact_propagation(graph_data, "file", 1, db_session)
    ids = [a["node_id"] for a in affected]
    assert 7 not in ids
