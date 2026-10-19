<div align="center">

# WHAT IF...?
### *Software Change Impact Analyzer // Causal Multiverse*

*Time. Space. Software. It's more than a linear path — it's a prism of endless possibilities where a single change can branch into infinite unseen consequences.*

<br/>

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge)](LICENSE)

<br/>

> **WHAT IF...?** is a software engineering impact intelligence platform. Before you merge a pull request or modify a critical file, WHAT IF...? traverses your codebase's Abstract Syntax Tree (AST) and historical Git evolution to compute the deterministic downstream blast radius, estimate risk scores, and surface the most qualified code reviewers.

</div>

---

## 📋 Table of Contents

- [🌌 Core Pillars](#-core-pillars)
- [🏗️ Architectural Architecture](#️-architectural-architecture)
- [⚡ Quick Start](#-quick-start)
- [🔮 WHAT IF Oracle (CI/CD API)](#-what-if-oracle-cicd-api)
- [💥 Blast Radius Simulator](#-blast-radius-simulator)
- [🪐 Multiverse Graph Visualizer](#-multiverse-graph-visualizer)
- [📡 Complete API Reference](#-complete-api-reference)
- [⚙️ Configuration](#️-configuration)
- [🧪 Testing](#-testing)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## 🌌 Core Pillars

### 1. 🌳 Deep AST Structural Dependency Analysis
- **Python Native AST (`ast.parse`)**: Recursively walks Python syntax trees to extract classes, functions, asynchronous definitions, and imports (`Import`, `ImportFrom`).
- **Tree-sitter Integration**: Supports JavaScript and TypeScript grammars for cross-file dependency mapping.
- **Hierarchical Dotted Import Resolution**: Resolves dotted imports (e.g. `fastapi.routing.APIRouter` or `requests.sessions.Session`) directly to their defining origin source files.

### 2. 🕰️ Temporal Git History & Co-Change Coupling
- Direct integration with `GitPython` across commit trees.
- Extracts author telemetry, change frequencies, insertions, deletions, and commit classifications.
- **Co-Evolution Coupling**: Identifies files that statistically change together across commits, revealing hidden coupling that static AST analysis cannot detect.

### 3. 💥 Causal Blast Radius Simulator
- Computes multi-hop propagation using reverse-adjacency Breadth-First Search (BFS) DAG traversal.
- Tri-color classification:
  - **Structural Inevitability (Cyan)**: Downstream modules that directly or transitively import the target file.
  - **Historical Resonance (Purple)**: Files that frequently co-commit alongside the target.
  - **The Singularity (White)**: The collision nexus where code structure and historical developer behavior overlap.

### 4. 🔮 WHAT IF Oracle (CI/CD Intelligence API)
- Answers: *"What if I change this file?"*
- Computes a quantitative risk score (0–100) and risk tier (`NONE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- Applies change multipliers: `delete` (1.4×), `rename` (1.25×), `modify` (1.0×), `add_dependency` (0.85×).
- Analyzes commit history to surface top historical contributors as recommended PR reviewers.
- Outputs copy-pasteable `cURL` snippets and GitHub Actions-ready JSON payloads.

---

## 🏗️ Architectural Architecture

```text
WHAT IF...?/
├── 📂 backend/
│   ├── 📂 fastapi_app/
│   │   ├── 📂 api/                # REST router endpoints (repositories, oracle, graph, commits)
│   │   ├── 📂 core/               # Analyzer engine, AST extractors, DB session setup
│   │   ├── 📂 models/             # SQLAlchemy ORM models (Repository, File, Commit, GraphEdge)
│   │   ├── 📂 schemas/            # Pydantic validation schemas
│   │   └── 📂 services/           # Oracle risk intelligence, Git history, Graph builder, BFS impact
│   ├── 📂 django_app/             # Django administration suite
│   └── 📂 tests/                  # Pytest test suite with dynamic repository simulation
├── 📂 frontend/                   # Cinematic sci-fi command HUD
│   ├── index.html                 # Single-page interface with canvas & Oracle decks
│   ├── app.js                     # Force simulation, Pan/Zoom, Matrix/Orbital tabs, API client
│   └── styles.css                 # Cyberpunk glassmorphism, responsive HUD styling
├── docker-compose.yml             # PostgreSQL container stack
├── requirements.txt               # Backend dependencies
└── README.md
```

---

## ⚡ Quick Start

### 1. Prerequisites
- **Python** ≥ 3.10
- **PostgreSQL** or **Docker**

### 2. Clone & Environment Setup
```bash
git clone https://github.com/Jeetchavan02/WHATIF.git
cd "WHAT IF"

# Configure environment
cp .env.example .env
```

### 3. Launch PostgreSQL
```bash
docker-compose up -d
```

### 4. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Launch the Servers
**Terminal 1 — Backend API (Port 8000):**
```bash
export PYTHONPATH=$PWD
uvicorn backend.fastapi_app.main:app --host 0.0.0.0 --port 8000 --reload
```
*API documentation available at `http://localhost:8000/docs`*

**Terminal 2 — Frontend HUD (Port 3000):**
```bash
python3 -m http.server 3000 --directory frontend
```
*Open `http://localhost:3000` in any modern web browser.*

---

## 🔮 WHAT IF Oracle (CI/CD API)

The Oracle endpoint is designed for automated pull-request risk assessment and CI/CD pipelines.

### Request
```bash
curl -X POST http://localhost:8000/api/repositories/1/oracle \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "fastapi/routing.py",
    "change_type": "delete",
    "max_depth": 4
  }'
```

### Response
```json
{
  "scenario_id": "WIF-A94F81C2",
  "generated_at": "2026-10-20T01:12:21Z",
  "repository_id": 10,
  "target_file": "fastapi/routing.py",
  "change_type": "delete",
  "risk_assessment": {
    "risk_level": "HIGH",
    "impact_score": 100,
    "blast_radius_count": 24,
    "source_commit_frequency": 15,
    "change_multiplier": 1.4
  },
  "blast_radius": [
    { "path": "fastapi/applications.py", "language": "python", "depth": 1 },
    { "path": "fastapi/openapi/utils.py", "language": "python", "depth": 1 },
    { "path": "tests/test_route_handler_wrapping.py", "language": "python", "depth": 1 }
  ],
  "suggested_reviewers": [
    { "name": "Sebastián Ramírez", "email": "tiangolo@gmail.com", "touch_count": 18 },
    { "name": "Alexander Rauhut", "email": "alexander@rauhut.dev", "touch_count": 4 }
  ],
  "summary": "Changing 'routing.py' via 'delete' affects 24 file(s) with HIGH risk (score 100/100). 2 reviewer(s) suggested based on commit history."
}
```

---

## 💥 Blast Radius Simulator

1. **Instant Search**: Type file substrings into the `🔍 Search files...` bar to filter candidates.
2. **Interactive Node Selection**: Click any file chip or canvas node to select it as the blast origin.
3. **Simulation Execution**: Adjust depth (1–10) and hit **Simulate Reality Collapse**.
4. **Causal Shockwaves**: Shockwaves ripple outwards across the graph while the downstream impact lists populate in real-time.

---

## 🪐 Multiverse Graph Visualizer

The canvas visualizer operates on an interactive 2D physics and matrix projection engine:
- **Orbital Force**: Physics simulation featuring gravitational pull, spring tension, and photon particle conduits.
- **Concentric Rims**: Projects components radially outward by layer depth.
- **Matrix Grid**: Aligns complex architectural layers in an organized inspection grid.
- **Interactive Controls**:
  - **Pan**: Click and drag empty space to pan across space.
  - **Zoom**: Scroll wheel or trackpad pinch to zoom relative to cursor position (`+`, `−`, `⟲ Reset` buttons).
  - **Draggable Nodes**: Grab any node to detach it and inspect local relationships.
  - **High-DPI Retina Ready**: Scales dynamically using `window.devicePixelRatio`.

---

## 📡 Complete API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/repositories` | Ingest and analyze a Git repository URL or local path |
| `DELETE` | `/api/repositories/{id}` | Completely erase a repository timeline and associated graph data |
| `PATCH` | `/api/repositories/{id}/url` | Update repository URL configuration |
| `POST` | `/api/repositories/{id}/whatif` | Run multi-depth BFS blast radius propagation |
| `POST` | `/api/repositories/{id}/oracle` | Query WHAT IF Oracle for CI/CD risk assessment & reviewer ranking |
| `GET` | `/api/repositories/{id}/graph` | Retrieve node and edge graph geometry |
| `GET` | `/api/repositories/{id}/files` | List all discovered source files |
| `GET` | `/api/repositories/{id}/dependencies` | Inspect parsed AST cross-file dependency edges |
| `GET` | `/api/repositories/{id}/commits` | Paginated commit history stream |

---

## ⚙️ Configuration

Set via environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | Connection URI for PostgreSQL database |
| `WHATIF_MAX_COMMITS` | `400` | Maximum historical commits indexed per repository for performance |
| `PORT` | `8000` | FastAPI server listening port |

---

## 🧪 Testing

Run backend tests using Pytest:

```bash
export PYTHONPATH=$PWD
pytest -v
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your branch: `git checkout -b feature/cosmic-enhancement`
3. Commit your changes: `git commit -m 'feat: introduce new feature'`
4. Push to branch: `git push origin feature/cosmic-enhancement`
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.

<br/>

<div align="center">
  <sub>Built with passion for deterministic software causality. <strong>WHAT IF...?</strong></sub>
</div>
