import os
import ast
import re
from datetime import datetime
from sqlalchemy.orm import Session
from git import Repo, InvalidGitRepositoryError

from backend.fastapi_app.models import models

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "virtualenv", "build", "dist"}

def get_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        return "python"
    elif ext in {".js", ".jsx", ".ts", ".tsx"}:
        return "javascript"
    return "unknown"

def analyze_python_file(file_path: str, file_model: models.File, db: Session, repo_id: int):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                sym = models.Symbol(
                    file_id=file_model.id,
                    name=node.name,
                    symbol_type="function",
                    start_line=node.lineno,
                    end_line=node.end_lineno
                )
                db.add(sym)
            elif isinstance(node, ast.ClassDef):
                sym = models.Symbol(
                    file_id=file_model.id,
                    name=node.name,
                    symbol_type="class",
                    start_line=node.lineno,
                    end_line=node.end_lineno
                )
                db.add(sym)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    dep = models.Dependency(
                        repository_id=repo_id,
                        source_file_id=file_model.id,
                        dependency_type="import",
                        target_name=alias.name
                    )
                    db.add(dep)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    dep = models.Dependency(
                        repository_id=repo_id,
                        source_file_id=file_model.id,
                        dependency_type="import_from",
                        target_name=f"{module}.{alias.name}"
                    )
                    db.add(dep)
    except Exception as e:
        pass # The analyzer must never crash because one source file cannot be parsed

def analyze_js_file(file_path: str, file_model: models.File, db: Session, repo_id: int):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Very basic regex for imports
        import_regex = re.compile(r'import\s+.*?\s+from\s+[\'"](.*?)[\'"]')
        for match in import_regex.finditer(content):
            dep = models.Dependency(
                repository_id=repo_id,
                source_file_id=file_model.id,
                dependency_type="import",
                target_name=match.group(1)
            )
            db.add(dep)
    except Exception:
        pass


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
                git_repo = Repo.clone_from(repo.url, local_path)
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

                f_model = models.File(
                    repository_id=repo_id,
                    path=rel_path,
                    language=lang,
                    size=size
                )
                db.add(f_model)
                db.flush() # to get id

                if lang == "python":
                    analyze_python_file(file_path, f_model, db, repo_id)
                elif lang == "javascript":
                    analyze_js_file(file_path, f_model, db, repo_id)
        
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

