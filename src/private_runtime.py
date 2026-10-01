from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .schemas import DataValidationError
from .source_registry import (
    hash_canonical_json,
    hash_file,
    load_private_corpus_read_only,
)


BUNDLE_NAME = "PE6201_Codex_Private_Runtime_Inputs_v01"


def default_private_bundle(project_root: str | Path) -> Path:
    return (
        Path(project_root)
        / "private_data"
        / "runtime_inputs_v01"
        / BUNDLE_NAME
    )


def audit_private_bundle(bundle_path: str | Path) -> dict[str, Any]:
    """Validate private inputs without modifying or reproducing their source bodies."""
    bundle = Path(bundle_path).resolve(strict=True)
    manifest_path = bundle / "freeze_manifest_v02.json"
    corpus_path = bundle / "working_corpus_v01.json"
    summary_path = bundle / "holdout_summary_v02.csv"

    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    chunks, raw_corpus_hash = load_private_corpus_read_only(corpus_path)
    canonical_corpus_hash = hash_canonical_json(corpus_path)
    expected_corpus_hash = str(manifest["corpus_sha256"]).lower()

    frozen_checks = []
    for name, expected_hash in manifest.get("file_sha256", {}).items():
        path = bundle / name
        actual_hash = hash_file(path) if path.is_file() else None
        frozen_checks.append(
            {
                "name": name,
                "present": path.is_file(),
                "expected_sha256": str(expected_hash).lower(),
                "actual_sha256": actual_hash,
                "hash_matches": actual_hash == str(expected_hash).lower(),
            }
        )

    return {
        "bundle_path": str(bundle),
        "corpus_path": str(corpus_path),
        "manifest_path": str(manifest_path),
        "summary_path": str(summary_path),
        "record_count": len(chunks),
        "unique_chunk_ids": len({chunk.chunk_id for chunk in chunks}),
        "raw_authority_levels": sorted({chunk.authority_level for chunk in chunks}),
        "canonical_authority_classes": sorted({chunk.authority_class for chunk in chunks}),
        "manifest_corpus_sha256": expected_corpus_hash,
        "raw_corpus_sha256": raw_corpus_hash,
        "canonical_corpus_sha256": canonical_corpus_hash,
        "canonical_hash_matches_manifest": canonical_corpus_hash == expected_corpus_hash,
        "manifest_file_sha256": hash_file(manifest_path),
        "summary_file_sha256": hash_file(summary_path),
        "frozen_file_checks": frozen_checks,
        "missing_manifest_files": [
            item["name"] for item in frozen_checks if not item["present"]
        ],
        "mismatched_frozen_files": [
            item["name"]
            for item in frozen_checks
            if item["present"] and not item["hash_matches"]
        ],
    }


def load_private_baseline(summary_path: str | Path) -> dict[str, Any]:
    """Read the supplied historical summary; never recompute it from the holdout."""
    with Path(summary_path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_method = {row["method"].strip().lower(): row for row in rows}
    if set(by_method) != {"bm25", "semantic"}:
        raise DataValidationError("Historical summary must contain BM25 and Semantic rows.")

    def metrics(method: str) -> dict[str, Any]:
        row = by_method[method]
        n = int(row["n"])
        at_1_count = int(row["hit_at_1_count"])
        at_5_count = int(row["hit_at_5_count"])
        return {
            "hit_at_1": float(row["hit_at_1_percent"]) / 100,
            "hit_at_1_count": f"{at_1_count}/{n}",
            "hit_at_5": float(row["hit_at_5_percent"]) / 100,
            "hit_at_5_count": f"{at_5_count}/{n}",
        }

    return {
        "status": "precomputed_historical_fixed_corpus_results",
        "source_note": (
            "Loaded read-only from supplied holdout_summary_v02.csv; not recomputed "
            "and not used to tune the frozen holdout."
        ),
        "corpus_chunks": 76,
        "development_questions": 12,
        "holdout_questions": 38,
        "labels_note": (
            "Historical fixed-corpus baseline only; this is not new workflow or agent performance."
        ),
        "bm25": metrics("bm25"),
        "semantic": metrics("semantic"),
        "immutability_note": "Read-only supplied result; never written by the application.",
    }
