import pytest
import os
import shutil
import tempfile
import subprocess
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.fastapi_app.models.base import Base
from backend.fastapi_app.models import models
from backend.fastapi_app.services.git_history_service import extract_git_history
from backend.fastapi_app.main import app
from backend.fastapi_app.core.database import get_db

@pytest.fixture(scope="module")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture(scope="module")
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture(scope="module")
def regression_repo():
    temp_dir = tempfile.mkdtemp()
    
    def run_git(*args):
        subprocess.run(["git", *args], cwd=temp_dir, check=True, capture_output=True)

    run_git("init", "-b", "main")
    run_git("config", "user.name", "Test User")
    run_git("config", "user.email", "test@example.com")
    
    # Create normal file and node_modules file
    os.makedirs(os.path.join(temp_dir, "node_modules", "package"), exist_ok=True)
    with open(os.path.join(temp_dir, "node_modules", "package", "index.js"), "w") as f:
        f.write("function ignoreMe() {}")
    with open(os.path.join(temp_dir, "server.js"), "w") as f:
        # A valid JS file with no functions/classes, just variables
        f.write("const express = require('express');\nconst app = express();\n")
    
    run_git("add", ".")
    run_git("commit", "-m", "Initial commit")
    
    yield temp_dir
    shutil.rmtree(temp_dir)

def test_regression_node_modules_and_empty_symbols(db_session, client, regression_repo):
    repo = models.Repository(name="Regression Repo", url=regression_repo)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    
    extract_git_history(regression_repo, repo.id, db_session)
    commits = db_session.query(models.Commit).filter_by(repository_id=repo.id).all()
    assert len(commits) == 1
    
    # 1. Test that node_modules was ignored
    fcs = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[0].id).all()
    file_paths = [fc.file_path for fc in fcs]
    assert "server.js" in file_paths
    assert not any("node_modules" in p for p in file_paths), "node_modules should be ignored"
    
    # 2. Test the API endpoint returns proper change_type for JS file with 0 symbols
    resp = client.get(f"/api/repositories/{repo.id}/change-map")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    files = data[0]["files"]
    
    server_js_file = next((f for f in files if f["path"] == "server.js"), None)
    assert server_js_file is not None
    
    # Should have a single fallback symbol representing the file
    assert len(server_js_file["symbols"]) == 1
    sym = server_js_file["symbols"][0]
    assert sym["name"] == "<file-level-only>"
    
    # This is the critical fix: it should be "added" (the file's change_type), NOT "unsupported"
    assert sym["change_type"] == "added"
