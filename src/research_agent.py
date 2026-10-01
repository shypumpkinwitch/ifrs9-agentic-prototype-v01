from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from .evidence_cards import draft_local_note
from .retrieval import BM25Index, search_candidates
from .schemas import Candidate, EvidenceCard, EvidenceChunk, GuidanceLink, ResearchRequest
from .trace_log import TraceLog


ALLOWED_TOOLS = {
    "search_candidate_registry",
    "inspect_report_metadata",
    "retrieve_local_disclosures",
    "get_guidance_links",
    "finish_research",
}


class ToolPolicyError(RuntimeError):
    """Raised when controller-level tool policy is violated."""


class ToolController:
    def __init__(
        self,
        handlers: dict[str, Callable[..., Any]],
        *,
        max_invocations: int = 4,
        max_argument_chars: int = 6000,
        max_elapsed_ms: float = 5000.0,
        mode: str = "offline workflow",
    ):
        unknown = set(handlers) - ALLOWED_TOOLS
        if unknown:
            raise ToolPolicyError(f"Handlers are not allowlisted: {sorted(unknown)}")
        self.handlers = handlers
        self.max_invocations = max_invocations
        self.max_argument_chars = max_argument_chars
        self.max_elapsed_ms = max_elapsed_ms
        self.model_token_budget = 0
        self.provider_budget_usd = 0.0
        self.started = time.perf_counter()
        self.seen_calls: set[str] = set()
        self.trace = TraceLog(mode=mode)

    def call(self, tool: str, arguments: dict[str, Any], reason: str) -> Any:
        if tool not in ALLOWED_TOOLS or tool not in self.handlers:
            raise ToolPolicyError(f"Tool is not available: {tool}")
        if len(self.trace.entries) >= self.max_invocations:
            raise ToolPolicyError(f"Tool step cap ({self.max_invocations}) reached.")
        if (time.perf_counter() - self.started) * 1000 > self.max_elapsed_ms:
            raise ToolPolicyError(f"Workflow time ceiling ({self.max_elapsed_ms} ms) reached.")
        signature = json.dumps(
            {"tool": tool, "arguments": arguments}, sort_keys=True, separators=(",", ":")
        )
        if len(signature) > self.max_argument_chars:
            raise ToolPolicyError(
                f"Tool arguments exceed the {self.max_argument_chars}-character ceiling."
            )
        if signature in self.seen_calls:
            raise ToolPolicyError("Repeated identical tool call blocked.")
        self.seen_calls.add(signature)
        started = time.perf_counter()
        try:
            result = self.handlers[tool](**arguments)
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            self.trace.add(
                tool=tool,
                reason=reason,
                arguments=arguments,
                observation=f"Safe error: {type(exc).__name__}: {exc}",
                elapsed_ms=elapsed,
            )
            raise
        elapsed = (time.perf_counter() - started) * 1000
        count = len(result) if isinstance(result, (list, tuple, dict)) else 1
        self.trace.add(
            tool=tool,
            reason=reason,
            arguments=arguments,
            observation=f"Returned {count} bounded result item(s).",
            elapsed_ms=elapsed,
        )
        return result


@dataclass(frozen=True)
class ResearchResult:
    mode: str
    candidates: list[dict[str, Any]]
    inspected_candidate: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    guidance_links: list[dict[str, Any]]
    draft_note: str
    limitations: list[str]
    approval_status: str
    token_count: int
    provider_cost_usd: float
    approximate_latency_ms: float
    trace: dict[str, Any]
    private_corpus_hash: str | None = None

    def safe_export(self) -> dict[str, Any]:
        """Build a shareable trace without local/private source bodies."""
        from dataclasses import asdict

        output = asdict(self)
        for item in output["evidence"]:
            item.pop("text", None)
        output["export_notice"] = (
            "Evidence text is intentionally omitted; local retrieval does not grant publication rights."
        )
        return output


