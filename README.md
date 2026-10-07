<div align="center">

# WHATIF — Software Change Impact Analyzer

### *Analyze code. Understand dependencies. Predict impact honestly.*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Django](https://img.shields.io/badge/Django-5.1-092E20?style=flat-square&logo=django)](https://www.djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-316192?style=flat-square&logo=postgresql)](https://postgresql.org)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?style=flat-square&logo=typescript)](https://typescriptlang.org)
[![React](https://img.shields.io/badge/React-18-20232a?style=flat-square&logo=react)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

> **WHATIF** is a research-oriented software engineering platform designed to understand the true impact of software changes. It combines structural codebase analysis with historical Git evolution to provide deterministic, quantitative predictions about what components will be affected when a specific file or symbol changes.

</div>

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🏗️ Tech Stack](#️-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🚀 Getting Started](#-getting-started)
- [⚙️ Environment Variables](#️-environment-variables)
- [📡 API Reference](#-api-reference)
- [🗃️ Database Models](#️-database-models)
- [📈 Milestones & Evaluation](#-milestones--evaluation)
- [🧪 Testing](#-testing)
- [🛡️ Known Limitations](#️-known-limitations)
- [🤝 Contributing](#-contributing)

---

## ✨ Features

### 🔍 Analysis Core
| Feature | Description |
|---|---|
| 🌳 **Structural Extraction** | Parses Python (AST) and JS/TS to extract functions, classes, and cross-file dependencies. |
| 🕰️ **Git History Tracking** | Reconstructs repository history, tracking every commit, file change, and diff. |
| 🎯 **Symbol Evolution** | Traces exact Python AST symbols (e.g., specific methods) as they are added, modified, or deleted across commits. |

### 🧠 Impact Intelligence
| Feature | Description |
|---|---|
| 🌐 **Impact Propagation** | Deterministically traverses the dependency graph (M6) to find structurally impacted components. |
| 📊 **Historical Co-change** | Identifies files that have historically changed alongside the target component (M7). |
| ⚡ **Hypothetical What-If** | Combines structural and historical evidence to produce a comprehensive predicted impact set (M8). |

### 🔬 Benchmarking & Research
| Feature | Description |
|---|---|
| 📈 **Batch Research Benchmark** | Evaluates impact prediction accuracy across large sets of historical commits using precision/recall/F1 metrics (M10). |
| 🖥️ **Admin Interface** | Django-powered dashboard for managing analyzed repositories, symbols, and graphs. |

---

## 🏗️ Tech Stack

### Backend & Analysis
| Technology | Purpose |
|---|---|
| **Python 3.12** | Core language for analysis and API |
| **FastAPI** | High-performance REST API |
| **Django** | Admin interface and ORM modeling |
| **PostgreSQL** | Relational data storage |
| **SQLAlchemy** | Database ORM and query building |
| **Alembic** | Database migrations |
| **Pytest** | Testing framework |
| **GitPython** | Git repository interaction and diff extraction |
| **ast** | Python built-in AST parsing |

### Frontend (Test Interface)
| Technology | Purpose |
|---|---|
| **HTML/JS** | Basic test UI |
| **React/TS** | (Planned) Full interactive impact dashboard |

---

## 📁 Project Structure

```text
WHATIF/
├── 📂 backend/
│   ├── 📂 fastapi_app/
│   │   ├── 📂 api/            # API endpoints (commits, repositories, benchmark)
│   │   ├── 📂 core/           # Config, database setup, dependencies
│   │   ├── 📂 models/         # SQLAlchemy models (Commit, File, Symbol)
│   │   ├── 📂 schemas/        # Pydantic validation schemas
│   │   ├── 📂 services/       # Core logic (impact, history, benchmark)
│   │   └── main.py            # FastAPI entry point
│   ├── 📂 django_app/         # Django admin interface
│   └── 📂 tests/              # Pytest suites
├── 📂 frontend/               # Basic UI interface
├── 📂 scripts/                # Helper tools
├── .env.example
├── alembic.ini
├── docker-compose.yml         # PostgreSQL setup
├── requirements.txt
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- **Python** ≥ 3.10
- **Docker & Docker Compose** (for PostgreSQL)

### 1. Clone the Repository
```bash
git clone https://github.com/Jeetchavan02/WHATIF.git
cd WHATIF
```

### 2. Environment Setup
```bash
cp .env.example .env
# Edit .env with your specific configuration if necessary
```

### 3. Start Database
```bash
docker-compose up -d
```

### 4. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Run Migrations
```bash
export PYTHONPATH=$PWD
alembic upgrade head
```

### 6. Start Applications
**Start FastAPI (API Server):**
```bash
export PYTHONPATH=$PWD
uvicorn backend.fastapi_app.main:app --reload
# → API running at http://localhost:8000
```

**Start Django (Admin Panel):**
```bash
cd backend/django_app
python manage.py createsuperuser
python manage.py runserver 8080
# → Admin running at http://localhost:8080
```

---

## ⚙️ Environment Variables

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/whatif

# Application
DEBUG=True
SECRET_KEY=your_secret_key_here
```

---

## 📡 API Reference

### 📁 Repositories & Commits
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/repositories` | Add and analyze a new Git repository |
| `GET`  | `/api/repositories/{id}/commits` | Paginated commit history |
| `GET`  | `/api/commits/{id}` | Detailed commit info & file changes |
| `GET`  | `/api/commits/{id}/changes` | Hierarchical symbol-level changes |

### 🎯 Analysis & Impact
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/repositories/{id}/change-map` | Structured graph of repository dependencies |
| `GET` | `/api/repositories/{id}/symbols/{id}/history` | Historical changes for a specific symbol |

### 🔬 Benchmarking
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/repositories/{id}/benchmark` | Run batch research benchmark (M10) |

---

## 🗃️ Database Models

### `Repository`
Stores tracked Git repositories.
```text
id, name, url, path, created_at
```

### `File` & `Symbol`
Represents the structural components of a repository.
```text
File: id, repository_id, path
Symbol: id, file_id, name, type (function, class), ast_dump
```

### `Commit` & `CommitFileChange`
Stores the evolution history.
```text
Commit: id, hash, author, message, committed_at
CommitFileChange: commit_id, file_path, change_type, additions, deletions
```

### `GraphEdge`
Represents structural dependencies (imports, function calls).
```text
source_id, target_id, edge_type, weight
```

---

## 📈 Milestones & Evaluation

WHATIF has evolved through 10 major milestones, culminating in **M10: Batch Research Benchmarking**.

### Workflow: `CODE → STRUCTURE → HISTORY → EVALUATE`

```mermaid
flowchart LR
    A([Git Commit]) --> B[Source Selection]
    B --> C[Structural Impact]
    B --> D[Historical Impact]
    C & D --> E[Combined Impact]
    E --> F([Benchmark Metrics])
```

### Batch Research Benchmarking (M10)

M10 deterministically selects valid historical commits and evaluates 3 impact prediction methods against the **actual ground truth** (files that actually changed in that commit).

| Method | Evidence | Description |
|---|---|---|
| **Structural** | Dependency graph | Uses deterministic reverse dependency traversal |
| **Historical** | Git co-change | Uses files that have historically changed alongside the source |
| **Combined** | Structural + Historical | The WHATIF hypothetical-change analysis combining both |

**Metrics Calculated:**
- **True Positive (TP):** Calculated impact that actually changed.
- **False Positive (FP):** Calculated impact that did NOT actually change.
- **False Negative (FN):** Actually changed, but NOT in calculated impact.
- **Precision, Recall, F1** (Macro-averaged across all eligible cases).

---

## 🧪 Testing

Run the full pytest suite (including dynamic Git repository simulation fixtures):

```bash
export PYTHONPATH=$PWD
pytest -q
```

*Note: Tests verify deterministic metric calculations, AST parsing, API endpoints, and idempotency.*

---

## 🛡️ Known Limitations

- **AST Parsing:** Currently limited to basic Python AST extraction and simple Regex for JS. Other languages only report file-level differences.
- **Rename Tracking:** Identifies symbol identity strictly by `file_path + type + name`. Sophisticated file/symbol rename tracking is pending.
- **Performance:** Git history collection can be slow for extremely large repositories as it parses every patch for line-level counts.
- **Temporal Graph Evaluation:** M10 currently evaluates historical commits using the latest dependency graph state. Full graph time-travel reconstruction is a future milestone.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/impact-scoring`)
3. Commit your changes (`git commit -m 'feat: improve impact scoring'`)
4. Push to the branch (`git push origin feature/impact-scoring`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License**. See `LICENSE` for details.

---

<div align="center">
  <p>◼ <strong>WHATIF</strong></p>
  <p><em>Predicting the butterfly effect in software engineering.</em></p>
</div>
