import os
import ast
import re
from datetime import datetime
from sqlalchemy.orm import Session
from git import Repo, InvalidGitRepositoryError

from backend.fastapi_app.models import models

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "virtualenv", "build", "dist", "assets", ".pytest_cache", ".gemini"}

def get_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        return "python"
    elif ext == ".js":
        return "javascript"
    elif ext == ".jsx":
        return "jsx" # Let's handle JSX with JS parser
    elif ext == ".ts":
        return "typescript"
    elif ext == ".tsx":
        return "tsx"
    return "unknown"

from backend.fastapi_app.services.parsers import extract_symbols, extract_dependencies

def analyze_file(file_path: str, file_model: models.File, db: Session, repo_id: int, lang: str):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return

    try:
        symbols = extract_symbols(content, lang)
        for sym_name, sym_info in symbols.items():
            sym = models.Symbol(
                file_id=file_model.id,
                name=sym_name,
                symbol_type=sym_info["type"],
                start_line=sym_info["start_line"],
                end_line=sym_info["end_line"]
            )
            db.add(sym)

        deps = extract_dependencies(content, lang)
        for dep_info in deps:
            dep = models.Dependency(
                repository_id=repo_id,
                source_file_id=file_model.id,
                dependency_type=dep_info["type"],
                target_name=dep_info["target"]
            )
            db.add(dep)
    except Exception as e:
        pass # The analyzer must never crash because one source file cannot be parsed

def run_analysis(repo_id: int, db: Session):
    run = db.query(models.AnalysisRun).filter(models.AnalysisRun.repository_id == repo_id, models.AnalysisRun.status == "pending").first()
    if not run:
        run = models.AnalysisRun(repository_id=repo_id, status="running")
        db.add(run)
        db.commit()
    else:
        run.status = "running"
        db.commit()

    repo = db.query(models.Repository).filter(models.Repository.id == repo_id).first()

    try:
        local_path = repo.url
        is_remote = repo.url.startswith("http://") or repo.url.startswith("https://")
        temp_dir = None

        if is_remote:
            import tempfile
            import shutil
            temp_dir = tempfile.mkdtemp()
            local_path = temp_dir
            try:
                git_repo = Repo.clone_from(repo.url, local_path, env={"GIT_TERMINAL_PROMPT": "0"})
            except Exception as e:
                shutil.rmtree(temp_dir)
                raise ValueError(f"Failed to clone repository: {e}")
        else:
            if not os.path.exists(local_path) or not os.path.isdir(local_path):
                raise ValueError(f"Path does not exist or is not a directory: {local_path}")

            try:
                git_repo = Repo(local_path)
            except InvalidGitRepositoryError:
                raise ValueError(f"Not a valid git repository: {local_path}")

        existing_files = {f.path: f for f in db.query(models.File).filter_by(repository_id=repo_id).all()}

        for root, dirs, files in os.walk(local_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            for file_name in files:
                file_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(file_path, local_path)

                lang = get_language(file_path)

                try:
                    size = os.path.getsize(file_path)
                except OSError:
                    continue

                f_model = existing_files.get(rel_path)
                if f_model:
                    f_model.language = lang
                    f_model.size = size
                else:
                    f_model = models.File(
                        repository_id=repo_id,
                        path=rel_path,
                        language=lang,
                        size=size
                    )
                    db.add(f_model)
                    db.flush()
                    existing_files[rel_path] = f_model

                if lang in ("python", "javascript", "typescript", "tsx", "jsx"):
                    # Wipe dependencies for this file (dependencies table has no external FKs targeting it)
                    db.query(models.Dependency).filter_by(source_file_id=f_model.id).delete(synchronize_session=False)

                    # Update or add symbols without deleting ones referenced by commit_symbol_changes
                    existing_syms = {s.name: s for s in db.query(models.Symbol).filter_by(file_id=f_model.id).all()}
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        new_symbols = extract_symbols(content, lang)
                        for sym_name, sym_info in new_symbols.items():
                            if sym_name in existing_syms:
                                s = existing_syms[sym_name]
                                s.symbol_type = sym_info["type"]
                                s.start_line = sym_info["start_line"]
                                s.end_line = sym_info["end_line"]
                            else:
                                sym = models.Symbol(
                                    file_id=f_model.id,
                                    name=sym_name,
                                    symbol_type=sym_info["type"],
                                    start_line=sym_info["start_line"],
                                    end_line=sym_info["end_line"]
                                )
                                db.add(sym)

                        deps = extract_dependencies(content, lang)
                        for dep_info in deps:
                            dep = models.Dependency(
                                repository_id=repo_id,
                                source_file_id=f_model.id,
                                dependency_type=dep_info["type"],
                                target_name=dep_info["target"]
                            )
                            db.add(dep)
                    except Exception:
                        pass

        # Extract git history
        from backend.fastapi_app.services.git_history_service import extract_git_history
        extract_git_history(local_path, repo_id, db)

        # Build repository graph edges
        from backend.fastapi_app.services.graph_service import build_repository_graph
        build_repository_graph(repo_id, db)

        if temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.utcnow()
        db.commit()

