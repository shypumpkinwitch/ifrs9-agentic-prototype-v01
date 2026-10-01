from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_loop_hardened import (  # noqa: E402
    AgentPolicyError,
    BoundedAgentController,
    run_bounded_agent,
)
from src.agent_planner import DeterministicFallbackPlanner, PlannerDecision  # noqa: E402
from src.agent_tools import LocalResearchTools  # noqa: E402
from src.private_runtime import default_private_bundle  # noqa: E402
from src.schemas import ResearchRequest  # noqa: E402
from src.source_registry import load_candidates, load_private_corpus_read_only  # noqa: E402


BUNDLE = default_private_bundle(PROJECT_ROOT)
PUBLIC = PROJECT_ROOT / "data" / "public_demo"


class RecordingFallbackPlanner(DeterministicFallbackPlanner):
    def __init__(self):
        self.menus = []

    def choose_next(self, state, tool_registry, remaining_steps, forbidden_texts):
        self.menus.append(
            {
                "state": state["workflow"]["current_state"],
                "tools": list(tool_registry),
            }
        )
        return super().choose_next(
            state, tool_registry, remaining_steps, forbidden_texts
        )


class NarrowingPlanner(DeterministicFallbackPlanner):
    def choose_next(self, state, tool_registry, remaining_steps, forbidden_texts):
        decision = super().choose_next(
            state, tool_registry, remaining_steps, forbidden_texts
        )
        if decision.tool == "assess_comparability":
            return PlannerDecision(
                decision.tool,
                {"companies": decision.arguments["companies"][:1]},
                "Attempt to assess only one inspected candidate.",
            )
        return decision


