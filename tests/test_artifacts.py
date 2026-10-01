from __future__ import annotations

import csv
import hashlib
import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class ArtifactTests(unittest.TestCase):
    def test_historical_metrics_are_precomputed_and_unchanged_when_read(self):
        path = PROJECT_ROOT / "data" / "public_demo" / "historical_metrics_v01.json"
        before = path.read_bytes()
        payload = json.loads(before)
        after = path.read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(payload["status"], "precomputed_historical_fixed_corpus_results")
        self.assertEqual(payload["bm25"]["hit_at_1_count"], "27/38")
        self.assertEqual(payload["semantic"]["hit_at_5_count"], "28/38")

    def test_scenario_evaluation_has_five_development_cases(self):
        path = PROJECT_ROOT / "data" / "public_demo" / "scenario_eval_v01.json"
        scenarios = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(scenarios), 5)
        self.assertEqual(len({case["scenario_id"] for case in scenarios}), 5)
        self.assertTrue(all("not a blind holdout" in case["classification"] for case in scenarios))

    def test_gate4_evaluation_is_separate_and_has_five_development_cases(self):
        path = PROJECT_ROOT / "data" / "public_demo" / "gate4_scenario_eval_v01.json"
        scenarios = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(scenarios), 5)
        self.assertEqual(len({case["scenario_id"] for case in scenarios}), 5)
        self.assertTrue(all(case["scenario_id"].startswith("G4-") for case in scenarios))
        self.assertTrue(all("not a frozen holdout" in case["classification"] for case in scenarios))

    def test_gate4_recorded_trace_contains_no_private_source_body(self):
        path = PROJECT_ROOT / "docs" / "GATE4_FLAGSHIP_TRACE_v01.json"
        trace = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(trace["step_count"], 6)
        self.assertFalse(trace["model_call_made"])
        self.assertFalse(trace["private_source_text_in_trace"])
        self.assertTrue(all("text" not in item for item in trace["selected_evidence"]))

    def test_gate45_live_audit_is_sanitized_and_separate(self):
        audit_path = PROJECT_ROOT / "docs" / "GATE45_LIVE_PLANNER_AUDIT_v01.json"
        audit_text = audit_path.read_text(encoding="utf-8")
        audit = json.loads(audit_text)
        self.assertEqual(audit["planner_model"], "openai/gpt-4o-mini")
        self.assertEqual(audit["counted_live_cases"], 3)
        self.assertEqual(audit["overall_acceptance"], "partial_failure")
        self.assertFalse(audit["frozen_holdout_used_or_tuned"])
        self.assertFalse(audit["api_key_saved"])
        self.assertFalse(audit["raw_annual_report_text_sent"])
        self.assertEqual(audit["aggregate_usage"]["input_tokens"], 18664)
        self.assertEqual(audit["aggregate_usage"]["output_tokens"], 1079)
        corpus_path = (
            PROJECT_ROOT
            / "private_data"
            / "runtime_inputs_v01"
            / "PE6201_Codex_Private_Runtime_Inputs_v01"
            / "working_corpus_v01.json"
        )
        if corpus_path.is_file():
            corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
            for record in corpus:
                self.assertNotIn(record["text"], audit_text)

    def test_gate45_failure_artifacts_remain_byte_identical(self):
        expected = {
            "GATE45_LIVE_PLANNER_AUDIT_v01.json": "b598918f9bcf50ad091356d60ab6c91ab9fe82ce61c6e1a8c0bafddbcb8dad35",
            "GATE45_LIVE_PLANNER_RESULTS_v01.md": "ca3f57f3edaea6496e9adade4f129f28e146db2932147d988d6fa3eb51d12213",
        }
        for name, digest in expected.items():
            with self.subTest(name=name):
                actual = hashlib.sha256((PROJECT_ROOT / "docs" / name).read_bytes()).hexdigest()
                self.assertEqual(actual, digest)

    def test_gate46_live_audit_is_sanitized_and_successful(self):
        audit_path = PROJECT_ROOT / "docs" / "GATE46_LIVE_PLANNER_AUDIT_v01.json"
        audit_text = audit_path.read_text(encoding="utf-8")
        audit = json.loads(audit_text)
        self.assertEqual(audit["planner_model"], "openai/gpt-4o-mini")
        self.assertEqual(audit["counted_live_cases"], 3)
        self.assertTrue(audit["all_cases_completed_intended_workflow"])
        self.assertFalse(audit["frozen_holdout_used_or_tuned"])
        self.assertFalse(audit["external_web_discovery_performed"])
        self.assertFalse(audit["api_key_saved"])
        self.assertFalse(audit["raw_annual_report_text_sent"])
        self.assertEqual(audit["aggregate_usage"]["input_tokens"], 11987)
        self.assertEqual(audit["aggregate_usage"]["output_tokens"], 1342)
        self.assertEqual(audit["token_efficiency"]["percentage_reduction"], 35.77)
        self.assertTrue(
            all(case["intended_workflow"]["completed"] for case in audit["cases"])
        )
        corpus_path = (
            PROJECT_ROOT
            / "private_data"
            / "runtime_inputs_v01"
            / "PE6201_Codex_Private_Runtime_Inputs_v01"
            / "working_corpus_v01.json"
        )
        if corpus_path.is_file():
            corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
            for record in corpus:
                self.assertNotIn(record["text"], audit_text)

    def test_gate5_live_audit_is_bounded_sanitized_and_separate(self):
        audit_path = PROJECT_ROOT / "docs" / "GATE5_LIVE_DISCOVERY_AUDIT_v01.json"
        audit_text = audit_path.read_text(encoding="utf-8")
        audit = json.loads(audit_text)
        self.assertEqual(audit["planner_model"], "openai/gpt-4o-mini")
        self.assertTrue(audit["live_model_completed_without_fallback"])
        self.assertTrue(audit["single_counted_live_run"])
        self.assertEqual(audit["limits"]["candidates_discovered"], 3)
        self.assertEqual(audit["limits"]["annual_filings_downloaded"], 2)
        self.assertEqual(audit["limits"]["agent_tool_steps_used"], 10)
        self.assertEqual(len(audit["external_requests"]), 7)
        self.assertTrue(all(item["status"] == "success" for item in audit["external_requests"]))
        self.assertEqual(audit["planner_usage"]["input_tokens"], 39538)
        self.assertEqual(audit["planner_usage"]["output_tokens"], 1284)
        self.assertFalse(audit["privacy_assertions"]["raw_private_corpus_text_sent_to_planner"])
        self.assertFalse(audit["privacy_assertions"]["raw_external_filing_text_sent_to_planner"])
        self.assertFalse(audit["evaluation_boundaries"]["frozen_holdout_used_or_tuned"])
        self.assertFalse(audit["evaluation_boundaries"]["external_documents_added_to_frozen_corpus"])
        self.assertFalse(audit["evaluation_boundaries"]["gate6_started"])
        self.assertEqual(
            {item["status"] for item in audit["reporting_framework_verification"]},
            {"US_GAAP", "PENDING_INSUFFICIENT_EVIDENCE"},
        )
        corpus_path = (
            PROJECT_ROOT
            / "private_data"
            / "runtime_inputs_v01"
            / "PE6201_Codex_Private_Runtime_Inputs_v01"
            / "working_corpus_v01.json"
        )
        if corpus_path.is_file():
            for record in json.loads(corpus_path.read_text(encoding="utf-8")):
                self.assertNotIn(record["text"], audit_text)
        raw_root = PROJECT_ROOT / "external_runtime" / "gate5_live_v01" / "raw"
        if raw_root.is_dir():
            for path in raw_root.rglob("*"):
                if path.is_file():
                    self.assertNotIn(path.read_text(encoding="utf-8"), audit_text)

    def test_gate51_live_audit_is_ifrs_targeted_sanitized_and_honest(self):
        path = PROJECT_ROOT / "docs" / "GATE51_LIVE_DISCOVERY_AUDIT_v01.json"
        audit_text = path.read_text(encoding="utf-8")
        audit = json.loads(audit_text)
        self.assertEqual(audit["planner_model"], "openai/gpt-4o-mini")
        self.assertTrue(audit["live_model_completed_without_fallback"])
        self.assertTrue(audit["single_live_run"])
        self.assertEqual(audit["required_reporting_framework"], "IFRS")
        self.assertEqual(audit["limits"]["candidates_discovered"], 3)
        self.assertEqual(audit["limits"]["agent_tool_steps_used"], 10)
        self.assertEqual(audit["limits"]["external_request_count"], 8)
        self.assertTrue(
            all(
                item["framework_status"] == "IFRS_AS_ISSUED_BY_IASB_VERIFIED"
                for item in audit["candidate_results"]
            )
        )
        accepted = [
            item for item in audit["candidate_results"]
            if item["final_gate51_decision"] == "accepted"
        ]
        self.assertEqual([item["company"] for item in accepted], ["Logistic Properties of the Americas"])
        self.assertEqual(accepted[0]["final_gate51_rating"], "partial")
        self.assertTrue(audit["live_integrity_review"]["material_issue_detected"])
        self.assertFalse(audit["live_integrity_review"]["live_output_overwritten"])
        self.assertEqual(audit["planner_usage"]["gate51_input_tokens"], 13345)
        self.assertEqual(audit["planner_usage"]["input_token_reduction_percent"], 66.25)
        self.assertEqual(
            audit["allied_reit_framework_verification"]["status"],
            "PENDING_INSUFFICIENT_EVIDENCE",
        )
        self.assertFalse(audit["evaluation_boundaries"]["gate6_started"])
        corpus_path = (
            PROJECT_ROOT
            / "private_data"
            / "runtime_inputs_v01"
            / "PE6201_Codex_Private_Runtime_Inputs_v01"
            / "working_corpus_v01.json"
        )
        if corpus_path.is_file():
            for record in json.loads(corpus_path.read_text(encoding="utf-8")):
                self.assertNotIn(record["text"], audit_text)
        raw_root = PROJECT_ROOT / "external_runtime" / "gate51_live_v01" / "raw"
        if raw_root.is_dir():
            for raw_path in raw_root.rglob("*"):
                if raw_path.is_file():
                    self.assertNotIn(raw_path.read_text(encoding="utf-8"), audit_text)

    def test_grounding_review_is_empty_and_pending_real_generation(self):
        path = PROJECT_ROOT / "docs" / "GENERATION_GROUNDING_REVIEW_v01.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 1)
        self.assertIn("independent_human_review_status", rows[0])


if __name__ == "__main__":
    unittest.main()
