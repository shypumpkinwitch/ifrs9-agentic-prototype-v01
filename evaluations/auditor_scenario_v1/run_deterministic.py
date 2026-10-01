"""Read-only offline observation runner. Prints sanitized evidence; does not grade cases."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluations.auditor_scenario_v1.validation import (
    EVALUATION_DIR, load_json, validate_cases, validate_manifest,
)
from src.agent_loop_hardened import run_bounded_agent
from src.agent_planner import DeterministicFallbackPlanner
from src.authority_registry import (
    build_separated_research_handoff, identify_ifrs9_research_topics,
    load_authority_registry, retrieve_authority_cards,
)
from src.final_submission import load_final_submission_snapshot
from src.private_runtime import default_private_bundle
from src.schemas import ResearchRequest
from src.source_registry import load_candidates, load_corpus, load_private_corpus_read_only


def run_offline() -> dict:
    # Verify the freeze and prior evidence before any scenario execution.
    manifest = validate_manifest()
    cases = load_json(EVALUATION_DIR / "cases_frozen_v1.json")
    validate_cases(cases)
    public = PROJECT_ROOT / "data/public_demo"
    corpus = default_private_bundle(PROJECT_ROOT) / "working_corpus_v01.json"
    chunks = load_private_corpus_read_only(corpus)[0] if corpus.is_file() else load_corpus(public / "disclosures_v01.json")
    candidates = load_candidates(public / "candidate_registry_v01.json")
    registry = load_authority_registry(public / "ifrs_authority_registry_v01.json")
    snapshot = load_final_submission_snapshot(PROJECT_ROOT)
    benchmark = {"status": "optional private benchmark unavailable"}
    if corpus.is_file():
        names = {
            "questions": "evaluation_question_bank_frozen_v01.json",
            "development": "development_ground_truth_frozen_v01.json",
            "frozen_holdout": "holdout_test_ground_truth_frozen_v01.json",
        }
        benchmark = {key: len(load_json(corpus.parent / name)) for key, name in names.items()}
        if benchmark != {"questions": 50, "development": 12, "frozen_holdout": 38}:
            raise ValueError("Historical retrieval benchmark split differs from 50/12/38.")
        benchmark["status"] = "read-only count check; no retrieval metrics recomputed"
    observations = []
    blocked = AssertionError("Network/model use is prohibited in this offline evaluation.")
    with (
        patch("socket.socket", side_effect=blocked),
        patch("socket.create_connection", side_effect=blocked),
        patch("urllib.request.urlopen", side_effect=blocked),
        patch("src.agent_planner.OpenRouterPlanner.from_environment", side_effect=blocked),
        patch("src.agent_planner.OpenRouterPlanner.choose_next", side_effect=blocked),
    ):
        for case in cases:
            # Same default topic as the UI, with optional industry/instrument hints blank.
            # Never inject the expected answers, topics or coverage gaps into the workflow.
            request = ResearchRequest(scenario=case["scenario"], topic="expected credit losses")
            topics = identify_ifrs9_research_topics(request)
            cards = retrieve_authority_cards(registry, topics)
            result = run_bounded_agent(
                request, chunks=chunks, candidates=candidates,
                planner=DeterministicFallbackPlanner(),
            )
            handoff = build_separated_research_handoff(cards, result.handoff, snapshot["recorded_candidates"])
            exported = result.safe_export()
            # Keep a concise reproducible observation, rather than duplicate every
            # dynamic tool contract or record wall-clock latency as a test result.
            safe_result = {key: exported[key] for key in (
                "mode", "planner_model", "step_count", "step_limit", "trace",
                "evidence_needs", "comparability", "retrieved_evidence", "authority",
                "missing_evidence", "handoff", "guardrails_triggered", "human_review_required",
                "planner_input_tokens", "planner_output_tokens", "provider_cost_usd",
            )}
            safe_result["trace"] = [
                {key: value for key, value in entry.items() if key != "elapsed_ms"}
                for entry in safe_result["trace"]
            ]
            serialized = json.dumps({"run": safe_result, "handoff": handoff})
            if any(chunk.text and chunk.text in serialized for chunk in chunks):
                raise AssertionError("Raw local source body entered evaluation evidence.")
            if result.planner_input_tokens or result.planner_output_tokens or result.provider_cost_usd:
                raise AssertionError("Offline execution must have zero model usage/cost.")
            observations.append({
                "case_id": case["case_id"],
                "classification": "Deterministic local workflow observation; manual dimensions not graded",
                "identified_authority_topics": topics,
                "official_authority_ids": [card.authority_id for card in cards],
                "current_local_run": safe_result,
                "separated_handoff": handoff,
                "recorded_external_metadata_reused": True,
                "new_external_discovery_performed": False,
            })
    validate_manifest()  # Check all frozen and protected file bytes again after execution.
    return {
        "evaluation_id": "auditor_scenario_evaluation_v1",
        "classification": "Offline diagnostic observations, not manual evaluation scores or retrieval metrics",
        "cases_sha256": manifest["files"]["cases_frozen_v1.json"],
        "scenario_execution_count": len(observations),
        "corpus_mode": "private local corpus read-only" if corpus.is_file() else "self-authored public fixtures",
        "input_controls": {"topic": "existing UI default: expected credit losses", "optional_industry_and_transaction_hints": "blank", "expected_answers_injected": False},
        "live_model_runs": 0, "live_sec_calls": 0, "network_allowed": False,
        "planner_input_tokens": 0, "planner_output_tokens": 0, "provider_cost_usd": 0,
        "historical_retrieval": benchmark,
        "protected_existing_files_checked_before_and_after": len(manifest["protected_existing_files"]),
        "protected_existing_files_unchanged": True,
        "manual_review_status": "pending; no manual PASS/FAIL/N/A judgements assigned",
        "observations": observations,
    }


if __name__ == "__main__":
    print(json.dumps(run_offline(), indent=2, ensure_ascii=False))
