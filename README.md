# WHATIF - Software Change Impact Analyzer

WHATIF is a research-oriented software engineering project aimed at analyzing software change impacts.
This V1 foundation provides:
1. Accept a Git repository
2. Analyze its structure (Python/JS)
3. Extract files, functions/classes, imports
4. Store in PostgreSQL
5. Expose via FastAPI
6. Manage via Django Admin

## Architecture

- **FastAPI** (`backend/fastapi_app/`): Handles API requests and runs background repository analysis.
- **Django** (`backend/django_app/`): Provides an admin interface connected to the same PostgreSQL database.
- **Frontend** (`frontend/`): Basic HTML/JS test interface.
- **Database**: PostgreSQL with SQLAlchemy/Alembic managing migrations.

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Start PostgreSQL using Docker Compose:
   ```bash
   docker-compose up -d
   ```

3. Setup Python Virtual Environment & Install Dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Database Migrations

Apply Alembic migrations to setup the schema:
```bash
export PYTHONPATH=$PWD
alembic upgrade head
```

## Running the Applications

### FastAPI
```bash
export PYTHONPATH=$PWD
uvicorn backend.fastapi_app.main:app --reload
```

### Django Admin
```bash
cd backend/django_app
python manage.py createsuperuser
python manage.py runserver 8080
```

### Frontend UI
Open `frontend/index.html` in your browser.

## Tests
```bash
export PYTHONPATH=$PWD
pytest backend/tests/
```

## Known Limitations
- Analysis is currently limited to basic Python AST extraction and simple Regex for JS.
- External dependencies and cross-module resolution are not perfect.
- If a file fails to parse, it silently skips to prevent crashes.

## Suggested Next Milestone
Enhance parsing for javascript/typescript to properly build the dependency graph using an AST parser (like esprima or babel).

## Milestone 2: Git History & Change Tracking
WHATIF now extracts and stores the historical evolution of a repository. This Git history is currently being collected as evidence for future impact analysis. It tracks commits, file changes (additions, modifications, deletions, renames), and their respective diffs.

### Database Additions
- **Commit**: Stores commit metadata (hash, author, date, message, parent).
- **CommitFileChange**: Stores individual file modifications for each commit (change type, additions, deletions, old/new paths).

### New API Endpoints
- `GET /api/repositories/{id}/commits` - Paginated commit history with date and author filtering.
- `GET /api/commits/{commit_id}` - Detailed metadata and file changes for a specific commit.
- `GET /api/repositories/{id}/commits/{hash}` - Retrieve a commit by its hash.
- `GET /api/repositories/{id}/history/stats` - Aggregated stats (total commits, additions, deletions, etc.).

### Testing
We use a dedicated temporary Git repository fixture using `pytest` to simulate a real git environment.
To run the git history tests:
```bash
export PYTHONPATH=$PWD
pytest backend/tests/test_git_history.py
```

### Known Limitations
- Git history collection can be slow for extremely large repositories since it parses every patch to count line-level additions and deletions.
- Idempotency logic only checks if a commit hash exists; it does not currently resume an interrupted analysis midway cleanly without rescanning if the previous scan crashed mid-commit.
