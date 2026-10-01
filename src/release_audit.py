from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_TOP_LEVEL = {"private_data", "external_runtime", "outputs", ".venv", ".git"}
EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".csv", ".txt", ".toml", ".yml", ".yaml"}
REQUIRED_IGNORE_LINES = {
    ".env",
    ".env*",
    ".venv/",
    ".streamlit/secrets.toml",
    "private_data/*",
    "external_runtime/*",
    "outputs/*",
}
GENERIC_SECRET_PATTERNS = {
    "OpenRouter-style key": re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{20,}\b"),
    "authorization bearer token": re.compile(r"Authorization\s*[:=]\s*Bearer\s+[A-Za-z0-9._~-]{20,}", re.I),
    "assigned OpenRouter key": re.compile(
        r"OPENROUTER_API_KEY\s*=\s*['\"](?!\s*(?:<|your-|example|dummy))[^'\"]{16,}['\"]",
        re.I,
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_files(project_root: Path = PROJECT_ROOT) -> list[Path]:
    files: list[Path] = []
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        if len(relative.parts) == 1 and relative.name.casefold().startswith(".env"):
            continue
        if relative.parts[0] in EXCLUDED_TOP_LEVEL:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in relative.parts):
            continue
        files.append(path)
    return sorted(files)


def run_release_audit(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    root = project_root.resolve()
    findings: list[dict[str, str]] = []
    ignored_material: list[str] = []

    ignore_path = root / ".gitignore"
    ignore_lines = {
        line.strip()
        for line in ignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    } if ignore_path.is_file() else set()
    for required in sorted(REQUIRED_IGNORE_LINES - ignore_lines):
        findings.append({"type": "missing_ignore_rule", "detail": required})

    for private_root in (root / "private_data", root / "external_runtime"):
        if private_root.exists():
            ignored_material.append(str(private_root.relative_to(root)).replace("\\", "/"))

    exact_secrets = {
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", "").strip(),
        "SEC_USER_AGENT": os.getenv("SEC_USER_AGENT", "").strip(),
    }
    scanned = public_files(root)
    for path in scanned:
        relative = str(path.relative_to(root)).replace("\\", "/")
        lower_name = path.name.casefold()
        if lower_name == ".env" or lower_name.startswith(".env."):
            findings.append({"type": "environment_file", "path": relative})
        if lower_name in {"working_corpus_v01.json", "primary.htm", "primary.html"}:
            findings.append({"type": "raw_source_file", "path": relative})
        if path.suffix.casefold() not in TEXT_SUFFIXES and path.name != ".gitignore":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in GENERIC_SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append({"type": "credential_pattern", "path": relative, "detail": label})
        for name, value in exact_secrets.items():
            if value and value in text:
                findings.append({"type": "exact_runtime_secret", "path": relative, "detail": name})

    ledger_path = root / "docs" / "final_submission" / "HISTORICAL_ARTIFACT_HASHES_v01.json"
    historical_checks: list[dict[str, Any]] = []
    if ledger_path.is_file():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for relative, expected in ledger["artifacts"].items():
            path = root / relative
            actual = _sha256(path) if path.is_file() else None
            historical_checks.append(
                {
                    "path": relative,
                    "present": path.is_file(),
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                    "hash_matches": actual == expected,
                }
            )
    else:
        findings.append({"type": "missing_preservation_ledger", "path": str(ledger_path)})

    if any(not item["hash_matches"] for item in historical_checks):
        findings.append({"type": "historical_artifact_integrity", "detail": "one or more hash mismatches"})

    private_integrity: dict[str, Any] = {"status": "not_available_optional_input"}
    bundle = root / "private_data" / "runtime_inputs_v01" / "PE6201_Codex_Private_Runtime_Inputs_v01"
    if bundle.is_dir():
        sys.path.insert(0, str(root))
        from src.private_runtime import audit_private_bundle

        audit = audit_private_bundle(bundle)
        private_integrity = {
            "status": "checked",
            "record_count": audit["record_count"],
            "unique_chunk_ids": audit["unique_chunk_ids"],
            "raw_corpus_sha256": audit["raw_corpus_sha256"],
            "canonical_corpus_sha256": audit["canonical_corpus_sha256"],
            "manifest_corpus_sha256": audit["manifest_corpus_sha256"],
            "canonical_hash_matches_manifest": audit["canonical_hash_matches_manifest"],
            "missing_manifest_files": audit["missing_manifest_files"],
            "mismatched_frozen_files": audit["mismatched_frozen_files"],
        }
        if (
            audit["record_count"] != 76
            or audit["unique_chunk_ids"] != 76
            or not audit["canonical_hash_matches_manifest"]
            or audit["missing_manifest_files"]
            or audit["mismatched_frozen_files"]
        ):
            findings.append({"type": "private_frozen_integrity", "detail": "private bundle check failed"})

    return {
        "status": "pass" if not findings else "fail",
        "project_root": str(root),
        "public_files_scanned": len(scanned),
        "excluded_local_runtime_roots_present": ignored_material,
        "findings": findings,
        "historical_artifact_checks": historical_checks,
        "private_frozen_integrity": private_integrity,
        "notes": [
            "The scan evaluates the release-eligible tree after excluding explicitly ignored local runtime roots.",
            "A passing credential scan reduces accidental-disclosure risk but is not a substitute for platform secret scanning before publication.",
        ],
    }


def main() -> int:
    result = run_release_audit()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
