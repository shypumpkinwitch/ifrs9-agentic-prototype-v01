from __future__ import annotations

from copy import deepcopy
import tempfile
import unittest
from pathlib import Path

from evaluations.auditor_scenario_v1.run_deterministic import run_offline
from evaluations.auditor_scenario_v1.validation import (
    CASE_IDS, DIMENSIONS, EVALUATION_DIR, load_json, summarise_manual_review,
    validate_cases, validate_manifest,
)


class AuditorScenarioEvaluationV1Tests(unittest.TestCase):
    def setUp(self):
        self.cases = load_json(EVALUATION_DIR / "cases_frozen_v1.json")
        self.template = load_json(EVALUATION_DIR / "manual_review_template_v1.json")["cases"]

    def test_exact_eight_cases_and_requested_schema(self):
        validate_cases(self.cases)
        self.assertEqual([item["case_id"] for item in self.cases], CASE_IDS)
        self.assertEqual(self.cases[6]["expected_scope"], "IFRS9_IMPAIRMENT_AUTHORITY_BOUNDARY")
        self.assertEqual(self.cases[7]["expected_scope"], "OUT_OF_SCOPE_IFRS9_IMPAIRMENT")
        protocol = load_json(EVALUATION_DIR / "protocol_v1.json")
        self.assertEqual(protocol["dimensions"], list(DIMENSIONS))
        self.assertEqual(protocol["retrieval_benchmark"], {
            "questions": 50, "development": 12, "frozen_holdout": 38, "metrics_recomputed": False,
        })

    def test_invalid_count_duplicates_fields_and_types_rejected(self):
        variants = [self.cases[:-1], deepcopy(self.cases), deepcopy(self.cases), deepcopy(self.cases)]
        variants[1][1]["case_id"] = "S01"
        variants[2][0]["extra"] = "not allowed"
        variants[3][0]["expected_research_topics"] = "not a list"
        for cases in variants:
            with self.subTest(cases=cases[0]["case_id"]), self.assertRaises(ValueError):
                validate_cases(cases)

    def test_manifest_and_historical_files_match(self):
        manifest = validate_manifest()
        self.assertTrue(manifest["frozen_before_execution"])
        self.assertEqual(len(manifest["files"]), 3)
        self.assertIn("data/public_demo/historical_metrics_v01.json", manifest["protected_existing_files"])

    def test_manifest_detects_tampered_case_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            evaluation = Path(temporary)
            for name in ("freeze_manifest_v1.json", "cases_frozen_v1.json", "cases.schema.json", "protocol_v1.json"):
                (evaluation / name).write_bytes((EVALUATION_DIR / name).read_bytes())
            with (evaluation / "cases_frozen_v1.json").open("ab") as handle:
                handle.write(b" ")
            with self.assertRaisesRegex(ValueError, "Integrity mismatch"):
                validate_manifest(evaluation_dir=evaluation)

    def test_pending_review_is_not_a_pass_or_na(self):
        summary = summarise_manual_review(self.template)
        self.assertIsNone(summary["scenario_pass_count"])
        self.assertFalse(summary["manual_review_complete"])
        for rates in summary["per_dimension"].values():
            self.assertEqual(rates["pending"], 8)
            self.assertEqual(rates["not_applicable"], 0)
            self.assertIsNone(rates["pass_rate_excluding_na"])

    def test_mock_manual_rates_exclude_na_and_require_all_applicable_passes(self):
        # Synthetic judgements exercise aggregation; they are not actual case scores.
        reviews = deepcopy(self.template)
        for case in reviews:
            for judgement in case["dimensions"].values():
                judgement.update(status="PASS", reason="Synthetic aggregation test only")
        reviews[0]["dimensions"]["official_authority"]["status"] = "N/A"
        reviews[1]["dimensions"]["official_authority"]["status"] = "FAIL"
        summary = summarise_manual_review(reviews)
        rates = summary["per_dimension"]["official_authority"]
        self.assertEqual((rates["pass"], rates["fail"], rates["not_applicable"]), (6, 1, 1))
        self.assertAlmostEqual(rates["pass_rate_excluding_na"], 6 / 7)
        self.assertEqual(summary["scenario_pass_count"], 7)
        self.assertFalse(summary["per_case"][1]["scenario_pass"])
        self.assertNotIn("weighted_score", summary)

    def test_na_requires_reason_and_all_na_is_not_scenario_pass(self):
        reviews = deepcopy(self.template)
        for case in reviews:
            for judgement in case["dimensions"].values():
                judgement.update(status="N/A", reason="Synthetic inapplicability test")
        summary = summarise_manual_review(reviews)
        self.assertEqual(summary["scenario_pass_count"], 0)
        self.assertTrue(all(rate["pass_rate_excluding_na"] is None for rate in summary["per_dimension"].values()))
        reviews[0]["dimensions"]["safe_handoff"]["reason"] = ""
        with self.assertRaises(ValueError):
            summarise_manual_review(reviews)

    def test_all_cases_execute_offline_with_safe_evidence_and_no_mutation(self):
        report = run_offline()
        self.assertEqual(report["scenario_execution_count"], 8)
        self.assertEqual(report["live_model_runs"], 0)
        self.assertEqual(report["live_sec_calls"], 0)
        self.assertTrue(report["protected_existing_files_unchanged"])
        self.assertEqual(report["planner_input_tokens"] + report["planner_output_tokens"], 0)
        self.assertEqual(report["provider_cost_usd"], 0)
        self.assertEqual([item["case_id"] for item in report["observations"]], CASE_IDS)
        recorded = load_json(EVALUATION_DIR / "deterministic_observations_v1.json")
        if recorded["corpus_mode"] == report["corpus_mode"]:
            self.assertEqual(report, recorded)
        for observation in report["observations"]:
            run = observation["current_local_run"]
            self.assertLessEqual(run["step_count"], run["step_limit"])
            self.assertTrue(run["human_review_required"])
            self.assertFalse(observation["new_external_discovery_performed"])
            self.assertTrue(all("text" not in item for item in run["retrieved_evidence"]))
            self.assertFalse(observation["separated_handoff"]["company_disclosure_promoted_to_official_authority"])


if __name__ == "__main__":
    unittest.main()
