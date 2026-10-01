from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.final_submission import candidate_by_company, load_final_submission_snapshot
from src.release_audit import run_release_audit


class Gate6SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = load_final_submission_snapshot(PROJECT_ROOT)

    def test_flagship_snapshot_preserves_required_comparator_decisions(self):
        allied = candidate_by_company(self.snapshot, "Allied_REIT")
        lpa = candidate_by_company(self.snapshot, "Logistic Properties of the Americas")
        shinhan = candidate_by_company(self.snapshot, "SHINHAN FINANCIAL GROUP CO LTD")
        self.assertEqual(allied["comparability_rating"], "strong")
        self.assertEqual(allied["framework_status"], "PENDING_INSUFFICIENT_EVIDENCE")
        self.assertEqual(lpa["comparability_rating"], "partial")
        self.assertEqual(lpa["framework_status"], "IFRS_AS_ISSUED_BY_IASB_VERIFIED")
        self.assertTrue(shinhan["decision"].startswith("rejected"))

    def test_gate51_caveat_discloses_offline_only_hardening(self):
        caveat = self.snapshot["gate51_integrity_caveat"]
        self.assertFalse(caveat["second_live_run_performed"])
        self.assertFalse(caveat["live_checkpoint_overwritten"])
        self.assertIn("Shinhan", caveat["live_issue"])

    def test_historical_metrics_and_costs_are_exact_recorded_values(self):
        historical = self.snapshot["historical_retrieval"]
        self.assertEqual(historical["holdout_n"], 38)
        self.assertEqual(historical["bm25_hit_at_1"], 0.711)
        self.assertEqual(historical["bm25_hit_at_5"], 0.974)
        self.assertEqual(historical["semantic_hit_at_1"], 0.342)
        self.assertEqual(historical["semantic_hit_at_5"], 0.737)
        by_stage = {item["stage"]: item for item in self.snapshot["model_cost_summary"]}
        self.assertEqual(by_stage["Gate 4.5 live planner"]["input_tokens"], 18664)
        self.assertEqual(by_stage["Gate 4.6 live planner"]["provider_reported_api_cost_usd"], 0.00251685)
        self.assertEqual(by_stage["Gate 5 live discovery"]["input_tokens"], 39538)
        self.assertEqual(by_stage["Gate 5.1 live discovery"]["input_tokens"], 13345)
        self.assertEqual(self.snapshot["gate5_to_gate51_input_token_reduction"]["percent"], 66.25)

    def test_authority_boundary_and_human_review_remain_explicit(self):
        statuses = {item["authority_class"]: item["status"] for item in self.snapshot["authority_status"]}
        self.assertEqual(statuses["IFRS_FOUNDATION_OFFICIAL"], "missing_from_indexed_research_corpus")
        self.assertEqual(statuses["PROFESSIONAL_COMMENTARY"], "missing_from_indexed_research_corpus")
        self.assertTrue(self.snapshot["final_handoff"]["human_auditor_review_required"])
        self.assertFalse(self.snapshot["final_handoff"]["final_accounting_or_audit_judgment_provided"])

    def test_snapshot_contains_metadata_not_source_bodies(self):
        text = json.dumps(self.snapshot, ensure_ascii=False)
        self.assertNotIn("raw_filing_text", text)
        self.assertNotIn("annual_report_chunk_text", text)
        self.assertLess(len(text), 20000)

    def test_release_eligible_tree_passes_privacy_and_integrity_audit(self):
        result = run_release_audit(PROJECT_ROOT)
        self.assertEqual(result["status"], "pass", result["findings"])
        self.assertEqual(result["findings"], [])
        self.assertTrue(all(item["hash_matches"] for item in result["historical_artifact_checks"]))
        if result["private_frozen_integrity"]["status"] == "checked":
            self.assertEqual(result["private_frozen_integrity"]["record_count"], 76)
            self.assertEqual(result["private_frozen_integrity"]["unique_chunk_ids"], 76)


if __name__ == "__main__":
    unittest.main()
