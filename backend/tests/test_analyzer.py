import os
import pytest
from backend.fastapi_app.core.analyzer import get_language, IGNORED_DIRS

def test_get_language():
    assert get_language("test.py") == "python"
    assert get_language("app.js") == "javascript"
    assert get_language("components.tsx") == "tsx"
    assert get_language("unknown.txt") == "unknown"

def test_ignored_dirs():
    assert ".git" in IGNORED_DIRS
    assert "node_modules" in IGNORED_DIRS
    assert "__pycache__" in IGNORED_DIRS

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.fastapi_app.models import models
from backend.fastapi_app.core.analyzer import run_analysis
import subprocess

def test_idempotency(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    f1 = repo_dir / "main.py"
    f1.write_text("def test():\n    pass")

    subprocess.run(["git", "init"], cwd=repo_dir, check=True)

    repo = models.Repository(name="test_repo", url=str(repo_dir))
    db.add(repo)
    db.commit()

    # Run analysis 1
    run_analysis(repo.id, db)
    db.commit()

    files_1 = db.query(models.File).all()
    assert len(files_1) == 1

    syms_1 = db.query(models.Symbol).all()
    assert len(syms_1) > 0

    # Run analysis 2
    run_analysis(repo.id, db)
    db.commit()

    files_2 = db.query(models.File).all()
    assert len(files_2) == 1
    assert files_2[0].id == files_1[0].id

    syms_2 = db.query(models.Symbol).all()
    assert len(syms_2) == len(syms_1)

    db.close()
