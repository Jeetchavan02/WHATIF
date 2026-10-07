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

## Milestone 3: Symbol-Level Change Analysis
WHATIF connects Git history to code semantics. It currently performs structural change analysis for Python files using Abstract Syntax Trees (AST). **It does not yet predict impact.**

### Symbol Tracking (Python)
For every commit that modifies a `.py` file, WHATIF compares the parent file and the new file:
- **Added**: Symbol exists after but not before.
- **Deleted**: Symbol exists before but not after.
- **Modified**: Symbol exists in both, but the normalized AST body `ast.dump()` differs.
- **Unchanged**: Symbol exists in both and `ast.dump()` matches.

For non-Python files, symbol-level analysis is marked as `unsupported`.

### Historical Symbol Tracking
Symbols are tracked historically with exact line numbers (`old_start_line`, `new_start_line`, etc.) to map out precisely where an implementation shifted over time. Methods are appropriately namespaced to their classes (e.g. `User.authenticate`).

### New API Endpoints
- `GET /api/commits/{id}/changes` - Retrieve hierarchical changes (Commit -> Files -> Symbols) with line numbers.
- `GET /api/repositories/{id}/symbols/{symbol_id}/history` - View the commit history where a specific symbol was added, modified, or deleted.
- `GET /api/repositories/{id}/change-map` - A structured output of historical dependencies across the entire repository.

### Testing
We simulate Python file modifications (adding methods, modifying methods, deleting methods) dynamically via a temporary Git repository fixture using `pytest`.
```bash
export PYTHONPATH=$PWD
pytest backend/tests/test_git_history_symbols.py
```

### Known Limitations
- WHATIF identifies symbol identity strictly by `file_path + type + name`. It does not yet perform sophisticated rename tracking.
- Only Python is officially supported for deep AST symbol-level structural analysis at this stage. Other languages will only report file-level differences.
- Dependency linking is currently file-level and mapped indirectly to the symbol. Direct symbol-to-symbol relationships are a future milestone.

## M10 — Batch Research Benchmarking

M10 extends the single-commit evaluation introduced in M9 into a deterministic batch benchmark.

### Workflow

```text
Historical Commits
        ↓
Deterministic Source Selection
        ↓
┌──────────────┬──────────────┬──────────────┐
│ Structural   │ Historical   │ Combined     │
│ Impact       │ Impact       │ WHATIF       │
└──────────────┴──────────────┴──────────────┘
        ↓
Actual Historical Changes
        ↓
TP / FP / FN
        ↓
Precision / Recall / F1
        ↓
Aggregate Benchmark Results
```

### 1. Why M10 Exists

M9 evaluates a single historical commit. M10 asks whether the behavior generalizes across multiple historical commits. The benchmark allows comparison of:
- structural dependency evidence
- historical co-change evidence
- combined WHATIF evidence

The goal is not to optimize for a particular score. The goal is to measure the behavior of each approach honestly.

### 2. Three Methods

| Method | Evidence | Description |
|---|---|---|
| Structural | Dependency graph | Uses deterministic reverse dependency traversal |
| Historical | Git co-change history | Uses historical files that changed alongside the source |
| Combined | Structural + historical | Uses the existing WHATIF hypothetical-change analysis |

- **STRUCTURAL** uses the M6 impact propagation service to calculate structural impact.
- **HISTORICAL** uses the M7 historical co-change service to retrieve a historical candidate impact set.
- **COMBINED** uses the M8 hypothetical change analysis to generate a combined calculated impact set.

### 3. Benchmark Dataset

Commits are selected deterministically, ordered by `committed_at` and `commit ID`. Commits must contain multiple changed files, and source files must be supported source-code files.

Supported source extensions currently include:
- `.py`
- `.js`
- `.jsx`
- `.ts`
- `.tsx`

Non-source files such as `.env`, `.gitignore`, `README.md` and package metadata are not selected as source components. Source selection is deterministic, and commits without eligible source files are skipped.

### 4. Ground Truth

Ground truth comes directly from Git history. For an evaluation case:

Actual Impact Set = files that actually changed in the historical commit, excluding the selected source file.

M7 is an input/evidence source for the Historical and Combined methods, while the actual commit changes provide the evaluation ground truth.

### 5. Metrics

- **True Positive (TP):** A file calculated as impacted that actually changed.
- **False Positive (FP):** A file calculated as impacted that did not actually change.
- **False Negative (FN):** A file that actually changed but was not included in the calculated impact set.

- **Precision** = TP / (TP + FP)
- **Recall** = TP / (TP + FN)
- **F1** = 2 × Precision × Recall / (Precision + Recall)

Zero-denominator cases are handled deterministically by returning 0.0 according to the implementation.

### 6. Aggregation

M10 reports macro-averages across benchmark cases:
- mean precision, median precision, minimum precision, maximum precision
- mean recall, median recall, minimum recall, maximum recall
- mean F1, median F1, minimum F1, maximum F1

The primary aggregate is the macro-average because a large commit should not dominate the benchmark simply because it contains more changed files.

### 7. API

`POST /api/repositories/{repository_id}/benchmark`

Example request:
```json
{
  "limit": 10,
  "max_depth": 5,
  "historical_limit": 50
}
```

Parameters:
- `limit`: maximum number of eligible benchmark cases.
- `max_depth`: maximum structural dependency traversal depth.
- `historical_limit`: maximum number of historical co-change candidates considered.

### 8. Response

The endpoint returns:
- `repository_id`
- benchmark parameters
- `case_count`
- structural aggregate metrics
- historical aggregate metrics
- combined aggregate metrics
- individual benchmark `cases`

Each benchmark case includes:
- commit ID
- commit hash
- source file ID
- source file path
- actual impact count
- structural metrics
- historical metrics
- combined metrics

### 9. Reproducibility

Benchmark selection is deterministic. Given identical repository, `limit`, `max_depth`, `historical_limit`, and repository analysis state, the benchmark produces the same evaluation cases and ordering. No random sampling is used.

### Example Benchmark Run

```text
Repository: AutoFair
Repository ID: 11
Limit: 10
Max Depth: 5
Historical Limit: 50
Eligible Cases: 7
```
