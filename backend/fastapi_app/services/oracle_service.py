"""
WHAT IF Oracle — CI/CD Risk Intelligence Service

Given a repository, a target file path, and a proposed change type, returns a
structured risk report that can be consumed by GitHub Actions, PR bots, or any
CI pipeline to answer: "What if I change X?"

Complexity: O(F + C) where F = files in blast radius, C = commits touching those files.
All data is pre-indexed in the DB at analysis time — this query is purely read-only.
"""

import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.fastapi_app.models import models
from backend.fastapi_app.services.impact_service import get_impact_propagation

logger = logging.getLogger(__name__)

# Risk thresholds (blast radius file count → risk tier)
RISK_TIERS = [
    (0,   "NONE"),
    (3,   "LOW"),
    (10,  "MEDIUM"),
    (25,  "HIGH"),
    (999, "CRITICAL"),
]

CHANGE_MULTIPLIERS = {
    "delete":         1.4,   # deletion fans out hardest
    "rename":         1.25,  # rename breaks all importers
    "modify":         1.0,
    "add_dependency": 0.85,  # adds rarely break things
}

def _risk_level(blast_count: int, change_type: str) -> tuple[str, int]:
    """Return (risk_label, 0-100 impact_score)."""
    multiplier = CHANGE_MULTIPLIERS.get(change_type, 1.0)
    adjusted   = blast_count * multiplier
    label = "NONE"
    for threshold, tier in RISK_TIERS:
        if adjusted >= threshold:
            label = tier
    # Normalize to 0-100
    score = min(100, int((adjusted / max(adjusted, 1)) * min(100, adjusted * 3)))
    score = max(0, min(100, int(adjusted * 3)))
    return label, score


def run_oracle(
    repo_id: int,
    file_path: str,
    change_type: str,
    db: Session,
    max_depth: int = 4,
) -> dict:
    """
    Core Oracle logic — O(F + C) read-only analysis.

    Returns a structured dict suitable for JSON serialization.
    """
    scenario_id = f"WIF-{uuid.uuid4().hex[:8].upper()}"
    generated_at = datetime.now(timezone.utc).isoformat()

    # ── 1. Resolve file node ──────────────────────────────────────────────
    file_record = db.query(models.File).filter(
        models.File.repository_id == repo_id,
        models.File.path == file_path,
    ).first()

    if not file_record:
        # Fuzzy match: basename search
        basename = file_path.split("/")[-1]
        file_record = db.query(models.File).filter(
            models.File.repository_id == repo_id,
            models.File.path.ilike(f"%{basename}"),
        ).first()

    if not file_record:
        return {
            "scenario_id": scenario_id,
            "error": f"File '{file_path}' not found in repository index.",
            "tip": "Make sure the repository analysis has completed and the path matches exactly.",
        }

    # ── 2. Blast radius (structural propagation) ─────────────────────────
    blast_nodes = get_impact_propagation(repo_id, "file", file_record.id, db, max_depth=max_depth)
    blast_file_ids = [n["node_id"] for n in blast_nodes if n["node_type"] == "file"]
    blast_count = len(blast_file_ids)

    # Resolve blast file paths — single query
    blast_files: list[dict] = []
    if blast_file_ids:
        bf_records = db.query(models.File.id, models.File.path, models.File.language).filter(
            models.File.id.in_(blast_file_ids)
        ).all()
        blast_depth_map = {n["node_id"]: n["depth"] for n in blast_nodes if n["node_type"] == "file"}
        for bf in bf_records:
            blast_files.append({
                "path":     bf.path,
                "language": bf.language or "unknown",
                "depth":    blast_depth_map.get(bf.id, 0),
            })
        blast_files.sort(key=lambda x: x["depth"])

    # ── 3. Risk scoring ───────────────────────────────────────────────────
    risk_label, impact_score = _risk_level(blast_count, change_type)

    # ── 4. Suggested reviewers — who touched this file + blast radius most ─
    # Gather all relevant file IDs (source + blast)
    relevant_ids = [file_record.id] + blast_file_ids[:20]   # cap for perf

    # Find commit IDs that touched any of these files
    touched_commits = (
        db.query(models.CommitFileChange.commit_id, models.CommitFileChange.file_path)
        .join(models.Commit)
        .filter(
            models.Commit.repository_id == repo_id,
            models.CommitFileChange.file_path.in_([f["path"] for f in blast_files[:20]] + [file_record.path]),
        )
        .subquery()
    )

    reviewer_rows = (
        db.query(
            models.Commit.author_name,
            models.Commit.author_email,
            func.count(models.Commit.id).label("touch_count"),
        )
        .join(touched_commits, models.Commit.id == touched_commits.c.commit_id)
        .filter(models.Commit.repository_id == repo_id)
        .group_by(models.Commit.author_name, models.Commit.author_email)
        .order_by(func.count(models.Commit.id).desc())
        .limit(6)
        .all()
    )

    suggested_reviewers = [
        {
            "name":        r.author_name,
            "email":       r.author_email,
            "touch_count": r.touch_count,
        }
        for r in reviewer_rows
    ]

    # If the specific file or blast radius has no historical commit matches, fall back to top repository contributors
    if not suggested_reviewers:
        top_contribs = (
            db.query(
                models.Commit.author_name,
                models.Commit.author_email,
                func.count(models.Commit.id).label("touch_count"),
            )
            .filter(models.Commit.repository_id == repo_id)
            .group_by(models.Commit.author_name, models.Commit.author_email)
            .order_by(func.count(models.Commit.id).desc())
            .limit(3)
            .all()
        )
        suggested_reviewers = [
            {
                "name":        r.author_name,
                "email":       r.author_email,
                "touch_count": r.touch_count,
                "is_fallback": True,
            }
            for r in top_contribs
        ]

    # ── 5. Historical commit frequency for source file ────────────────────
    source_commit_count = (
        db.query(func.count(models.CommitFileChange.id))
        .join(models.Commit)
        .filter(
            models.Commit.repository_id == repo_id,
            models.CommitFileChange.file_path == file_record.path,
        )
        .scalar() or 0
    )

    # ── 6. Assemble response ──────────────────────────────────────────────
    return {
        "scenario_id":     scenario_id,
        "generated_at":    generated_at,
        "repository_id":   repo_id,
        "target_file":     file_record.path,
        "change_type":     change_type,
        "risk_assessment": {
            "risk_level":        risk_label,
            "impact_score":      impact_score,          # 0-100
            "blast_radius_count": blast_count,
            "source_commit_frequency": source_commit_count,
            "change_multiplier": CHANGE_MULTIPLIERS.get(change_type, 1.0),
        },
        "blast_radius":         blast_files,
        "suggested_reviewers":  suggested_reviewers,
        "summary": (
            f"Changing '{file_record.path.split('/')[-1]}' via '{change_type}' "
            f"affects {blast_count} file(s) with {risk_label} risk (score {impact_score}/100). "
            f"{len(suggested_reviewers)} reviewer(s) suggested based on commit history."
        ),
    }
