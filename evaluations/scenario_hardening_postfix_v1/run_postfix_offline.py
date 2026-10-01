"""Regression diagnostics informed by known QA cases; not an unseen evaluation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
EVIDENCE_DIR = Path(__file__).resolve().parent
FROZEN_DIR = PROJECT_ROOT / "evaluations/auditor_scenario_v1_1"

from evaluations.auditor_scenario_v1.validation import validate_cases
from src.agent_loop_hardened import run_bounded_agent
from src.agent_planner import DeterministicFallbackPlanner
from src.authority_registry import build_separated_research_handoff, identify_ifrs9_research_topics, load_authority_registry, retrieve_authority_cards
from src.final_submission import load_final_submission_snapshot
from src.private_runtime import default_private_bundle
from src.schemas import ResearchRequest
from src.source_registry import load_candidates, load_corpus, load_private_corpus_read_only


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_protected_artifacts():
    manifest = load_json(EVIDENCE_DIR / "protected_artifacts_manifest.json")
    for name, expected in manifest["protected_artifacts"].items():
        path = PROJECT_ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise AssertionError(f"Protected artifact changed: {name}")
    # Validate the original frozen case/schema/protocol hashes without expecting
    # authorised runtime source changes to match the old code environment.
    frozen_manifest = load_json(FROZEN_DIR / "freeze_manifest_v1_1.json")
    for name, expected in frozen_manifest["files"].items():
        if hashlib.sha256((FROZEN_DIR / name).read_bytes()).hexdigest() != expected:
            raise AssertionError(f"Frozen scenario input changed: {name}")
    return manifest


def run_postfix():
    preservation = verify_protected_artifacts()
    cases = load_json(FROZEN_DIR / "cases_frozen_v1_1.json")
    validate_cases(cases, load_json(FROZEN_DIR / "cases.schema.json"))
    public = PROJECT_ROOT / "data/public_demo"
    corpus = default_private_bundle(PROJECT_ROOT) / "working_corpus_v01.json"
    chunks = load_private_corpus_read_only(corpus)[0] if corpus.is_file() else load_corpus(public / "disclosures_v01.json")
    candidates = load_candidates(public / "candidate_registry_v01.json")
    registry = load_authority_registry(public / "ifrs_authority_registry_v01.json")
    snapshot = load_final_submission_snapshot(PROJECT_ROOT)
    original = load_json(FROZEN_DIR / "deterministic_observations_v1_1.json")
    baseline = {item["case_id"]: item for item in original["observations"]}
    blocked = AssertionError("Live network/model access is prohibited in regression diagnostics.")
    observations = []
    with (
        patch("socket.socket", side_effect=blocked),
        patch("socket.create_connection", side_effect=blocked),
        patch("urllib.request.urlopen", side_effect=blocked),
        patch("src.agent_planner.OpenRouterPlanner.from_environment", side_effect=blocked),
        patch("src.agent_planner.OpenRouterPlanner.choose_next", side_effect=blocked),
    ):
        for case in cases:
            request = ResearchRequest(scenario=case["scenario"])
            topics = identify_ifrs9_research_topics(request)
            cards = retrieve_authority_cards(registry, topics)
            result = run_bounded_agent(request, chunks=chunks, candidates=candidates, planner=DeterministicFallbackPlanner())
            exported = result.safe_export()
            exported.pop("approximate_latency_ms", None)
            exported.pop("dynamic_tool_menus", None)
            exported["trace"] = [{key: value for key, value in entry.items() if key != "elapsed_ms"} for entry in exported["trace"]]
            handoff = build_separated_research_handoff(cards, result.handoff, snapshot["recorded_candidates"], request=request)
            serialized = json.dumps({"run": exported, "handoff": handoff})
            if any(chunk.text and chunk.text in serialized for chunk in chunks):
                raise AssertionError("Raw private source text leaked into regression evidence.")
            if result.planner_input_tokens or result.planner_output_tokens or result.provider_cost_usd:
                raise AssertionError("Unexpected model usage during offline regression.")
            previous = baseline[case["case_id"]]
            observations.append({
                "case_id": case["case_id"], "scenario": case["scenario"],
                "before": {
                    "authority_ids": previous["official_authority_ids"],
                    "selected_candidates": previous["current_local_run"]["handoff"]["selected_candidates"],
                    "steps": previous["current_local_run"]["step_count"],
                    "recorded_snapshot_attached": bool(previous["separated_handoff"]["How comparable companies disclosed similar exposures"]["recorded_comparable_summaries"]),
                },
                "after": {
                    "scenario_routing": request.scenario_routing(),
                    "authority_ids": [card.authority_id for card in cards],
                    "authority_coverage": result.handoff["authority_coverage"],
                    "selected_candidates": result.handoff["selected_candidates"],
                    "comparator_status": result.handoff["comparator_status"],
                    "abstention": result.handoff["abstention"],
                    "steps": result.step_count,
                    "recorded_snapshot_attached": False,
                    "run": exported, "separated_handoff": handoff,
                },
            })
    verify_protected_artifacts()
    return {
        "classification": "Post-fix regression-validation evidence informed by these eight cases; not unbiased unseen holdout performance",
        "frozen_case_sha256": preservation["original_case_sha256"],
        "scenario_count": 8, "case_expectations_fed_to_runtime": False,
        "request_topic": "automatic from scenario content; no forced ECL default",
        "corpus_mode": "private read-only" if corpus.is_file() else "self-authored fixtures",
        "live_openrouter_calls": 0, "live_sec_calls": 0,
        "planner_input_tokens": 0, "planner_output_tokens": 0, "provider_cost_usd": 0,
        "protected_artifacts_checked": len(preservation["protected_artifacts"]),
        "protected_artifacts_unchanged": True, "manual_scenario_scores_assigned": False,
        "observations": observations,
    }


if __name__ == "__main__":
    print(json.dumps(run_postfix(), ensure_ascii=False, indent=2))
