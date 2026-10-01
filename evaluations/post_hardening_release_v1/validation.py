"""Version-aware release integrity checks without changing historical validators."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = EVALUATION_DIR / "release_manifest_v1.json"

EXPECTED_AUTHORISED_RUNTIME_DRIFT = {
    "app.py",
    "src/agent_loop_hardened.py",
    "src/agent_tools.py",
    "src/authority_registry.py",
    "src/schemas.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_hash_map(files: dict[str, str], *, label: str) -> None:
    for relative, expected in files.items():
        path = PROJECT_ROOT / relative
        if not path.is_file():
            raise ValueError(f"{label} missing: {relative}")
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"{label} integrity mismatch: {relative}")


def validate_current_release() -> dict[str, Any]:
    """Validate current source plus separately pinned immutable historical evidence."""
    manifest = load_json(MANIFEST_PATH)
    _verify_hash_map(manifest["current_application_files"], label="Current release")
    _verify_hash_map(manifest["current_regression_files"], label="Current regression")
    _verify_hash_map(
        manifest["historical_baseline_manifests"], label="Historical baseline manifest"
    )

    ledger_meta = manifest["immutable_evidence_ledger"]
    ledger_path = PROJECT_ROOT / ledger_meta["path"]
    if sha256(ledger_path) != ledger_meta["sha256"]:
        raise ValueError("Immutable evidence ledger integrity mismatch")
    ledger = load_json(ledger_path)
    protected = ledger["protected_artifacts"]
    if len(protected) != ledger_meta["artifact_count"]:
        raise ValueError("Immutable evidence artifact count mismatch")
    _verify_hash_map(protected, label="Protected historical artifact")

    observations = {
        item["path"]: item["sha256"] for item in manifest["observation_layers"].values()
    }
    _verify_hash_map(observations, label="Observation layer")
    benchmark = manifest["retrieval_benchmark_identity"]
    _verify_hash_map(
        {benchmark["question_bank_path"]: benchmark["question_bank_sha256"]},
        label="Frozen retrieval benchmark",
    )
    return manifest


def historical_baseline_drift(manifest_relative: str) -> list[dict[str, str]]:
    """Report every drift, unlike historical validators which stop at the first file."""
    baseline = load_json(PROJECT_ROOT / manifest_relative)
    drift = []
    for relative, expected in baseline["protected_existing_files"].items():
        actual = sha256(PROJECT_ROOT / relative)
        if actual != expected:
            drift.append({"path": relative, "expected": expected, "actual": actual})
    return drift


def validate_historical_snapshot_relationship() -> dict[str, list[dict[str, str]]]:
    """Confirm both baselines differ only in the five authorised runtime files."""
    result = {}
    for relative in (
        "evaluations/auditor_scenario_v1/freeze_manifest_v1.json",
        "evaluations/auditor_scenario_v1_1/freeze_manifest_v1_1.json",
    ):
        drift = historical_baseline_drift(relative)
        if {item["path"] for item in drift} != EXPECTED_AUTHORISED_RUNTIME_DRIFT:
            raise ValueError(f"Unexpected historical snapshot drift: {relative}")
        result[relative] = drift
    return result


def validate_observation_separation() -> dict[str, str]:
    """Confirm S01-S08 post-fix results are separate from both frozen observations."""
    manifest = load_json(MANIFEST_PATH)
    layers = manifest["observation_layers"]
    documents = {
        name: load_json(PROJECT_ROOT / metadata["path"])
        for name, metadata in layers.items()
    }
    case_ids = [f"S{number:02d}" for number in range(1, 9)]
    for name, document in documents.items():
        if [item["case_id"] for item in document["observations"]] != case_ids:
            raise ValueError(f"Observation case IDs differ: {name}")
    paths = {name: metadata["path"] for name, metadata in layers.items()}
    if len(set(paths.values())) != len(paths):
        raise ValueError("Observation layers are not stored separately")
    return paths
