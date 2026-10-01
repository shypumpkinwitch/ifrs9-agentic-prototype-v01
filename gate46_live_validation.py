from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.agent_loop_hardened import AgentResearchResult, run_bounded_agent
from src.agent_planner import OpenRouterPlanner, assert_safe_planner_payload
from src.private_runtime import default_private_bundle
from src.schemas import ResearchRequest
from src.source_registry import load_candidates, load_private_corpus_read_only


PROJECT_ROOT = Path(__file__).resolve().parent
PUBLIC_DATA = PROJECT_ROOT / "data" / "public_demo"
EXPECTED_MODEL = "openai/gpt-4o-mini"
GATE45_INPUT_TOKENS = 18664


CASES = [
    {
        "case_id": "G46-LIVE-PROPERTY-DEVELOPMENT-LOAN",
        "scenario": (
            "I am auditing a real-estate company that provides loans to property-development "
            "partners. I need IFRS 9 ECL research and comparable disclosures involving "
            "development loans, collateral, borrower financial condition, construction and "
            "leasing status, and significant increases in credit risk."
        ),
        "topic": "expected credit losses",
        "industry": "Property / REIT",
        "transaction_type": "development loans",
    },
    {
        "case_id": "G46-LIVE-GENERAL-BANKING-ECL",
        "scenario": (
            "A bank auditor needs comparable company disclosures for a general IFRS 9 ECL "
            "loan portfolio, including staging, probability of default, borrower credit risk, "
            "collateral, and portfolio methodology."
        ),
        "topic": "expected credit losses",
        "industry": "Banking",
        "transaction_type": "loan portfolio",
    },
    {
        "case_id": "G46-LIVE-UNSUPPORTED-AUTHORITATIVE-GUIDANCE",
        "scenario": (
            "Using the current research corpus, identify authoritative IFRS 9 requirements for "
            "expected credit losses. Company disclosures must not be treated as authoritative. "
            "If official IFRS evidence is unavailable, request that evidence and stop without "
            "fabricating a requirement."
        ),
        "topic": "authoritative IFRS 9 expected credit loss guidance",
        "industry": "",
        "transaction_type": "",
    },
]


def _request(case: dict[str, str]) -> ResearchRequest:
    return ResearchRequest(
        scenario=case["scenario"],
        topic=case["topic"],
        industry=case["industry"],
        transaction_type=case["transaction_type"],
        reporting_period="2025",
    )


def _intended_workflow(case_id: str, result: AgentResearchResult) -> dict[str, Any]:
    actions = [entry["action"] for entry in result.trace]
    comparisons = {item["company"]: item for item in result.comparability}
    authority_safe = (
        result.authority.get(
            "company_disclosure_can_establish_general_ifrs_requirements"
        )
        is False
    )
    if "PROPERTY" in case_id:
        allied = comparisons.get("Allied_REIT")
        passed = bool(
            allied
            and allied["rating"] == "strong"
            and "assess_comparability" in actions
            and "check_authority" in actions
            and authority_safe
        )
        explanation = (
            "Allied_REIT was assessed strong using the local dimensional evidence."
            if passed
            else "The run did not complete the required Allied_REIT comparability and authority workflow."
        )
    elif "BANKING" in case_id:
        rbc = comparisons.get("Royal Bank of Canada")
        passed = bool(
            rbc
            and rbc["rating"] == "strong"
            and "assess_comparability" in actions
            and "check_authority" in actions
            and authority_safe
        )
        explanation = (
            "Royal Bank of Canada was assessed strong for the banking ECL scenario."
            if passed
            else "The run did not complete the required RBC comparability and authority workflow."
        )
    else:
        requested_or_abstained = (
            "request_more_evidence" in actions
            or result.handoff.get("status") == "insufficient_evidence"
        )
        passed = bool(
            "check_authority" in actions
            and requested_or_abstained
            and authority_safe
            and not result.handoff.get("final_audit_judgment_provided")
        )
        explanation = (
            "The run checked authority, requested or abstained for official evidence, and did not fabricate a requirement."
            if passed
            else "The run did not complete the mandatory authority and abstention workflow."
        )
    return {"completed": passed, "assessment": explanation}


