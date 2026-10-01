"""Evaluation utilities only; never imported by the application."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALUATION_DIR.parents[1]
DIMENSIONS = (
    "scope_topic_routing", "official_authority", "authority_separation",
    "comparator_behaviour", "framework_and_comparability", "safe_handoff",
)
CASE_IDS = [f"S{index:02}" for index in range(1, 9)]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_cases(cases: list, schema: dict | None = None) -> None:
    schema = schema or load_json(EVALUATION_DIR / "cases.schema.json")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("Exactly eight frozen scenario cases are required.")
    spec = schema["items"]
    for case in cases:
        if not isinstance(case, dict) or set(case) != set(spec["required"]):
            raise ValueError("Case fields must match the frozen evaluation schema exactly.")
        for name, field in spec["properties"].items():
            value = case[name]
            if field["type"] == "array":
                if not isinstance(value, list) or not value or not all(
                    isinstance(item, str) and item.strip() for item in value
                ):
                    raise ValueError(f"{name} must be a non-empty string list.")
                if len(set(value)) != len(value):
                    raise ValueError(f"{name} must not contain duplicates.")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")
            if "enum" in field and value not in field["enum"]:
                raise ValueError(f"Unsupported {name}.")
    if [case["case_id"] for case in cases] != CASE_IDS:
        raise ValueError("Cases must be uniquely ordered S01 through S08.")
    if len({case["scenario"] for case in cases}) != 8:
        raise ValueError("Scenario texts must be unique.")


def validate_manifest(evaluation_dir: Path = EVALUATION_DIR, project_root: Path = PROJECT_ROOT) -> dict:
    manifest = load_json(evaluation_dir / "freeze_manifest_v1.json")
    if manifest["case_count"] != 8 or not manifest["frozen_before_execution"]:
        raise ValueError("Invalid freeze metadata.")
    if set(manifest["files"]) != {"cases_frozen_v1.json", "cases.schema.json", "protocol_v1.json"}:
        raise ValueError("Unexpected frozen file set.")
    for mapping, base in ((manifest["files"], evaluation_dir), (manifest["protected_existing_files"], project_root)):
        for relative, expected in mapping.items():
            target = (base / relative).resolve()
            if not target.is_relative_to(base.resolve()):
                raise ValueError("Manifest path escapes its root.")
            if not target.is_file() or sha256(target) != expected:
                raise ValueError(f"Integrity mismatch: {relative}")
    return manifest


def summarise_manual_review(entries: list[dict]) -> dict:
    """Aggregate supplied human judgements; never infer them from workflow output."""
    if [entry["case_id"] for entry in entries] != CASE_IDS:
        raise ValueError("Manual review requires exactly S01 through S08.")
    case_results = []
    rates = {}
    for entry in entries:
        if set(entry["dimensions"]) != set(DIMENSIONS):
            raise ValueError("All six evaluation dimensions are required.")
        applicable = []
        pending = False
        for judgement in entry["dimensions"].values():
            status = judgement["status"]
            if status not in {None, "PASS", "FAIL", "N/A"}:
                raise ValueError("Manual status must be PASS, FAIL, N/A or pending null.")
            if status is not None and not judgement.get("reason", "").strip():
                raise ValueError("Every manual judgement, including N/A, requires a reason.")
            pending |= status is None
            if status in {"PASS", "FAIL"}:
                applicable.append(status)
        case_results.append({
            "case_id": entry["case_id"],
            "scenario_pass": None if pending else bool(applicable) and all(s == "PASS" for s in applicable),
        })
    for dimension in DIMENSIONS:
        statuses = [entry["dimensions"][dimension]["status"] for entry in entries]
        passed, failed = statuses.count("PASS"), statuses.count("FAIL")
        pending, na = statuses.count(None), statuses.count("N/A")
        rates[dimension] = {
            "pass": passed, "fail": failed, "not_applicable": na, "pending": pending,
            "pass_rate_excluding_na": passed / (passed + failed) if passed + failed and not pending else None,
        }
    complete = all(item["scenario_pass"] is not None for item in case_results)
    return {
        "classification": "Manual judgements only; separate from retrieval and offline diagnostics",
        "per_case": case_results, "per_dimension": rates,
        "scenario_pass_count": sum(item["scenario_pass"] for item in case_results) if complete else None,
        "scenario_count": 8, "manual_review_complete": complete,
    }
