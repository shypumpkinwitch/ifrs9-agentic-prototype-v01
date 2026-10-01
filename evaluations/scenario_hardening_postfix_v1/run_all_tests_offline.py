"""Run the unfiltered existing unittest suite with real networking blocked."""
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def run_suite():
    blocked = AssertionError("Real network access is blocked during offline regression tests.")
    with (
        patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "SEC_USER_AGENT": ""}),
        patch("socket.socket", side_effect=blocked),
        patch("socket.create_connection", side_effect=blocked),
        patch("urllib.request.urlopen", side_effect=blocked),
    ):
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=2).run(suite)
    return {
        "classification": "Full, unfiltered regression suite; tests with mocked providers do not represent live calls",
        "tests_run": result.testsRun,
        "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "failed": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "failure_details": [{"test": test.id(), "error": traceback.strip().splitlines()[-1]} for test, traceback in result.failures],
        "error_details": [{"test": test.id(), "error": traceback.strip().splitlines()[-1]} for test, traceback in result.errors],
        "skipped_details": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "real_network_access_allowed": False,
        "live_openrouter_calls": 0, "live_sec_calls": 0,
    }


if __name__ == "__main__":
    report = run_suite()
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if report["failed"] or report["errors"] else 0)