@unittest.skipUnless(BUNDLE.is_dir(), "Private Gate 4.6 corpus is not installed")
class Gate46StateMachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks, _ = load_private_corpus_read_only(
            BUNDLE / "working_corpus_v01.json"
        )
        cls.candidates = load_candidates(PUBLIC / "candidate_registry_v01.json")

    @staticmethod
    def flagship_request():
        return ResearchRequest(
            scenario=(
                "I am auditing a real-estate company that provides loans to property-development "
                "partners. I need IFRS 9 ECL research and comparable disclosures involving "
                "development loans, collateral, borrower financial condition, construction and "
                "leasing status, and significant increases in credit risk."
            ),
            topic="expected credit losses",
            industry="Property / REIT",
            transaction_type="development loans",
            reporting_period="2025",
        )

    def test_start_exposes_only_scenario_analysis(self):
        controller = BoundedAgentController(
            LocalResearchTools(self.chunks, self.candidates),
            max_steps=6,
            planner_mode="test",
        )
        state = {
            "request": {"scenario": self.flagship_request().scenario},
            "completed_tools": [],
            "observations": {},
        }
        self.assertEqual(
            list(controller.allowed_registry(state)), ["analyse_audit_scenario"]
        )

    def test_illegal_start_transition_is_blocked(self):
        controller = BoundedAgentController(
            LocalResearchTools(self.chunks, self.candidates),
            max_steps=6,
            planner_mode="test",
        )
        state = {
            "request": {"scenario": self.flagship_request().scenario},
            "completed_tools": [],
            "observations": {},
        }
        with self.assertRaisesRegex(AgentPolicyError, "Illegal state transition"):
            controller.execute(
                PlannerDecision(
                    "search_private_corpus",
                    {"query": "development loan ECL", "top_k": 5},
                    "Attempt to skip analysis.",
                ),
                state,
            )

    def test_duplicate_evidence_gap_signature_is_blocked(self):
        scenario = "A space-launch company asks about cryptographic token minting liabilities."
        controller = BoundedAgentController(
            LocalResearchTools(self.chunks, self.candidates),
            max_steps=6,
            planner_mode="test",
        )
        state = {
            "request": {"scenario": scenario},
            "completed_tools": [],
            "observations": {},
        }
        controller.execute(
            PlannerDecision(
                "analyse_audit_scenario", {"scenario": scenario}, "Analyse first."
            ),
            state,
        )
        gap = {
            "missing_authority_types": [],
            "missing_business_comparability_evidence": True,
            "missing_instrument_specific_evidence": True,
            "missing_reporting_framework_evidence": False,
        }
        controller.execute(
            PlannerDecision(
                "request_more_evidence",
                {
                    "gap": gap,
                    "evidence_types": ["clarified IFRS 9 question"],
                    "reason": "The scenario is outside the supported scope.",
                },
                "Record the evidence gap.",
            ),
            state,
        )
        with self.assertRaisesRegex(
            AgentPolicyError, "Duplicate unresolved evidence-gap signature"
        ):
            controller.execute(
                PlannerDecision(
                    "request_more_evidence",
                    {
                        "gap": gap,
                        "evidence_types": ["different wording"],
                        "reason": "The same unresolved gap with a different reason.",
                    },
                    "Repeat the gap.",
                ),
                state,
            )

    def test_comparable_workflow_requires_comparability_and_authority(self):
        planner = RecordingFallbackPlanner()
        result = run_bounded_agent(
            self.flagship_request(),
            chunks=self.chunks,
            candidates=self.candidates,
            planner=planner,
        )
        self.assertEqual(
            [entry["action"] for entry in result.trace],
            [
                "analyse_audit_scenario",
                "search_private_corpus",
                "inspect_candidate_metadata",
                "assess_comparability",
                "check_authority",
                "stop_and_summarise",
            ],
        )
        self.assertEqual(
            result.state_transition_sequence,
            [
                "START",
                "SCENARIO_ANALYSED",
                "EVIDENCE_SEARCHED",
                "CANDIDATES_INSPECTED",
                "COMPARABILITY_ASSESSED",
                "AUTHORITY_CHECKED",
                "READY_TO_STOP",
                "STOPPED",
            ],
        )
        self.assertTrue(all(len(menu["tools"]) == 1 for menu in planner.menus))
        self.assertEqual(
            {item["company"] for item in result.candidates},
            {item["company"] for item in result.comparability},
        )
        allied = next(
            item for item in result.comparability if item["company"] == "Allied_REIT"
        )
        self.assertEqual(allied["rating"], "strong")
        self.assertIn("Materially useful", allied["comparability_explanation"])
        self.assertIn("reporting_framework_status", allied["dimensions"])
        self.assertEqual(
            result.trace[-2]["action"], "check_authority"
        )

    def test_authoritative_request_checks_authority_then_requests_gap(self):
        result = run_bounded_agent(
            ResearchRequest(
                scenario=(
                    "Using the current corpus, identify authoritative IFRS 9 requirements for "
                    "expected credit losses. Company disclosure is not authoritative."
                ),
                topic="authoritative IFRS 9 expected credit loss guidance",
                reporting_period="2025",
            ),
            chunks=self.chunks,
            candidates=self.candidates,
            planner=DeterministicFallbackPlanner(),
        )
        self.assertEqual(
            [entry["action"] for entry in result.trace],
            [
                "analyse_audit_scenario",
                "search_private_corpus",
                "check_authority",
                "request_more_evidence",
                "stop_and_summarise",
            ],
        )
        self.assertFalse(
            result.authority[
                "company_disclosure_can_establish_general_ifrs_requirements"
            ]
        )
        self.assertIn("IFRS_FOUNDATION_OFFICIAL", result.missing_evidence)
        self.assertIn("EVIDENCE_GAP_IDENTIFIED", result.state_transition_sequence)

    def test_controller_binds_comparability_to_every_inspected_candidate(self):
        result = run_bounded_agent(
            self.flagship_request(),
            chunks=self.chunks,
            candidates=self.candidates,
            planner=NarrowingPlanner(),
        )
        self.assertEqual(
            {item["company"] for item in result.candidates},
            {item["company"] for item in result.comparability},
        )
        self.assertTrue(
            any(
                "bound comparability assessment" in item
                for item in result.guardrails_triggered
            )
        )

    def test_early_safe_abstention_still_works(self):
        result = run_bounded_agent(
            ResearchRequest(
                scenario="A space-launch company asks about cryptographic token minting liabilities.",
                topic="unrelated topic",
                industry="Aerospace",
                transaction_type="token",
            ),
            chunks=self.chunks,
            candidates=self.candidates,
            planner=DeterministicFallbackPlanner(),
        )
        self.assertEqual(result.step_count, 3)
        self.assertEqual(
            [entry["action"] for entry in result.trace],
            [
                "analyse_audit_scenario",
                "request_more_evidence",
                "stop_and_summarise",
            ],
        )
        self.assertEqual(result.handoff["status"], "insufficient_evidence")
        self.assertFalse(result.handoff["final_audit_judgment_provided"])


if __name__ == "__main__":
    unittest.main()
