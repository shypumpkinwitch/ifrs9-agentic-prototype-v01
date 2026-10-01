from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.agent_planner import OpenRouterPlanner, assert_safe_planner_payload
from src.external_discovery import SecEdgarClient, extract_visible_text
from src.external_discovery_ifrs import run_gate51_discovery
from src.private_runtime import default_private_bundle
from src.schemas import ResearchRequest
from src.source_registry import hash_file, load_candidates, load_private_corpus_read_only


PROJECT_ROOT = Path(__file__).resolve().parent
PUBLIC = PROJECT_ROOT / "data" / "public_demo"
RUNTIME = PROJECT_ROOT / "external_runtime" / "gate51_live_v01"
EXPECTED_MODEL = "openai/gpt-4o-mini"
GATE5_INPUT_TOKENS = 39538
GATE5_COST_USD = 0.0067011


def flagship_request() -> ResearchRequest:
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


def main() -> None:
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise SystemExit("OPENROUTER_API_KEY is unavailable; no live run was attempted.")
    if not os.getenv("SEC_USER_AGENT", "").strip():
        raise SystemExit("SEC_USER_AGENT is unavailable; no live run was attempted.")
    if os.getenv("OPENROUTER_MODEL", EXPECTED_MODEL) != EXPECTED_MODEL:
        raise SystemExit(f"OPENROUTER_MODEL must be {EXPECTED_MODEL}.")

    bundle = default_private_bundle(PROJECT_ROOT)
    chunks, _ = load_private_corpus_read_only(bundle / "working_corpus_v01.json")
    candidates = load_candidates(PUBLIC / "candidate_registry_v01.json")
    protected = [
        *[path for path in bundle.iterdir() if path.is_file()],
        PROJECT_ROOT / "docs" / "GATE45_LIVE_PLANNER_AUDIT_v01.json",
        PROJECT_ROOT / "docs" / "GATE45_LIVE_PLANNER_RESULTS_v01.md",
        PROJECT_ROOT / "docs" / "GATE46_LIVE_REVALIDATION_ATTEMPT1_v01.json",
        PROJECT_ROOT / "docs" / "GATE46_LIVE_PLANNER_AUDIT_v01.json",
        PROJECT_ROOT / "docs" / "GATE46_HARDENING_RESULTS_v01.md",
        PROJECT_ROOT / "docs" / "GATE5_LIVE_DISCOVERY_AUDIT_v01.json",
        PROJECT_ROOT / "docs" / "GATE5_RESULTS_v01.md",
    ]
    before = {str(path): hash_file(path) for path in protected}
    planner = OpenRouterPlanner.from_environment()
    if planner is None:
        raise RuntimeError("Planner environment changed before the live run.")
    sec = SecEdgarClient.from_environment()
    result = run_gate51_discovery(
        flagship_request(),
        private_chunks=chunks,
        local_candidates=candidates,
        sec_client=sec,
        runtime_root=RUNTIME,
        jurisdiction_context_path=PUBLIC / "ifrs_jurisdiction_context_v01.json",
        planner=planner,
        max_steps=10,
    )
    after = {str(path): hash_file(path) for path in protected}
    if before != after:
        raise RuntimeError("A protected frozen or accepted-gate artifact changed during Gate 5.1.")

    external_texts = []
    raw_root = RUNTIME / "raw"
    for path in raw_root.rglob("*") if raw_root.is_dir() else []:
        if path.is_file():
            body = path.read_bytes()
            external_texts.append(extract_visible_text(body, "text/html"))
    forbidden = [chunk.text for chunk in chunks] + [text for text in external_texts if text]
    for payload in planner.payloads:
        assert_safe_planner_payload(payload, forbidden)

    input_reduction = GATE5_INPUT_TOKENS - result.planner_input_tokens
    evidence = {
        "classification": "Gate 5.1 IFRS-targeted comparable-company discovery; separate from every earlier gate and the frozen retrieval holdout",
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "planner_model": EXPECTED_MODEL,
        "live_model_completed_without_fallback": result.mode == "model-planned bounded agent",
        "required_reporting_framework": "IFRS",
        "result": result.safe_export(),
        "efficiency": {
            "gate5_input_tokens": GATE5_INPUT_TOKENS,
            "gate51_input_tokens": result.planner_input_tokens,
            "input_token_reduction": input_reduction,
            "input_token_reduction_percent": round(input_reduction / GATE5_INPUT_TOKENS * 100, 2),
            "gate5_provider_cost_usd": GATE5_COST_USD,
            "gate51_provider_cost_usd": result.provider_cost_usd,
            "cost_change_usd": round(result.provider_cost_usd - GATE5_COST_USD, 8),
            "correctness_safeguards_preserved": True,
        },
        "source_policy": {
            "primary_source": "SEC EDGAR",
            "allowed_hosts": ["efts.sec.gov", "data.sec.gov", "www.sec.gov"],
            "user_agent_present": True,
            "user_agent_value_saved": False,
            "broad_crawling_performed": False,
        },
        "privacy_assertions": {
            "raw_private_corpus_text_sent_to_planner": False,
            "raw_external_filing_text_sent_to_planner": False,
            "api_key_or_authorization_saved": False,
            "full_filing_text_saved_in_audit": False,
        },
        "evaluation_boundaries": {
            "frozen_holdout_used_or_tuned": False,
            "frozen_metrics_recomputed": False,
            "external_documents_added_to_frozen_corpus": False,
            "gate5_artifacts_changed": False,
            "gate6_started": False,
        },
        "protected_artifact_hashes_before_and_after_match": True,
    }
    serialized = json.dumps(evidence, ensure_ascii=False, indent=2)
    for text in forbidden:
        if len(text) >= 40 and text in serialized:
            raise RuntimeError("Raw source text entered the sanitized Gate 5.1 audit.")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / "sanitized_live_result_v01.json").write_text(serialized, encoding="utf-8")
    print(
        json.dumps(
            {
                "recorded_at": evidence["recorded_at"],
                "mode": result.mode,
                "steps": result.step_count,
                "external_requests": len(result.external_request_log),
                "candidates": [item["company"] for item in result.candidates],
                "framework_results": [
                    {
                        "company": item["company"],
                        "status": item["status"],
                        "decision": item["decision"],
                    }
                    for item in result.framework_results
                ],
                "verified_ifrs_candidate_found": result.handoff.get("verified_ifrs_candidate_found"),
                "useful_ifrs_comparator_found": result.handoff.get("useful_ifrs_comparator_found"),
                "input_tokens": result.planner_input_tokens,
                "output_tokens": result.planner_output_tokens,
                "provider_cost_usd": result.provider_cost_usd,
                "runtime_audit": "external_runtime/gate51_live_v01/sanitized_live_result_v01.json",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