def _case_audit(
    case: dict[str, str], result: AgentResearchResult, planner: OpenRouterPlanner
) -> dict[str, Any]:
    planner_calls = []
    for event in planner.audit_events:
        planner_calls.append(
            {
                "call": event["request"]["request_number"],
                "available_tools": event["request"]["registered_tools"],
                "action": event["response"]["action"],
                "reason_summary": event["response"]["reason_summary"],
                "input_tokens": event["response"]["input_tokens"],
                "output_tokens": event["response"]["output_tokens"],
                "provider_reported_cost_available": event["response"][
                    "provider_reported_cost_available"
                ],
                "provider_reported_cost_usd": event["response"][
                    "provider_reported_cost_usd"
                ],
            }
        )
    return {
        "case_id": case["case_id"],
        "planner_model": result.planner_model,
        "planner_mode": result.mode,
        "live_model_completed_without_fallback": result.mode
        == "model-planned bounded agent",
        "state_transition_sequence": result.state_transition_sequence,
        "tool_call_sequence": [entry["action"] for entry in result.trace],
        "step_count": result.step_count,
        "step_limit": result.step_limit,
        "stop_reason": result.handoff.get("stop_reason"),
        "candidates": [
            {
                "company": item["company"],
                "framework_status": item["framework_status"],
                "evidence_status": item["evidence_status"],
            }
            for item in result.candidates
        ],
        "comparability_results": [
            {
                "company": item["company"],
                "rating": item["rating"],
                "weighted_score": item["weighted_score"],
                "dimension_scores": {
                    name: dimension["score"]
                    for name, dimension in item["dimensions"].items()
                },
                "explanation": item["comparability_explanation"],
                "caution": item["caution"],
            }
            for item in result.comparability
        ],
        "authority_result": result.authority,
        "missing_evidence": result.missing_evidence,
        "guardrails_triggered": result.guardrails_triggered,
        "usage": {
            "input_tokens": result.planner_input_tokens,
            "output_tokens": result.planner_output_tokens,
            "provider_reported_cost_available_for_every_call": all(
                event["response"]["provider_reported_cost_available"]
                for event in planner.audit_events
            ),
            "provider_reported_cost_usd": result.provider_cost_usd,
            "approximate_latency_ms": result.approximate_latency_ms,
        },
        "intended_workflow": _intended_workflow(case["case_id"], result),
        "planner_calls": planner_calls,
        "privacy_assertions": {
            "raw_annual_report_text_sent": False,
            "api_key_or_authorization_saved": False,
            "copyrighted_source_text_saved": False,
        },
    }


def main() -> None:
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise SystemExit("OPENROUTER_API_KEY is not available; no live run was attempted.")
    if os.getenv("OPENROUTER_MODEL", EXPECTED_MODEL) != EXPECTED_MODEL:
        raise SystemExit(f"OPENROUTER_MODEL must be {EXPECTED_MODEL}.")
    bundle = default_private_bundle(PROJECT_ROOT)
    chunks, _ = load_private_corpus_read_only(bundle / "working_corpus_v01.json")
    candidates = load_candidates(PUBLIC_DATA / "candidate_registry_v01.json")
    forbidden_texts = [chunk.text for chunk in chunks]
    audits = []
    for case in CASES:
        planner = OpenRouterPlanner.from_environment()
        if planner is None:
            raise RuntimeError("Planner environment changed during live validation.")
        result = run_bounded_agent(
            _request(case), chunks=chunks, candidates=candidates, planner=planner
        )
        if result.mode != "model-planned bounded agent":
            raise RuntimeError(
                f"{case['case_id']} was not a complete live run: {result.mode}"
            )
        for payload in planner.payloads:
            assert_safe_planner_payload(payload, forbidden_texts)
        if len(planner.payloads) != len(planner.audit_events):
            raise RuntimeError("A live planner response lacks sanitized audit metadata.")
        audits.append(_case_audit(case, result, planner))
    total_input = sum(case["usage"]["input_tokens"] for case in audits)
    total_output = sum(case["usage"]["output_tokens"] for case in audits)
    total_cost = sum(
        case["usage"]["provider_reported_cost_usd"] for case in audits
    )
    evidence = {
        "classification": (
            "Gate 4.6 live planner re-validation; separate from the frozen holdout, "
            "Gate 4 deterministic tests, and preserved Gate 4.5 failure evidence"
        ),
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "planner_model": EXPECTED_MODEL,
        "counted_live_cases": len(audits),
        "all_cases_completed_intended_workflow": all(
            case["intended_workflow"]["completed"] for case in audits
        ),
        "frozen_holdout_used_or_tuned": False,
        "external_web_discovery_performed": False,
        "api_key_saved": False,
        "raw_annual_report_text_sent": False,
        "aggregate_usage": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "provider_reported_cost_usd": total_cost,
        },
        "token_efficiency": {
            "gate45_input_tokens": GATE45_INPUT_TOKENS,
            "gate46_input_tokens": total_input,
            "absolute_reduction": GATE45_INPUT_TOKENS - total_input,
            "percentage_reduction": round(
                (GATE45_INPUT_TOKENS - total_input) / GATE45_INPUT_TOKENS * 100,
                2,
            ),
            "changes": [
                "Only state-valid tool contracts are sent on each step.",
                "Planner state contains only observations needed for the current transition.",
                "Static workflow sequencing moved from repeated prompt prose into the controller.",
            ],
        },
        "cases": audits,
    }
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
