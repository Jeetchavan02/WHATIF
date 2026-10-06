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
    
    # Commit 1
    with open(os.path.join(temp_dir, "user.py"), "w") as f:
        f.write("class User:\n    def validate(self):\n        pass\n")
    with open(os.path.join(temp_dir, "readme.txt"), "w") as f:
        f.write("test file")
    run_git("add", ".")
    run_git("commit", "-m", "Commit 1")
    
    # Commit 2
    with open(os.path.join(temp_dir, "user.py"), "w") as f:
        f.write("class User:\n    def validate(self):\n        return True\n")
    run_git("add", "user.py")
    run_git("commit", "-m", "Commit 2")
    
    # Commit 3
    with open(os.path.join(temp_dir, "user.py"), "w") as f:
        f.write("class User:\n    def validate(self):\n        return True\n    def authenticate(self):\n        pass\n")
    run_git("add", "user.py")
    run_git("commit", "-m", "Commit 3")
    
    # Commit 4
    with open(os.path.join(temp_dir, "user.py"), "w") as f:
        f.write("class User:\n    def validate(self):\n        return True\n    def authenticate(self):\n        return True\n")
    run_git("add", "user.py")
    run_git("commit", "-m", "Commit 4")
    
    # Commit 5
    with open(os.path.join(temp_dir, "user.py"), "w") as f:
        f.write("class User:\n    def authenticate(self):\n        return True\n")
    run_git("add", "user.py")
    run_git("commit", "-m", "Commit 5")
    
    # Commit 6
    with open(os.path.join(temp_dir, "user.py"), "w") as f:
        f.write("class User:\n    def authenticate(self):\n        return False\n    def new_method(self):\n        pass\n")
    run_git("add", "user.py")
    run_git("commit", "-m", "Commit 6")

    yield temp_dir
    shutil.rmtree(temp_dir)

def test_symbol_extraction(db_session, repo_fixture):
    repo = models.Repository(name="Test Repo Symbols", url=repo_fixture)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    
    extract_git_history(repo_fixture, repo.id, db_session)
    
    commits = db_session.query(models.Commit).filter_by(repository_id=repo.id).order_by(models.Commit.id.desc()).all()
    assert len(commits) == 6
    
    def get_symbol(c_idx, name):
        fc = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[c_idx].id, file_path="user.py").first()
        for sc in fc.symbol_changes:
            if sc.symbol_name == name:
                return sc
        return None

    # Commit 1
    u1 = get_symbol(0, "User")
    assert u1.change_type == "added"
    v1 = get_symbol(0, "User.validate")
    assert v1.change_type == "added"
    
    fc_txt = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[0].id, file_path="readme.txt").first()
    assert fc_txt.symbol_changes[0].change_type == "unsupported"

    # Commit 2 (Modify validate)
    v2 = get_symbol(1, "User.validate")
    assert v2.change_type == "modified"
    u2 = get_symbol(1, "User")
    assert u2.change_type == "modified"

    # Commit 3 (Add authenticate)
    a3 = get_symbol(2, "User.authenticate")
    assert a3.change_type == "added"
    v3 = get_symbol(2, "User.validate")
    assert v3.change_type == "unchanged"

    # Commit 4 (Modify authenticate)
    a4 = get_symbol(3, "User.authenticate")
    assert a4.change_type == "modified"

    # Commit 5 (Delete validate)
    v5 = get_symbol(4, "User.validate")
    assert v5.change_type == "deleted"

    # Commit 6 (Modify multiple)
    a6 = get_symbol(5, "User.authenticate")
    assert a6.change_type == "modified"
    n6 = get_symbol(5, "User.new_method")
    assert n6.change_type == "added"
