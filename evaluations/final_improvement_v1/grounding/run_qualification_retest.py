"""One-call v2.1 qualification-retention retest, preserving all v2 inputs/results."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluations.final_improvement_v1.grounding.run_grounding_evaluation import (
    CASES_PATH, SOURCES_PATH, RESULTS_PATH, MODEL, _default_transport,
    _load_json, _private_forbidden_texts, build_request, structural_checks,
    validate_sources,
)

PROMPT_VERSION = "grounding-v2.1-critical-qualification-retention"
QUALIFICATION_RULE = (
    "Preserve all material qualifications, conditions, exceptions and limitations explicitly stated "
    "in the supplied evidence that constrain your answer. Do not strengthen conditional statements "
    "into unconditional claims or replace 'may' with 'must'. Brevity must not remove a material "
    "qualification. Include the applicable conditions in the cited answer, and check the answer "
    "against the supplied evidence before returning it. Return only the answer, without internal reasoning."
)
OUTPUT = Path(__file__).with_name("live_results_v2_1.json")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    cases = _load_json(CASES_PATH)
    case = next(item for item in cases if item["case_id"] == "GRD-03-FORWARD-LOOKING")
    sources = validate_sources(_load_json(SOURCES_PATH))
    if case["source_ids"] != ["EDU-FWD-003"]:
        raise ValueError("Retest requires the unchanged original single-source case.")
    body, audit = build_request(case, sources, forbidden_texts=_private_forbidden_texts())
    body["messages"][0]["content"] += " " + QUALIFICATION_RULE
    serialized = json.dumps(body, ensure_ascii=False, sort_keys=True)
    audit["payload_sha256"] = hashlib.sha256(serialized.encode()).hexdigest()
    audit["prompt_version"] = PROMPT_VERSION
    return case, sources, body, audit


def compare(original, revised, source):
    phrase = "without undue cost or effort"
    return {
        "validation_type": "automated phrase retention; independent human factual review pending",
        "qualification_stated_in_source": phrase in source.lower(),
        "original_retains_qualification": phrase in original.lower(),
        "revised_retains_qualification": phrase in revised.lower(),
        "independent_human_review_status": "pending",
        "fully_supported_by_source": None,
    }


def main():
    if OUTPUT.exists():
        raise SystemExit("Existing v2.1 artifact protected; no further live call made.")
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is unavailable; no live call made.")
    protected_paths = [CASES_PATH, SOURCES_PATH, RESULTS_PATH,
                       RESULTS_PATH.with_name("manual_review_checklist_v1.json")]
    before = {path.name: sha256(path) for path in protected_paths}
    case, sources, body, audit = prepare()
    original = next(item for item in _load_json(RESULTS_PATH)["records"]
                    if item["case_id"] == case["case_id"])
    response = _default_transport(body, {"Authorization": f"Bearer {key}",
                                         "Content-Type": "application/json"})
    choice = response["choices"][0]
    revised = choice["message"]["content"]
    checks = structural_checks(revised, case, set(sources))
    comparison = compare(original["model_response"], revised, sources["EDU-FWD-003"]["text"])
    usage = response.get("usage") or {}
    after = {path.name: sha256(path) for path in protected_paths}
    result = {
        "evaluation_id": "generation_grounding_v2_1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": MODEL, "live_calls": 1, "retries": 0,
        "case_id": case["case_id"], "question": case["question"],
        "prompt_version": PROMPT_VERSION,
        "system_instruction": body["messages"][0]["content"],
        "request_audit": audit,
        "original_response": original["model_response"],
        "revised_response": revised,
        "source_citations": checks["citations"],
        "structural_checks": checks,
        "qualification_comparison": comparison,
        "outcome": ("qualification_retained; manual factual review pending"
                    if checks["structural_pass"] and comparison["revised_retains_qualification"]
                    else "failed or partial qualification-retention result"),
        "usage": {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "provider_reported_cost_available": usage.get("cost") is not None,
            "provider_reported_cost_usd": usage.get("cost"),
        },
        "provider_response_metadata": {
            "response_id": response.get("id"), "provider_model": response.get("model"),
            "finish_reason": choice.get("finish_reason"),
        },
        "original_artifact_hashes_before": before,
        "original_artifact_hashes_after": after,
        "original_artifacts_unchanged": before == after,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"outcome": result["outcome"], "response": revised,
                      "usage": result["usage"], "original_artifacts_unchanged": before == after}, indent=2))


if __name__ == "__main__":
    main()
