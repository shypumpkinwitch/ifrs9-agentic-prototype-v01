from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.agent_loop import AgentResearchResult, run_bounded_agent
from src.agent_planner import (
    DeterministicFallbackPlanner,
    OpenRouterPlanner,
    assert_safe_planner_payload,
)
from src.private_runtime import default_private_bundle
from src.schemas import ResearchRequest
from src.source_registry import load_candidates, load_private_corpus_read_only


PROJECT_ROOT = Path(__file__).resolve().parent
PUBLIC_DATA = PROJECT_ROOT / "data" / "public_demo"
EXPECTED_MODEL = "openai/gpt-4o-mini"


CASES = [
    {
        "case_id": "G45-LIVE-PROPERTY-DEVELOPMENT-LOAN",
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
        "case_id": "G45-LIVE-GENERAL-BANKING-ECL",
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
        "case_id": "G45-LIVE-UNSUPPORTED-AUTHORITATIVE-GUIDANCE",
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


def _outcome_signature(result: AgentResearchResult) -> dict[str, Any]:
    return {
        "handoff_status": result.handoff.get("status"),
        "selected_candidates": result.handoff.get("selected_candidates", []),
        "comparability": {
            item["company"]: item["rating"] for item in result.comparability
        },
        "missing_evidence": sorted(result.missing_evidence),
        "final_audit_judgment_provided": result.handoff.get(
            "final_audit_judgment_provided"
        ),
    }


def _material_comparison(
    live: AgentResearchResult, fallback: AgentResearchResult
) -> dict[str, Any]:
    live_signature = _outcome_signature(live)
    fallback_signature = _outcome_signature(fallback)
    changed = [
        key
        for key in live_signature
        if live_signature[key] != fallback_signature[key]
    ]
    return {
        "materially_differs": bool(changed),
        "changed_outcome_fields": changed,
        "live_tool_sequence": [item["action"] for item in live.trace],
        "fallback_tool_sequence": [item["action"] for item in fallback.trace],
        "live_outcome": live_signature,
        "fallback_outcome": fallback_signature,
    }


def _case_audit(
    case: dict[str, str],
    live: AgentResearchResult,
    fallback: AgentResearchResult,
    planner: OpenRouterPlanner,
) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "scenario": case["scenario"],
        "planner_model": live.planner_model,
        "planner_mode": live.mode,
        "live_model_completed_without_fallback": live.mode
        == "model-planned bounded agent",
        "tool_call_sequence": [item["action"] for item in live.trace],
        "step_count": live.step_count,
        "step_limit": live.step_limit,
        "stop_reason": live.handoff.get("stop_reason"),
        "trace": [
            {
                "step": item["step"],
                "action": item["action"],
                "reason_summary": item["reason"],
                "result_summary": item["result_summary"],
            }
            for item in live.trace
        ],
        "candidate_companies": [
            {
                "company": item["company"],
                "framework_status": item["framework_status"],
                "evidence_status": item["evidence_status"],
            }
            for item in live.candidates
        ],
        "comparability_assessment": [
            {
                "company": item["company"],
                "rating": item["rating"],
                "weighted_score": item["weighted_score"],
                "dimension_scores": {
                    name: dimension["score"]
                    for name, dimension in item["dimensions"].items()
                },
                "caution": item["caution"],
            }
            for item in live.comparability
        ],
        "authority_warnings": {
            "required_message": live.authority.get("required_message"),
            "present_authority_classes": live.authority.get(
                "present_authority_classes", []
            ),
            "missing_authority_classes": live.authority.get(
                "missing_authority_classes", []
            ),
            "company_disclosure_can_establish_general_ifrs_requirements": live.authority.get(
                "company_disclosure_can_establish_general_ifrs_requirements"
            ),
            "handoff_authority_boundary": live.handoff.get("authority_boundary"),
        },
        "missing_evidence": live.missing_evidence,
        "guardrails_triggered": live.guardrails_triggered,
        "usage": {
            "input_tokens": live.planner_input_tokens,
            "output_tokens": live.planner_output_tokens,
            "provider_reported_cost_available_for_every_call": all(
                event["response"]["provider_reported_cost_available"]
                for event in planner.audit_events
            ),
            "provider_reported_cost_usd": live.provider_cost_usd,
            "approximate_latency_ms": live.approximate_latency_ms,
        },
        "comparison_with_deterministic_fallback": _material_comparison(
            live, fallback
        ),
        "sanitized_planner_exchanges": planner.audit_events,
        "privacy_assertions": {
            "outbound_payload_count": len(planner.payloads),
            "sanitized_exchange_count": len(planner.audit_events),
            "raw_annual_report_text_sent": False,
            "api_key_or_authorization_saved": False,
            "copyrighted_source_text_saved": False,
        },
    }


def main() -> None:
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise SystemExit("OPENROUTER_API_KEY is not available; no live run was attempted.")
    configured_model = os.getenv("OPENROUTER_MODEL", EXPECTED_MODEL)
    if configured_model != EXPECTED_MODEL:
        raise SystemExit(
            f"OPENROUTER_MODEL must be {EXPECTED_MODEL}; received a different model name."
        )

    bundle = default_private_bundle(PROJECT_ROOT)
    chunks, _ = load_private_corpus_read_only(bundle / "working_corpus_v01.json")
    candidates = load_candidates(PUBLIC_DATA / "candidate_registry_v01.json")
    forbidden_texts = [chunk.text for chunk in chunks]
    audits = []
    for case in CASES:
        planner = OpenRouterPlanner.from_environment()
        if planner is None:
            raise RuntimeError("Planner environment changed during live validation.")
        live = run_bounded_agent(
            _request(case), chunks=chunks, candidates=candidates, planner=planner
        )
        if live.mode != "model-planned bounded agent":
            raise RuntimeError(
                f"{case['case_id']} did not complete as a live model-planned run: {live.mode}"
            )
        for payload in planner.payloads:
            assert_safe_planner_payload(payload, forbidden_texts)
        if len(planner.payloads) != len(planner.audit_events):
            raise RuntimeError("A planner request is missing sanitized response metadata.")
        fallback = run_bounded_agent(
            _request(case),
            chunks=chunks,
            candidates=candidates,
            planner=DeterministicFallbackPlanner(),
        )
        audits.append(_case_audit(case, live, fallback, planner))

    evidence = {
        "classification": (
            "Gate 4.5 live planner development validation; separate from the frozen holdout "
            "and deterministic Gate 4 tests"
        ),
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "planner_model": EXPECTED_MODEL,
        "case_count": len(audits),
        "frozen_holdout_used_or_tuned": False,
        "external_web_discovery_performed": False,
        "api_key_saved": False,
        "raw_annual_report_text_sent": False,
        "cases": audits,
    }
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
