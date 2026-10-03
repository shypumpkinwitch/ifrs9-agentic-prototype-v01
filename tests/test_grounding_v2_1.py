"""Offline tests of qualification retention and the single-source retest boundary."""
import json
import unittest

from evaluations.final_improvement_v1.grounding.run_qualification_retest import (
    QUALIFICATION_RULE, prepare, compare,
)


class QualificationRetestTests(unittest.TestCase):
    def test_general_rule_is_not_case_specific(self):
        self.assertNotIn("EDU-FWD-003", QUALIFICATION_RULE)
        self.assertNotIn("without undue cost or effort", QUALIFICATION_RULE)
        for concept in ("qualifications", "conditions", "exceptions", "limitations"):
            self.assertIn(concept, QUALIFICATION_RULE)

    def test_single_original_question_and_approved_source(self):
        case, sources, body, audit = prepare()
        context = json.loads(body["messages"][1]["content"])
        selected = context["approved_educational_sources"]
        self.assertEqual([s["source_id"] for s in selected], ["EDU-FWD-003"])
        self.assertEqual(selected[0]["source_text"], sources["EDU-FWD-003"]["text"])
        self.assertEqual(context["question"], case["question"])
        self.assertEqual(body["model"], "openai/gpt-4o-mini")
        self.assertIn(QUALIFICATION_RULE, body["messages"][0]["content"])
        self.assertFalse(audit["raw_annual_report_text_included"])

    def test_omission_is_detected_without_claiming_human_review(self):
        source = "Information available without undue cost or effort."
        result = compare("Use information.", source, source)
        self.assertFalse(result["original_retains_qualification"])
        self.assertTrue(result["revised_retains_qualification"])
        self.assertIsNone(result["fully_supported_by_source"])
        self.assertEqual(result["independent_human_review_status"], "pending")


if __name__ == "__main__":
    unittest.main()
