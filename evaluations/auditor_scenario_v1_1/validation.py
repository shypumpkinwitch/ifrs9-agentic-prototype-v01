"""Version 1.1 evaluation helpers; no application integration or mutation."""
from pathlib import Path

from evaluations.auditor_scenario_v1.validation import (
    CASE_IDS, DIMENSIONS, load_json, sha256, summarise_manual_review,
    validate_cases as validate_original_schema,
)

EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALUATION_DIR.parents[1]


def validate_cases(cases: list) -> None:
    validate_original_schema(cases, load_json(EVALUATION_DIR / "cases.schema.json"))


def validate_manifest(evaluation_dir: Path = EVALUATION_DIR, project_root: Path = PROJECT_ROOT) -> dict:
    manifest = load_json(evaluation_dir / "freeze_manifest_v1_1.json")
    if manifest["evaluation_id"] != "auditor_scenario_evaluation_v1_1":
        raise ValueError("Wrong evaluation version.")
    if manifest["case_count"] != 8 or not manifest["frozen_before_execution"]:
        raise ValueError("Invalid freeze metadata.")
    if set(manifest["files"]) != {"cases_frozen_v1_1.json", "cases.schema.json", "protocol_v1_1.json"}:
        raise ValueError("Unexpected frozen file set.")
    for mapping, base in ((manifest["files"], evaluation_dir), (manifest["protected_existing_files"], project_root)):
        for relative, expected in mapping.items():
            target = (base / relative).resolve()
            if not target.is_relative_to(base.resolve()):
                raise ValueError("Manifest path escapes its root.")
            if not target.is_file() or sha256(target) != expected:
                raise ValueError(f"Integrity mismatch: {relative}")
    return manifest
