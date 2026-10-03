from __future__ import annotations

import json
import unittest
from pathlib import Path

from evaluations.final_improvement_v1.grounding.run_grounding_evaluation import (
    ABSTENTION,
    build_request,
    run as run_grounding,
    structural_checks,
    validate_sources,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_ROOT = PROJECT_ROOT / "evaluations" / "final_improvement_v1"


class FinalImprovementEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = json.loads(
            (EVALUATION_ROOT / "grounding" / "educational_sources_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.cases = json.loads(
            (EVALUATION_ROOT / "grounding" / "cases_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.by_id = validate_sources(self.sources)

    def test_grounding_sources_are_self_authored_and_not_company_or_standard_text(self):
        self.assertEqual(len(self.by_id), 4)
        self.assertEqual(
            {source["authority_level"] for source in self.sources},
            {"PROJECT_EDUCATIONAL_NOTE"},
        )
        invalid = dict(self.sources[0], authority_level="COMPANY_DISCLOSURE")
        with self.assertRaisesRegex(ValueError, "Only project educational notes"):
            validate_sources([invalid])

    def test_payload_uses_only_selected_notes_and_blocks_private_text(self):
        case = self.cases[0]
        body, audit = build_request(case, self.by_id, forbidden_texts=[])
        serialized = json.dumps(body)
        self.assertIn(case["source_ids"][0], serialized)
        for source in self.sources[1:]:
            self.assertNotIn(source["text"], serialized)
        self.assertFalse(audit["raw_annual_report_text_included"])
        self.assertFalse(audit["raw_ifrs_source_text_included"])
        selected_text = self.by_id[case["source_ids"][0]]["text"]
        with self.assertRaisesRegex(ValueError, "annual-report text"):
            build_request(case, self.by_id, forbidden_texts=[selected_text])

    def test_structural_checks_are_not_manual_grounding_review(self):
        sufficient = self.cases[0]
        check = structural_checks(
            "A bounded answer. [EDU-ECL-001]", sufficient, set(self.by_id)
        )
        self.assertTrue(check["structural_pass"])
        self.assertIn("not a factual-grounding judgement", check["scope_note"])
        insufficient = self.cases[-1]
        check = structural_checks(ABSTENTION, insufficient, set(self.by_id))
        self.assertTrue(check["structural_pass"])

    def test_mocked_six_case_run_records_responses_citations_usage_and_pending_review(self):
        def transport(body, headers):
            self.assertIn("Authorization", headers)
            context = json.loads(body["messages"][1]["content"])
            source_ids = [
                source["source_id"]
                for source in context["approved_educational_sources"]
            ]
            text = (
                f"A bounded answer. [{source_ids[0]}]"
                if source_ids and "exact" not in context["question"].lower()
                else ABSTENTION
            )
            return {
                "id": "mock-response",
                "model": "mock-model",
                "choices": [
                    {"message": {"content": text}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "cost": 0.00001},
            }

        result, checklist = run_grounding(
            "mock-key", transport=transport, forbidden_texts=[]
        )
        self.assertEqual(result["cases"], 6)
        self.assertEqual(result["automated_structural_pass_count"], 6)
        self.assertEqual(result["aggregate_usage"]["model_calls"], 6)
        self.assertEqual(result["aggregate_usage"]["input_tokens"], 60)
        self.assertEqual(len(checklist), 6)
        self.assertEqual(
            {item["manual_review_status"] for item in checklist},
            {"pending_human_review"},
        )
        self.assertIsNone(result["manual_factual_grounding_pass_count"])

    def test_saved_retrieval_result_is_development_only_and_contains_no_source_text(self):
        result = json.loads(
            (EVALUATION_ROOT / "retrieval_dev" / "results_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result["inputs"]["development_questions"], 12)
        self.assertFalse(result["frozen_holdout_accessed"])
        self.assertFalse(result["frozen_holdout_tuned"])
        self.assertFalse(result["production_retriever_changed"])
        self.assertNotIn('"text"', json.dumps(result))

    def test_live_grounding_artifact_keeps_structural_and_manual_results_separate(self):
        result = json.loads(
            (EVALUATION_ROOT / "grounding" / "live_results_v1.json").read_text(
                encoding="utf-8"
            )
        )
        checklist = json.loads(
            (EVALUATION_ROOT / "grounding" / "manual_review_checklist_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result["cases"], 6)
        self.assertEqual(len(result["records"]), 6)
        self.assertEqual(result["automated_structural_pass_count"], 6)
        self.assertIsNone(result["manual_factual_grounding_pass_count"])
        self.assertEqual(result["manual_review_status"], "pending_human_review")
        self.assertEqual(len(checklist), 6)
        self.assertTrue(all(item["model_response"] for item in result["records"]))
        self.assertFalse(result["privacy"]["raw_annual_report_text_sent"])
        self.assertFalse(result["privacy"]["raw_ifrs_source_text_sent"])

    def test_cost_ledger_distinguishes_calls_scenarios_and_zero_cost_fallback(self):
        ledger = json.loads(
            (EVALUATION_ROOT / "cost" / "cost_ledger_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(ledger["pricing_assumptions_used"])
        self.assertFalse(ledger["estimated_savings_reported"])
        self.assertEqual(ledger["per_model_call"]["record_count"], 36)
        self.assertTrue(
            all(item["matches"] for item in ledger["call_to_scenario_reconciliation"])
        )
        gate5_rows = [
            item
            for item in ledger["per_research_scenario"]["records"]
            if item["stage"] in {"Gate 5 live discovery", "Gate 5.1 live discovery"}
        ]
        self.assertEqual(len(gate5_rows), 2)
        self.assertTrue(all(item["model_call_count"] is None for item in gate5_rows))
        self.assertTrue(
            all(
                item["provider_reported_cost_usd"] == 0
                and item["model_calls"] == 0
                for item in ledger["deterministic_fallback"]
            )
        )


if __name__ == "__main__":
    unittest.main()
