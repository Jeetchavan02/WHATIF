import pytest
import os
import shutil
import tempfile
import subprocess
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.fastapi_app.models.base import Base
from backend.fastapi_app.models import models
from backend.fastapi_app.services.git_history_service import extract_git_history

@pytest.fixture(scope="module")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture(scope="module")
def repo_fixture():
    temp_dir = tempfile.mkdtemp()
    
    def run_git(*args):
        subprocess.run(["git", *args], cwd=temp_dir, check=True, capture_output=True)

    # Initialize repo
    run_git("init")
    run_git("config", "user.name", "Test User")
    run_git("config", "user.email", "test@example.com")
    
    # Commit 1: add file
    with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
        f.write("Line 1\n")
    run_git("add", "file1.txt")
    run_git("commit", "-m", "Commit 1")
    
    # Commit 2: modify file
    with open(os.path.join(temp_dir, "file1.txt"), "a") as f:
        f.write("Line 2\n")
    run_git("add", "file1.txt")
    run_git("commit", "-m", "Commit 2")
    
    # Commit 3: add another file
    with open(os.path.join(temp_dir, "file2.txt"), "w") as f:
        f.write("A new file\n")
    run_git("add", "file2.txt")
    run_git("commit", "-m", "Commit 3")
    
    # Commit 4: delete a file
    run_git("rm", "file2.txt")
    run_git("commit", "-m", "Commit 4")
    
    # Commit 5: rename a file
    run_git("mv", "file1.txt", "file1_renamed.txt")
    run_git("commit", "-m", "Commit 5")
    
    # Commit 6: modify multiple files
    with open(os.path.join(temp_dir, "file1_renamed.txt"), "a") as f:
        f.write("Line 3\n")
    with open(os.path.join(temp_dir, "file3.txt"), "w") as f:
        f.write("File 3\n")
    run_git("add", "file1_renamed.txt", "file3.txt")
    run_git("commit", "-m", "Commit 6")

    yield temp_dir
    
    shutil.rmtree(temp_dir)

def test_git_history_extraction(db_session, repo_fixture):
    # Setup repo model
    repo = models.Repository(name="Test Repo", url=repo_fixture)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    
    # Run service
    extract_git_history(repo_fixture, repo.id, db_session)
    
    commits = db_session.query(models.Commit).filter_by(repository_id=repo.id).order_by(models.Commit.id.desc()).all()
    
    assert len(commits) == 6
    
    # Commit 1
    c1_changes = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[0].id).all()
    assert len(c1_changes) == 1
    assert c1_changes[0].change_type == "added"
    assert c1_changes[0].file_path == "file1.txt"
    assert c1_changes[0].additions == 1
    
    # Commit 2
    c2_changes = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[1].id).all()
    assert len(c2_changes) == 1
    assert c2_changes[0].change_type == "modified"
    assert c2_changes[0].file_path == "file1.txt"
    assert c2_changes[0].additions == 1
    
    # Commit 3
    c3_changes = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[2].id).all()
    assert len(c3_changes) == 1
    assert c3_changes[0].change_type == "added"
    
    # Commit 4
    c4_changes = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[3].id).all()
    assert len(c4_changes) == 1
    assert c4_changes[0].change_type == "deleted"
    
    # Commit 5
    c5_changes = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[4].id).all()
    assert len(c5_changes) == 1
    assert c5_changes[0].change_type == "renamed"
    assert c5_changes[0].old_path == "file1.txt"
    assert c5_changes[0].new_path == "file1_renamed.txt"
    
    # Commit 6
    c6_changes = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[5].id).all()
    assert len(c6_changes) == 2
    
def test_git_history_idempotency(db_session, repo_fixture):
    repo = db_session.query(models.Repository).first()
    
    # Run service again
    extract_git_history(repo_fixture, repo.id, db_session)
    
    commits = db_session.query(models.Commit).filter_by(repository_id=repo.id).all()
    # Count should still be 6
    assert len(commits) == 6
