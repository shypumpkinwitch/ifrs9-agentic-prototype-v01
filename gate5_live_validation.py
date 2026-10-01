from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.agent_planner import OpenRouterPlanner, assert_safe_planner_payload
from src.external_discovery import SecEdgarClient, run_gate5_discovery
from src.private_runtime import default_private_bundle
from src.schemas import ResearchRequest
from src.source_registry import hash_file, load_candidates, load_private_corpus_read_only


PROJECT_ROOT = Path(__file__).resolve().parent
PUBLIC = PROJECT_ROOT / "data" / "public_demo"
EXPECTED_MODEL = "openai/gpt-4o-mini"


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
        raise SystemExit(
            "SEC_USER_AGENT is unavailable; set it to an operator/company name plus contact email. No live run was attempted."
        )
    if os.getenv("OPENROUTER_MODEL", EXPECTED_MODEL) != EXPECTED_MODEL:
        raise SystemExit(f"OPENROUTER_MODEL must be {EXPECTED_MODEL}.")

    bundle = default_private_bundle(PROJECT_ROOT)
    chunks, _ = load_private_corpus_read_only(bundle / "working_corpus_v01.json")
    candidates = load_candidates(PUBLIC / "candidate_registry_v01.json")
    protected = [
        bundle / "working_corpus_v01.json",
        bundle / "freeze_manifest_v02.json",
        bundle / "evaluation_question_bank_frozen_v01.json",
        bundle / "development_ground_truth_frozen_v01.json",
        bundle / "holdout_test_ground_truth_frozen_v01.json",
        bundle / "all_76_chunk_label_audit_frozen_v01.csv",
        bundle / "ground_truth_QA_report_frozen_v01.md",
        PROJECT_ROOT / "docs" / "GATE45_LIVE_PLANNER_AUDIT_v01.json",
        PROJECT_ROOT / "docs" / "GATE45_LIVE_PLANNER_RESULTS_v01.md",
        PROJECT_ROOT / "docs" / "GATE46_LIVE_REVALIDATION_ATTEMPT1_v01.json",
        PROJECT_ROOT / "docs" / "GATE46_LIVE_PLANNER_AUDIT_v01.json",
        PROJECT_ROOT / "docs" / "GATE46_HARDENING_RESULTS_v01.md",
    ]
    before = {str(path): hash_file(path) for path in protected}
    planner = OpenRouterPlanner.from_environment()
    if planner is None:
        raise RuntimeError("Planner environment changed before the live run.")
    sec = SecEdgarClient.from_environment()
    result = run_gate5_discovery(
        flagship_request(),
        private_chunks=chunks,
        local_candidates=candidates,
        sec_client=sec,
        runtime_root=PROJECT_ROOT / "external_runtime" / "gate5_live_v01",
        jurisdiction_context_path=PUBLIC / "ifrs_jurisdiction_context_v01.json",
        planner=planner,
        max_steps=10,
    )
    after = {str(path): hash_file(path) for path in protected}
    if before != after:
        raise RuntimeError("A protected frozen or Gate 4.5/4.6 artifact changed during Gate 5.")
    external_texts = []
    raw_root = PROJECT_ROOT / "external_runtime" / "gate5_live_v01" / "raw"
    for path in raw_root.rglob("*") if raw_root.is_dir() else []:
        if path.is_file():
            body = path.read_bytes()
            try:
                external_texts.append(body.decode("utf-8"))
            except UnicodeDecodeError:
                pass
    forbidden = [chunk.text for chunk in chunks] + external_texts
    for payload in planner.payloads:
        assert_safe_planner_payload(payload, forbidden)
    evidence = {
        "classification": "Gate 5 bounded external comparable-company discovery; separate from all frozen and Gate 4 evaluations",
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "planner_model": EXPECTED_MODEL,
        "live_model_completed_without_fallback": result.mode == "model-planned bounded agent",
        "external_source_policy": {
            "primary_source": "SEC EDGAR",
            "allowed_hosts": ["data.sec.gov", "efts.sec.gov", "www.sec.gov"],
            "user_agent_present": True,
            "user_agent_saved": False,
            "minimum_request_interval_seconds": sec.minimum_interval_seconds,
            "broad_crawling_performed": False,
        },
        "evaluation_boundaries": {
            "frozen_holdout_used_or_tuned": False,
            "frozen_metrics_recomputed": False,
            "external_documents_added_to_frozen_corpus": False,
            "gate45_or_gate46_artifacts_changed": False,
        },
        "privacy_assertions": {
            "raw_private_corpus_text_sent_to_planner": False,
            "raw_external_filing_text_sent_to_planner": False,
            "api_key_or_authorization_saved": False,
            "full_filing_text_saved_in_audit": False,
        },
        "result": result.safe_export(),
        "usage": {
            "input_tokens": result.planner_input_tokens,
            "output_tokens": result.planner_output_tokens,
            "provider_reported_cost_usd": result.provider_cost_usd,
        },
        "protected_artifact_hashes_before_and_after_match": True,
    }
    serialized = json.dumps(evidence, ensure_ascii=False, indent=2)
    for text in forbidden:
        if len(text) >= 40 and text in serialized:
            raise RuntimeError("Raw source text entered the sanitized Gate 5 audit.")
    print(serialized)


if __name__ == "__main__":
    main()
