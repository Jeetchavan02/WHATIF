import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.fastapi_app.models.base import Base
from backend.fastapi_app.models import models
from backend.fastapi_app.services.graph_service import build_repository_graph, resolve_local_dependency

@pytest.fixture(scope="module")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_local_dependency_resolution(db_session):
    repo = models.Repository(name="Test Repo", url="dummy")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    f1 = models.File(repository_id=repo.id, path="src/A.js", language="javascript")
    f2 = models.File(repository_id=repo.id, path="src/B.ts", language="typescript")
    f3 = models.File(repository_id=repo.id, path="src/utils/index.js", language="javascript")
    db_session.add_all([f1, f2, f3])
    db_session.commit()

    # A.js -> ./B (resolves to B.ts)
    res = resolve_local_dependency(repo.id, "src/A.js", "./B", db_session)
    assert res is not None and res.id == f2.id

    # A.js -> ./utils (resolves to utils/index.js)
    res = resolve_local_dependency(repo.id, "src/A.js", "./utils", db_session)
    assert res is not None and res.id == f3.id

    # Unresolved doesn't crash
    res = resolve_local_dependency(repo.id, "src/A.js", "./C", db_session)
    assert res is None

def test_graph_builder(db_session):
    repo = models.Repository(name="Graph Repo", url="dummy2")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    f_a = models.File(repository_id=repo.id, path="a.js")
    f_b = models.File(repository_id=repo.id, path="b.js")
    db_session.add_all([f_a, f_b])
    db_session.commit()

    sym = models.Symbol(file_id=f_a.id, name="foo", symbol_type="function")
    db_session.add(sym)
    db_session.commit()

    # dep with no target_file_id but resolvable target_name
    dep = models.Dependency(repository_id=repo.id, source_file_id=f_a.id, dependency_type="import", target_name="./b")
    # unresolved dep
    dep_bad = models.Dependency(repository_id=repo.id, source_file_id=f_a.id, dependency_type="import", target_name="fs")
    db_session.add_all([dep, dep_bad])
    db_session.commit()

    commit = models.Commit(repository_id=repo.id, commit_hash="123", author_name="a", author_email="e", message="m")
    db_session.add(commit)
    db_session.commit()

    fc = models.CommitFileChange(commit_id=commit.id, file_path="a.js", change_type="modified")
    db_session.add(fc)
    db_session.commit()

    sc = models.CommitSymbolChange(commit_file_change_id=fc.id, symbol_name="foo", change_type="modified")
    db_session.add(sc)
    db_session.commit()

    # Build graph
    res1 = build_repository_graph(repo.id, db_session)
    
    # Assert edges
    edges = db_session.query(models.GraphEdge).filter_by(repository_id=repo.id).all()
    # Expect: 
    # sym->file (defined_in)
    # file->file (depends_on)
    # commit->file (changed)
    # commit->symbol (changed)
    assert len(edges) == 4
    edge_types = {(e.source_type, e.target_type, e.edge_type) for e in edges}
    assert ("symbol", "file", "defined_in") in edge_types
    assert ("file", "file", "depends_on") in edge_types
    assert ("commit", "file", "changed") in edge_types
    assert ("commit", "symbol", "changed") in edge_types

    # Test Idempotency / Rebuild behavior
    # Now that the API wipes and rebuilds, it will create 4 edges again
    res2 = build_repository_graph(repo.id, db_session)
    assert res2["edges_created"] == 4
    edges_after = db_session.query(models.GraphEdge).filter_by(repository_id=repo.id).all()
    assert len(edges_after) == 4
