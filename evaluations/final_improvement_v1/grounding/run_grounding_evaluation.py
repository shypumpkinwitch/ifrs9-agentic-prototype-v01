"""Live grounding evaluation using approved self-authored educational notes only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCES_PATH = EVALUATION_DIR / "educational_sources_v1.json"
CASES_PATH = EVALUATION_DIR / "cases_v1.json"
RESULTS_PATH = EVALUATION_DIR / "live_results_v1.json"
CHECKLIST_PATH = EVALUATION_DIR / "manual_review_checklist_v1.json"
PRIVATE_CORPUS_PATH = (
    PROJECT_ROOT
    / "private_data"
    / "runtime_inputs_v01"
    / "PE6201_Codex_Private_Runtime_Inputs_v01"
    / "working_corpus_v01.json"
)
ABSTENTION = "Insufficient evidence in the approved educational materials."
MODEL = "openai/gpt-4o-mini"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
CITATION_PATTERN = re.compile(r"\[(EDU-[A-Z0-9-]+)\]")


Transport = Callable[[dict[str, Any], dict[str, str]], dict[str, Any]]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_sources(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    required = {
        "source_id",
        "title",
        "authority_level",
        "authored_by",
        "self_authored",
        "approved_for_external_api",
        "text",
    }
    by_id: dict[str, dict[str, Any]] = {}
    for source in sources:
        if set(source) != required:
            raise ValueError("Educational source schema mismatch.")
        if source["authority_level"] != "PROJECT_EDUCATIONAL_NOTE":
            raise ValueError("Only project educational notes may enter this evaluation.")
        if source["self_authored"] is not True or source["approved_for_external_api"] is not True:
            raise ValueError("Every source must be self-authored and approved for external API use.")
        if not isinstance(source["text"], str) or not source["text"].strip():
            raise ValueError("Educational source text must be non-empty.")
        if source["source_id"] in by_id:
            raise ValueError("Duplicate educational source ID.")
        by_id[source["source_id"]] = source
    return by_id


def _private_forbidden_texts(path: Path = PRIVATE_CORPUS_PATH) -> list[str]:
    if not path.is_file():
        return []
    records = _load_json(path)
    return [item["text"] for item in records if len(item.get("text", "")) >= 40]


def build_request(
    case: dict[str, Any],
    sources_by_id: dict[str, dict[str, Any]],
    *,
    forbidden_texts: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = []
    for source_id in case["source_ids"]:
        if source_id not in sources_by_id:
            raise ValueError(f"Unknown source ID: {source_id}")
        source = sources_by_id[source_id]
        selected.append(
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "authority_level": source["authority_level"],
                "self_authored": True,
                "source_text": source["text"],
            }
        )
    context = {
        "case_id": case["case_id"],
        "question": case["question"],
        "approved_educational_sources": selected,
    }
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "This is a controlled grounding evaluation. Use only the supplied self-authored educational notes. "
                    "Do not use external knowledge and do not state that the notes are authoritative IFRS requirements. "
                    "If the notes are sufficient, answer in one or two concise lines and place one or more source citations "
                    "such as [EDU-ECL-001] on every line. If they are insufficient, output exactly: "
                    f"{ABSTENTION}"
                ),
            },
            {"role": "user", "content": json.dumps(context, sort_keys=True)},
        ],
    }
    serialized = json.dumps(body, ensure_ascii=False, sort_keys=True)
    leaked = [text for text in (forbidden_texts or []) if text in serialized]
    if leaked:
        raise ValueError("Raw private annual-report text was blocked from the grounding payload.")
    if "COMPANY_DISCLOSURE" in serialized or "IFRS_STANDARD_OFFICIAL_AUTHORITY" in serialized:
        raise ValueError("Disallowed authority material was blocked from the grounding payload.")
    audit = {
        "payload_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "source_ids": list(case["source_ids"]),
        "source_count": len(selected),
        "outbound_material": "approved self-authored educational notes only",
        "raw_annual_report_text_included": False,
        "raw_ifrs_source_text_included": False,
        "authorization_header_saved": False,
    }
    return body, audit


def _default_transport(body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"OpenRouter grounding call failed: {type(exc).__name__}") from exc


def structural_checks(
    response_text: str,
    case: dict[str, Any],
    all_source_ids: set[str],
) -> dict[str, Any]:
    citations = CITATION_PATTERN.findall(response_text)
    selected = set(case["source_ids"])
    unknown = sorted(set(citations) - all_source_ids)
    outside_context = sorted(set(citations) - selected)
    expected_abstention = case["expected_behavior"] == "abstain_insufficient_evidence"
    exact_abstention = response_text.strip() == ABSTENTION
    lines = [line.strip() for line in response_text.splitlines() if line.strip()]
    every_answer_line_cited = bool(lines) and all(CITATION_PATTERN.search(line) for line in lines)
    if expected_abstention:
        passed = exact_abstention and not citations
    else:
        passed = (
            not exact_abstention
            and bool(citations)
            and not unknown
            and not outside_context
            and every_answer_line_cited
        )
    return {
        "expected_behavior": case["expected_behavior"],
        "citations": citations,
        "unknown_citations": unknown,
        "citations_outside_supplied_context": outside_context,
        "exact_abstention": exact_abstention,
        "every_answer_line_has_citation": every_answer_line_cited if not expected_abstention else None,
        "structural_pass": passed,
        "scope_note": "Automated syntax and source-ID checks only; not a factual-grounding judgement.",
    }


def run(
    api_key: str,
    *,
    transport: Transport = _default_transport,
    forbidden_texts: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required; live results are never simulated.")
    sources = _load_json(SOURCES_PATH)
    cases = _load_json(CASES_PATH)
    sources_by_id = validate_sources(sources)
    forbidden = _private_forbidden_texts() if forbidden_texts is None else forbidden_texts
    records = []
    checklist = []
    totals = {"input_tokens": 0, "output_tokens": 0, "provider_reported_cost_usd": 0.0}
    cost_available_for_every_call = True

    for case in cases:
        body, request_audit = build_request(
            case, sources_by_id, forbidden_texts=forbidden
        )
        response = transport(
            body,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            text = response["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise RuntimeError("OpenRouter response did not contain answer text.") from exc
        usage = response.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        cost_available = usage.get("cost") is not None
        cost = float(usage.get("cost") or 0.0)
        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["provider_reported_cost_usd"] += cost
        cost_available_for_every_call &= cost_available
        checks = structural_checks(text, case, set(sources_by_id))
        records.append(
            {
                "case_id": case["case_id"],
                "question": case["question"],
                "expected_behavior": case["expected_behavior"],
                "request_audit": request_audit,
                "model_response": text,
                "source_citations": checks["citations"],
                "structural_checks": checks,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "provider_reported_cost_available": cost_available,
                    "provider_reported_cost_usd": cost,
                },
                "provider_response_metadata": {
                    "response_id": response.get("id"),
                    "provider_model": response.get("model"),
                    "finish_reason": (response.get("choices") or [{}])[0].get("finish_reason"),
                },
            }
        )
        checklist.append(
            {
                "case_id": case["case_id"],
                "automated_structural_pass": checks["structural_pass"],
                "manual_review_status": "pending_human_review",
                "factual_claims_supported_by_cited_material": None,
                "citations_entail_claims": None,
                "abstention_appropriate": None,
                "material_omission_present": None,
                "reviewer_name": None,
                "reviewed_at": None,
                "review_notes": "",
            }
        )

    result = {
        "evaluation_id": "generation_grounding_v2",
        "evaluation_status": "live structural evaluation complete; manual factual review pending",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "cases": len(records),
        "sufficient_evidence_cases": sum(
            item["expected_behavior"] == "answer_with_citations" for item in records
        ),
        "insufficient_evidence_cases": sum(
            item["expected_behavior"] == "abstain_insufficient_evidence" for item in records
        ),
        "automated_structural_pass_count": sum(
            item["structural_checks"]["structural_pass"] for item in records
        ),
        "manual_factual_grounding_pass_count": None,
        "manual_review_status": "pending_human_review",
        "aggregate_usage": {
            **{
                **totals,
                "provider_reported_cost_usd": round(
                    totals["provider_reported_cost_usd"], 10
                ),
            },
            "provider_reported_cost_available_for_every_call": cost_available_for_every_call,
            "model_calls": len(records),
        },
        "privacy": {
            "source_authority_level": "PROJECT_EDUCATIONAL_NOTE",
            "self_authored_sources_only": True,
            "raw_annual_report_text_sent": False,
            "raw_ifrs_source_text_sent": False,
            "api_key_saved": False,
        },
        "structural_vs_manual_boundary": (
            "Automated checks validate citation syntax, source-ID membership and exact abstention only. "
            "They do not establish factual support; the checklist requires independent human review."
        ),
        "records": records,
    }
    return result, checklist


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RESULTS_PATH)
    parser.add_argument("--checklist", type=Path, default=CHECKLIST_PATH)
    args = parser.parse_args()
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    result, checklist = run(key)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.checklist.write_text(json.dumps(checklist, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "evaluation_status": result["evaluation_status"],
                "cases": result["cases"],
                "automated_structural_pass_count": result["automated_structural_pass_count"],
                "aggregate_usage": result["aggregate_usage"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
