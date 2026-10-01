from __future__ import annotations

import unittest

from evaluations.auditor_scenario_v1.validation import validate_manifest as validate_v1
from evaluations.auditor_scenario_v1_1.validation import validate_manifest as validate_v11
from evaluations.post_hardening_release_v1.validation import (
    EXPECTED_AUTHORISED_RUNTIME_DRIFT,
    validate_current_release,
    validate_historical_snapshot_relationship,
    validate_observation_separation,
)


class PostHardeningReleaseIntegrityTests(unittest.TestCase):
    def test_current_release_and_all_88_immutable_artifacts_match(self):
        manifest = validate_current_release()
        self.assertEqual(manifest["release_id"], "post_hardening_release_v1")
        self.assertEqual(manifest["immutable_evidence_ledger"]["artifact_count"], 88)

    def test_historical_validators_remain_strict_and_available(self):
        for validator in (validate_v1, validate_v11):
            with self.subTest(validator=validator.__module__):
                with self.assertRaisesRegex(ValueError, r"^Integrity mismatch: app\.py$"):
                    validator()

    def test_complete_baseline_drift_is_only_the_authorised_five_files(self):
        report = validate_historical_snapshot_relationship()
        self.assertEqual(len(report), 2)
        for manifest, drift in report.items():
            with self.subTest(manifest=manifest):
                self.assertEqual(
                    {item["path"] for item in drift}, EXPECTED_AUTHORISED_RUNTIME_DRIFT
                )
                self.assertEqual(drift[0]["path"], "app.py")

    def test_postfix_s01_s08_observations_are_separate_from_originals(self):
        paths = validate_observation_separation()
        self.assertEqual(len(paths), 3)
        self.assertNotEqual(paths["historical_v1_1"], paths["post_hardening_s01_s08"])

    def test_frozen_benchmark_and_offline_policy_are_explicit(self):
        manifest = validate_current_release()
        benchmark = manifest["retrieval_benchmark_identity"]
        self.assertEqual(
            (benchmark["questions"], benchmark["development"], benchmark["frozen_holdout"]),
            (50, 12, 38),
        )
        self.assertFalse(benchmark["metrics_recomputed"])
        self.assertEqual(
            manifest["execution_policy"],
            {"network_allowed": False, "live_openrouter_calls": 0, "live_sec_calls": 0},
        )


if __name__ == "__main__":
    unittest.main()
