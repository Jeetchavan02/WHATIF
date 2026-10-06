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

    run_git("init", "-b", "main")
    run_git("config", "user.name", "Test User")
    run_git("config", "user.email", "test@example.com")
    
    # Commit 1: Add JS/TS files
    with open(os.path.join(temp_dir, "app.js"), "w") as f:
        f.write("class App { start() { return 1; } } function main() {}\n")
    with open(os.path.join(temp_dir, "types.ts"), "w") as f:
        f.write("interface User { id: string; }\ntype Role = string;\n")
    with open(os.path.join(temp_dir, "Comp.tsx"), "w") as f:
        f.write("import React from 'react';\nexport function Comp() { return <div></div>; }\n")
    with open(os.path.join(temp_dir, "View.jsx"), "w") as f:
        f.write("export default function View() { return <div/>; }\n")
    run_git("add", ".")
    run_git("commit", "-m", "Commit 1: Add symbols")
    
    # Commit 2: Modify symbols
    with open(os.path.join(temp_dir, "app.js"), "w") as f:
        f.write("class App { start() { return 2; } } function main() {}\n")
    run_git("add", ".")
    run_git("commit", "-m", "Commit 2: Modify symbol")
    
    # Commit 3: Delete symbols
    with open(os.path.join(temp_dir, "types.ts"), "w") as f:
        f.write("type Role = string;\n")
    run_git("add", ".")
    run_git("commit", "-m", "Commit 3: Delete interface")
    
    # Commit 4: Add imports
    with open(os.path.join(temp_dir, "app.js"), "w") as f:
        f.write("import { run } from './runner';\nclass App { start() { return 2; } } function main() {}\n")
    run_git("add", ".")
    run_git("commit", "-m", "Commit 4: Add import")

    # Commit 5: Modify multiple
    with open(os.path.join(temp_dir, "Comp.tsx"), "w") as f:
        f.write("import React from 'react';\nexport function Comp() { return <span>hello</span>; }\nfunction Helper() {}\n")
    run_git("add", ".")
    run_git("commit", "-m", "Commit 5: Modify Comp and add Helper")

    yield temp_dir
    shutil.rmtree(temp_dir)

def test_multi_lang_history(db_session, repo_fixture):
    repo = models.Repository(name="Multi Lang Repo", url=repo_fixture)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    
    extract_git_history(repo_fixture, repo.id, db_session)
    commits = db_session.query(models.Commit).filter_by(repository_id=repo.id).order_by(models.Commit.id.desc()).all()
    assert len(commits) == 5
    
    def get_symbol(c_idx, path, name):
        fc = db_session.query(models.CommitFileChange).filter_by(commit_id=commits[c_idx].id, file_path=path).first()
        if not fc: return None
        for sc in fc.symbol_changes:
            if sc.symbol_name == name:
                return sc
        return None

    for i, c in enumerate(commits):
        print(f"Commit {i}: {c.id}")
        for fc in c.file_changes:
            print(f"  File: {fc.file_path}")
            for sc in fc.symbol_changes:
                print(f"    Sym: {sc.symbol_name} ({sc.change_type})")

    # Commit 1
    assert get_symbol(0, "app.js", "App").change_type == "added"
    assert get_symbol(0, "app.js", "main").change_type == "added"
    assert get_symbol(0, "types.ts", "User").change_type == "added"
    assert get_symbol(0, "Comp.tsx", "Comp").change_type == "added"
    assert get_symbol(0, "View.jsx", "View").change_type == "added"

    # Commit 2: Modify App.start in app.js
    assert get_symbol(1, "app.js", "App.start").change_type == "modified"
    assert get_symbol(1, "app.js", "main").change_type == "unchanged"

    # Commit 3: Delete User in types.ts
    assert get_symbol(2, "types.ts", "User").change_type == "deleted"
    assert get_symbol(2, "types.ts", "Role").change_type == "unchanged"

    # Commit 4: Add import in app.js - this won't show in symbol changes as import isn't a tracked symbol
    # But we can verify it doesn't crash
    assert get_symbol(3, "app.js", "App").change_type == "unchanged"

    # Commit 5: Modify Comp and add Helper
    assert get_symbol(4, "Comp.tsx", "Comp").change_type == "modified"
    assert get_symbol(4, "Comp.tsx", "Helper").change_type == "added"
