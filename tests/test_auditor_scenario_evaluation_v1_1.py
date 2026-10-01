from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from evaluations.auditor_scenario_v1_1.run_deterministic import run_offline
from evaluations.auditor_scenario_v1_1.validation import (
    CASE_IDS, EVALUATION_DIR, PROJECT_ROOT, load_json, summarise_manual_review,
    validate_cases, validate_manifest,
)


class AuditorScenarioEvaluationV11Tests(unittest.TestCase):
    def setUp(self):
        self.cases = load_json(EVALUATION_DIR / "cases_frozen_v1_1.json")
        self.original = load_json(PROJECT_ROOT / "evaluations/auditor_scenario_v1/cases_frozen_v1.json")

    def test_only_authorised_case_fields_changed(self):
        expected = {
            "S03": {"scenario", "expected_research_topics", "expected_authority_behaviour"},
            "S04": {"scenario"}, "S06": {"expected_authority_behaviour"},
        }
        for before, after in zip(self.original, self.cases):
            changed = {field for field in before if before[field] != after[field]}
            self.assertEqual(changed, expected.get(before["case_id"], set()))

    def test_manufacturing_trade_receivable_correction(self):
        self.assertEqual(self.cases[2]["scenario"], (
            "A manufacturing company has a large portfolio of trade receivables. Overdue balances "
            "have increased and several major customers account for a significant share of the balance. "
            "The auditor wants to research the applicable IFRS 9 ECL requirements and how comparable "
            "manufacturers incorporate historical loss experience and forward-looking information into their disclosures."
        ))
        self.assertEqual(self.cases[2]["expected_research_topics"], [
            "trade-receivable ECL", "simplified approach / lifetime ECL",
            "historical loss experience or provision-matrix considerations",
            "forward-looking information / adjustment",
            "customer concentration and delinquency as relevant credit-risk information",
        ])
        self.assertIn(
            "Do not require SICR tracking as though the general approach necessarily applies.",
            self.cases[2]["expected_authority_behaviour"],
        )

    def test_banking_only_initial_recognition_wording_changed(self):
        self.assertEqual(
            self.cases[3]["scenario"],
            self.original[3]["scenario"].replace("since origination", "since initial recognition"),
        )
        self.assertEqual(
            {key: value for key, value in self.cases[3].items() if key != "scenario"},
            {key: value for key, value in self.original[3].items() if key != "scenario"},
        )

    def test_lease_policy_election_requires_authority_and_preserves_gap(self):
        behaviour = " ".join(self.cases[5]["expected_authority_behaviour"])
        self.assertIn("accounting-policy election", behaviour)
        self.assertIn("do not imply that the simplified approach is automatically mandatory", behaviour)
        self.assertIn("Seek sufficient official authority before concluding", behaviour)
        self.assertIn(self.original[5]["expected_authority_behaviour"][1], behaviour)

    def test_schema_and_case_ids(self):
        validate_cases(self.cases)
        self.assertEqual([case["case_id"] for case in self.cases], CASE_IDS)
        for invalid in (self.cases[:-1], deepcopy(self.cases)):
            if len(invalid) == 8:
                invalid[0]["expected_research_topics"] = "not a list"
            with self.assertRaises(ValueError):
                validate_cases(invalid)

    def test_freeze_and_protected_v1_application_historical_integrity(self):
        manifest = validate_manifest()
        self.assertTrue(manifest["frozen_before_execution"])
        self.assertFalse(manifest["live_execution_performed_before_refreeze"])
        self.assertEqual(manifest["version"], "1.1")
        self.assertEqual(manifest["parent_cases_sha256"],
                         "33087678fadd578e70e3b6c65327bbf2e2d9dc5ceb2462c2b1d7a8cd844cf31c")
        self.assertIn("app.py", manifest["protected_existing_files"])
        self.assertIn("evaluations/auditor_scenario_v1/readiness_hashes_v1.json", manifest["protected_existing_files"])

    def test_tampered_copy_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ("freeze_manifest_v1_1.json", "cases_frozen_v1_1.json", "cases.schema.json", "protocol_v1_1.json"):
                (directory / name).write_bytes((EVALUATION_DIR / name).read_bytes())
            with (directory / "cases_frozen_v1_1.json").open("ab") as handle:
                handle.write(b" ")
            with self.assertRaisesRegex(ValueError, "Integrity mismatch"):
                validate_manifest(evaluation_dir=directory)

    def test_deterministic_replay_zero_live_calls_cost_and_ungraded_template(self):
        report = run_offline()
        self.assertEqual(report, load_json(EVALUATION_DIR / "deterministic_observations_v1_1.json"))
        self.assertEqual(report["evaluation_id"], "auditor_scenario_evaluation_v1_1")
        self.assertEqual(report["scenario_execution_count"], 8)
        self.assertFalse(report["network_allowed"])
        for field in ("live_model_runs", "live_sec_calls", "planner_input_tokens", "planner_output_tokens", "provider_cost_usd"):
            self.assertEqual(report[field], 0)
        self.assertTrue(report["protected_existing_files_unchanged"])
        self.assertEqual(report["historical_retrieval"]["questions"], 50)
        self.assertEqual(report["historical_retrieval"]["development"], 12)
        self.assertEqual(report["historical_retrieval"]["frozen_holdout"], 38)
        for observation in report["observations"]:
            run = observation["current_local_run"]
            self.assertLessEqual(run["step_count"], 6)
            self.assertTrue(run["human_review_required"])
            self.assertTrue(all("text" not in item for item in run["retrieved_evidence"]))
            self.assertFalse(observation["new_external_discovery_performed"])
        summary = summarise_manual_review(load_json(EVALUATION_DIR / "manual_review_template_v1_1.json")["cases"])
        self.assertFalse(summary["manual_review_complete"])
        self.assertIsNone(summary["scenario_pass_count"])


if __name__ == "__main__":
    unittest.main()
