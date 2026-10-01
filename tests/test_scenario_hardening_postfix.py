from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluations.scenario_hardening_postfix_v1.run_postfix_offline import run_postfix, verify_protected_artifacts
from src.agent_loop_hardened import run_bounded_agent
from src.agent_planner import DeterministicFallbackPlanner, OpenRouterPlanner, assert_safe_planner_payload
from src.agent_tools import extract_local_features
from src.authority_registry import build_separated_research_handoff, identify_ifrs9_research_topics, load_authority_registry, retrieve_authority_cards
from src.private_runtime import default_private_bundle
from src.schemas import ResearchRequest
from src.source_registry import load_candidates, load_private_corpus_read_only

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data/public_demo"


class ScenarioHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_postfix()
        cls.after = {item["case_id"]: item["after"] for item in cls.report["observations"]}
        cls.cards = load_authority_registry(PUBLIC / "ifrs_authority_registry_v01.json")

    def test_s01_supported_property_evidence_retained(self):
        after = self.after["S01"]
        self.assertEqual(after["selected_candidates"][0]["company"], "Allied_REIT")
        self.assertEqual(after["selected_candidates"][0]["rating"], "strong")
        self.assertFalse(after["authority_coverage"]["instrument_specific_authority_gaps"])
        self.assertTrue({41, 132, 150}.issubset({item["pdf_page"] for item in after["run"]["retrieved_evidence"]}))

    def test_s04_supported_banking_evidence_retained(self):
        after = self.after["S04"]
        self.assertEqual(after["selected_candidates"][0]["company"], "Royal Bank of Canada")
        self.assertTrue(all(item["company"] == "Royal Bank of Canada" for item in after["run"]["retrieved_evidence"]))
        self.assertTrue(all(item["rating"] != "strong" for item in after["run"]["comparability"] if item["company"] == "Allied_REIT"))

    def test_s02_s03_trade_receivable_gap_not_general_sicr_requirement(self):
        for case in ("S02", "S03"):
            with self.subTest(case=case):
                after = self.after[case]
                self.assertEqual(after["scenario_routing"]["instrument"], "trade_receivables")
                self.assertIn("simplified-approach / lifetime-ECL", " ".join(after["authority_coverage"]["instrument_specific_authority_gaps"]))
                self.assertNotIn("IFRS9-AUTH-SICR-004", after["authority_ids"])
                self.assertNotIn("IFRS9-AUTH-STAGING-003", after["authority_ids"])
                self.assertEqual(after["selected_candidates"], [])
                self.assertIn("Abstain", after["abstention"])

    def test_s05_debt_investment_scope_gap_and_no_loan_comparator(self):
        after = self.after["S05"]
        self.assertEqual(after["scenario_routing"]["instrument"], "debt_investments")
        self.assertIn("debt-investment", " ".join(after["authority_coverage"]["instrument_specific_authority_gaps"]))
        self.assertEqual(after["selected_candidates"], [])

    def test_s06_lease_policy_election_gap_no_false_strong_match(self):
        after = self.after["S06"]
        self.assertIn("accounting-policy election", " ".join(after["authority_coverage"]["instrument_specific_authority_gaps"]))
        self.assertEqual(after["selected_candidates"], [])
        self.assertTrue(all(item["rating"] != "strong" for item in after["run"]["comparability"]))

    def test_s07_guarantee_commitment_scope_gap_no_generic_comparator(self):
        after = self.after["S07"]
        self.assertEqual(after["scenario_routing"]["instrument"], "guarantees_commitments")
        self.assertIn("guarantee", " ".join(after["authority_coverage"]["instrument_specific_authority_gaps"]))
        self.assertEqual(after["selected_candidates"], [])

    def test_s08_clean_scope_stop_no_cards_search_or_snapshot(self):
        after = self.after["S08"]
        self.assertEqual(after["scenario_routing"]["scope_status"], "out_of_scope")
        self.assertEqual(after["authority_ids"], [])
        self.assertEqual(after["selected_candidates"], [])
        self.assertNotIn("search_private_corpus", [item["action"] for item in after["run"]["trace"]])
        self.assertIn("different accounting-standard", after["abstention"])
        self.assertFalse(after["recorded_snapshot_attached"])
        self.assertEqual(after["run"]["missing_evidence"], ["different accounting-standard research scope"])

    def test_independent_wording_and_business_uncertainty(self):
        variations = [
            ("A REIT finances construction partners through secured project lending; investigate expected credit losses.", "development_loans"),
            ("A real estate developer extends a credit loan to a development partner and needs impairment research.", "development_loans"),
            ("An industrial producer has overdue trade debtors and wants forecast-adjusted historical credit-loss research.", "trade_receivables"),
            ("An online marketplace has accounts receivable from sellers and seeks impairment research.", "trade_receivables"),
            ("A credit institution reviews increased default risk on its corporate lending portfolio.", "banking_loans"),
            ("A bank reviews overdue corporate loans and lifetime expected credit losses.", "banking_loans"),
            ("Treasury holds bond investments at amortized cost and researches impairment.", "debt_investments"),
            ("Research amortised-cost debt securities held by a treasury department.", "debt_investments"),
            ("A lessor holds rental receivables and researches credit losses.", "lease_receivables"),
            ("Research impairment of leasing receivables at a property manager.", "lease_receivables"),
            ("An entity provides credit guarantees and undrawn credit facilities; investigate impairment scope.", "guarantees_commitments"),
            ("Research unfunded loan commitments and financial guarantees.", "guarantees_commitments"),
        ]
        for scenario, expected in variations:
            with self.subTest(scenario=scenario):
                self.assertEqual(ResearchRequest(scenario=scenario).scenario_routing()["instrument"], expected)
        self.assertEqual(ResearchRequest(scenario="A treasury department holds a loan portfolio.").scenario_routing()["business_category"], "treasury")

    def test_topic_and_hints_cannot_override_out_of_scope(self):
        for scenario in ("How should we recognise revenue from online sales?", "Research revenue recognition for a marketplace."):
            request = ResearchRequest(scenario=scenario, topic="expected credit losses", industry="Property / REIT", transaction_type="development loans")
            self.assertFalse(request.scenario_routing()["in_scope"])
            self.assertTrue(request.scenario_routing()["selected_topic_conflict"])
            self.assertEqual(identify_ifrs9_research_topics(request), [])
            self.assertEqual(retrieve_authority_cards(self.cards, []), [])
        mixed = ResearchRequest(scenario="Research revenue recognition and impairment of trade receivables.")
        self.assertEqual(mixed.scenario_routing()["scope_status"], "clarification_required")

    def test_handoff_defence_filters_forged_scope_leakage(self):
        request = ResearchRequest(scenario="Research revenue recognition.", topic="expected credit losses")
        handoff = build_separated_research_handoff(self.cards, {
            "selected_candidates": [{"company": "Allied_REIT"}],
            "evidence": [{"company": "Allied_REIT"}], "missing_evidence": [],
        }, [{"company": "Property Issuer", "comparability_rating": "strong", "decision": "retain", "rationale": "Old snapshot"}], request=request)
        self.assertEqual(handoff["What official IFRS sources indicate"], [])
        company = handoff["How comparable companies disclosed similar exposures"]
        self.assertEqual(company["recorded_comparable_summaries"], [])
        self.assertEqual(company["current_company_disclosure_handoff"]["evidence"], [])

    def test_exposure_evidence_not_created_by_generic_ecl_cooccurrence(self):
        features = extract_local_features("A property company describes ECL on trade receivables and leasing operations.", "Issuer")
        self.assertFalse(features["development_loan"])
        self.assertFalse(features["lease_receivables"])
        self.assertTrue(features["trade_receivables"])

    def test_caps_safe_exports_original_artifacts_and_no_unseen_score_claim(self):
        self.assertTrue(self.report["protected_artifacts_unchanged"])
        self.assertFalse(self.report["manual_scenario_scores_assigned"])
        verify_protected_artifacts()
        for observation in self.report["observations"]:
            after = observation["after"]
            self.assertLessEqual(after["steps"], 6)
            self.assertFalse(after["recorded_snapshot_attached"])
            self.assertTrue(after["run"]["human_review_required"])
            self.assertTrue(all("text" not in item for item in after["run"]["retrieved_evidence"]))
            self.assertEqual(after["separated_handoff"]["How comparable companies disclosed similar exposures"]["recorded_comparable_summaries"], [])
        for metric in ("live_openrouter_calls", "live_sec_calls", "planner_input_tokens", "planner_output_tokens", "provider_cost_usd"):
            self.assertEqual(self.report[metric], 0)

    def test_mock_model_payloads_contain_structured_authority_not_source_text(self):
        chunks, _ = load_private_corpus_read_only(default_private_bundle(ROOT) / "working_corpus_v01.json")
        candidates = load_candidates(PUBLIC / "candidate_registry_v01.json")
        payloads = []
        fallback = DeterministicFallbackPlanner()

        def transport(body, headers, endpoint):
            context = assert_safe_planner_payload(body, [chunk.text for chunk in chunks])
            payloads.append(body)
            decision = fallback.choose_next(context["research_state"], context["tools"], context["remaining_steps"], [])
            return {"choices": [{"message": {"content": json.dumps({"tool": decision.tool, "arguments": decision.arguments, "reason": decision.reason})}}], "usage": {}}

        result = run_bounded_agent(ResearchRequest(scenario="A property company lends secured development loans and needs ECL disclosures."), chunks=chunks, candidates=candidates, planner=OpenRouterPlanner("mock-key", transport=transport))
        self.assertEqual(result.step_count, 6)
        serialized = json.dumps(payloads)
        self.assertIn("official_authority_cards", serialized)
        for chunk in chunks:
            self.assertNotIn(chunk.text, serialized)
        self.assertNotIn("mock-key", json.dumps(result.safe_export()))


