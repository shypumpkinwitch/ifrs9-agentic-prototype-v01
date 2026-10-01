from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import DataValidationError


SNAPSHOT_NAME = "final_submission_snapshot_v01.json"


def load_final_submission_snapshot(project_root: str | Path) -> dict[str, Any]:
    """Load the public-safe, recorded demo synthesis without making network calls."""
    path = Path(project_root) / "data" / "public_demo" / SNAPSHOT_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "classification",
        "flagship_scenario",
        "research_needs",
        "recorded_candidates",
        "authority_status",
        "gate51_integrity_caveat",
        "historical_retrieval",
        "model_cost_summary",
        "gate5_to_gate51_input_token_reduction",
        "final_handoff",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise DataValidationError(
            "Final submission snapshot is missing fields: " + ", ".join(missing)
        )
    if payload["gate51_integrity_caveat"]["second_live_run_performed"]:
        raise DataValidationError("Gate 5.1 snapshot must not claim a second live run.")
    if payload["historical_retrieval"]["holdout_n"] != 38:
        raise DataValidationError("Historical holdout size must remain 38.")
    return payload


def candidate_by_company(snapshot: dict[str, Any], company: str) -> dict[str, Any]:
    for candidate in snapshot["recorded_candidates"]:
        if candidate["company"] == company:
            return candidate
    raise DataValidationError(f"Recorded candidate not found: {company}")