def run_offline_workflow(
    request: ResearchRequest,
    *,
    candidates: list[Candidate],
    chunks: list[EvidenceChunk],
    guidance_links: list[GuidanceLink],
    evidence_cards: list[EvidenceCard],
    private_corpus_hash: str | None = None,
) -> ResearchResult:
    """Execute actual deterministic read-only calls and label them truthfully as a workflow."""
    started = time.perf_counter()
    index = BM25Index(chunks)

    def search_candidate_registry(query: str, max_results: int = 5) -> list[dict]:
        return [item.to_dict() for item in search_candidates(candidates, query, max_results)]

    def inspect_report_metadata(candidate_id: str) -> dict:
        match = next((item for item in candidates if item.candidate_id == candidate_id), None)
        if match is None:
            raise KeyError(f"Unknown candidate: {candidate_id}")
        return match.to_dict()

    def retrieve_local_disclosures(
        query: str, top_k: int = 5, preferred_company: str | None = None
    ) -> list[dict]:
        return [
            hit.to_dict(include_text=True)
            for hit in index.search(
                query, top_k, preferred_company=preferred_company
            )
        ]

    def get_guidance_links(topic: str, max_results: int = 3) -> list[dict]:
        topic_terms = set(topic.lower().split())
        matches = [
            link
            for link in guidance_links
            if topic_terms.intersection(link.topic.lower().split())
        ]
        return [link.to_dict() for link in matches[:max_results]]

    def finish_research(reason: str) -> dict:
        return {"status": "finished", "reason": reason}

    controller = ToolController(
        {
            "search_candidate_registry": search_candidate_registry,
            "inspect_report_metadata": inspect_report_metadata,
            "retrieve_local_disclosures": retrieve_local_disclosures,
            "get_guidance_links": get_guidance_links,
            "finish_research": finish_research,
        }
    )
    query = request.search_text()
    candidate_results = controller.call(
        "search_candidate_registry",
        {"query": query, "max_results": 5},
        "Find metadata-only candidates relevant to the supplied scenario.",
    )
    inspected = None
    if candidate_results:
        inspected = controller.call(
            "inspect_report_metadata",
            {"candidate_id": candidate_results[0]["candidate_id"]},
            "Check the leading candidate's report and framework metadata before treating it as evidence.",
        )
    evidence = controller.call(
        "retrieve_local_disclosures",
        {
            "query": query,
            "top_k": 5,
            "preferred_company": (
                candidate_results[0]["company_name"] if candidate_results else None
            ),
        },
        (
            "Search only the local bounded corpus and prioritize the leading scenario-matched "
            "candidate; retrieval does not grant generation rights."
        ),
    )
    guidance = controller.call(
        "get_guidance_links",
        {"topic": request.topic, "max_results": 3},
        "Return official authority-aware links without treating linked text as indexed guidance.",
    )
    if not candidate_results:
        controller.call(
            "finish_research",
            {"reason": "No matching candidate registry entry; preserve abstention."},
            "Stop safely when the bounded registry has no relevant candidate.",
        )

    retrieved_companies = {
        item["company"].strip().casefold()
        for item in evidence
        if item.get("authority_class") == "COMPANY_DISCLOSURE" and item.get("company")
    }
    candidate_results = [
        {
            **candidate,
            "evidence_status": (
                "indexed_and_inspected"
                if any(
                    name.strip().casefold() in retrieved_companies
                    for name in [
                        candidate["company_name"],
                        *candidate.get("corpus_company_names", []),
                    ]
                )
                else candidate["evidence_status"]
            ),
        }
        for candidate in candidate_results
    ]

    retrieved_ids = {item["chunk_id"] for item in evidence}
    note = draft_local_note(evidence_cards, retrieved_ids)
    limitations = [
        "Official IFRS 9 guidance not available in this prototype; links are metadata only.",
        "Candidate metadata is not evidence that a disclosure was indexed or inspected.",
        "No model API call was made; this run is a deterministic offline workflow, not an autonomous agent run.",
    ]
    if not any(item["authority_class"] == "COMPANY_DISCLOSURE" for item in evidence):
        limitations.append("No company annual-report disclosure was retrieved in this run.")
    elapsed = (time.perf_counter() - started) * 1000
    return ResearchResult(
        mode="offline workflow",
        candidates=candidate_results,
        inspected_candidate=inspected,
        evidence=evidence,
        guidance_links=guidance,
        draft_note=note,
        limitations=limitations,
        approval_status="Pending independent human review",
        token_count=0,
        provider_cost_usd=0.0,
        approximate_latency_ms=round(elapsed, 3),
        trace=controller.trace.to_dict(),
        private_corpus_hash=private_corpus_hash,
    )