class ScopePresentationTests(unittest.TestCase):
    @patch.dict("os.environ", {"OPENROUTER_API_KEY": ""})
    def test_revenue_ui_has_no_ecl_cards_or_property_snapshot(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
        app.text_area[0].input("Research revenue recognition for an e-commerce company.")
        app.selectbox[0].set_value("expected credit losses")
        app.button[0].click().run(timeout=30)
        self.assertEqual(list(app.exception), [])
        visible = "\n".join(str(item.value) for group in (app.markdown, app.caption, app.warning, app.info) for item in group)
        self.assertIn("Scope mismatch", visible)
        self.assertNotIn("Allied_REIT", visible)
        self.assertNotIn("Logistic Properties", visible)
        self.assertNotIn("IFRS9-AUTH-", visible)
        self.assertEqual(len(app.tabs[8].json), 0)
        self.assertFalse(any("Gate 5.1" in item.label for item in app.tabs[9].expander))

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": ""})
    def test_lease_ui_surfaces_election_gap_and_no_flagship_history(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
        app.text_area[0].input("A property manager has lease receivables and needs impairment research.")
        app.button[0].click().run(timeout=30)
        self.assertEqual(list(app.exception), [])
        handoff = app.tabs[8]
        visible = "\n".join(str(item.value) for group in (handoff.markdown, handoff.warning, handoff.info) for item in group)
        self.assertIn("accounting-policy election", visible)
        self.assertIn("No verified suitable comparator", visible)
        self.assertNotIn("Allied_REIT", visible)
        self.assertNotIn("Logistic Properties", visible)


if __name__ == "__main__":
    unittest.main()
