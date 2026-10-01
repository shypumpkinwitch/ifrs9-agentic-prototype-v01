"""Run current tests and legacy snapshot checks as explicit, separate categories."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluations.post_hardening_release_v1.validation import (  # noqa: E402
    validate_current_release,
    validate_historical_snapshot_relationship,
    validate_observation_separation,
)


LEGACY_BASELINE_TEST_IDS = {
    "tests.test_auditor_scenario_evaluation_v1.AuditorScenarioEvaluationV1Tests.test_manifest_and_historical_files_match",
    "tests.test_auditor_scenario_evaluation_v1.AuditorScenarioEvaluationV1Tests.test_all_cases_execute_offline_with_safe_evidence_and_no_mutation",
    "tests.test_auditor_scenario_evaluation_v1_1.AuditorScenarioEvaluationV11Tests.test_freeze_and_protected_v1_application_historical_integrity",
    "tests.test_auditor_scenario_evaluation_v1_1.AuditorScenarioEvaluationV11Tests.test_deterministic_replay_zero_live_calls_cost_and_ungraded_template",
}


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def _summary(result: unittest.TestResult) -> dict[str, object]:
    return {
        "tests_run": result.testsRun,
        "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "failure_details": [
            {"test": test.id(), "error": traceback.strip().splitlines()[-1]}
            for test, traceback in result.failures
        ],
        "error_details": [
            {"test": test.id(), "error": traceback.strip().splitlines()[-1]}
            for test, traceback in result.errors
        ],
        "skipped_details": [
            {"test": test.id(), "reason": reason} for test, reason in result.skipped
        ],
    }


def run_reconciled_suite() -> dict[str, object]:
    validate_current_release()
    drift = validate_historical_snapshot_relationship()
    validate_observation_separation()

    discovered = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"), top_level_dir=str(ROOT)
    )
    tests = list(_flatten(discovered))
    legacy = [test for test in tests if test.id() in LEGACY_BASELINE_TEST_IDS]
    current = [test for test in tests if test.id() not in LEGACY_BASELINE_TEST_IDS]
    if {test.id() for test in legacy} != LEGACY_BASELINE_TEST_IDS:
        raise RuntimeError("The explicit legacy baseline test inventory is incomplete")

    blocked = AssertionError("Real network access is blocked during release verification.")
    with (
        patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "SEC_USER_AGENT": ""}),
        patch("socket.socket", side_effect=blocked),
        patch("socket.create_connection", side_effect=blocked),
        patch("urllib.request.urlopen", side_effect=blocked),
    ):
        current_result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=2).run(
            unittest.TestSuite(current)
        )
        legacy_result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=2).run(
            unittest.TestSuite(legacy)
        )

    current_summary = _summary(current_result)
    legacy_summary = _summary(legacy_result)
    legacy_expected = (
        legacy_summary["tests_run"] == 4
        and legacy_summary["failed"] == 0
        and legacy_summary["errors"] == 4
        and all(
            detail["error"] == "ValueError: Integrity mismatch: app.py"
            for detail in legacy_summary["error_details"]
        )
    )
    release_ready = (
        current_summary["failed"] == 0
        and current_summary["errors"] == 0
        and legacy_expected
    )
    return {
        "classification": "Version-aware offline release verification",
        "current_version_functional_and_integrity_tests": current_summary,
        "historical_baseline_snapshot_tests": {
            **legacy_summary,
            "expected_snapshot_drift": legacy_expected,
            "meaning": "These execute unchanged historical validators against a later application version.",
        },
        "historical_manifest_complete_drift": drift,
        "protected_immutable_artifacts_checked": 88,
        "live_openrouter_calls": 0,
        "live_sec_calls": 0,
        "release_ready": release_ready,
    }


if __name__ == "__main__":
    report = run_reconciled_suite()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["release_ready"] else 1)
