from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

from .agent_planner import (
    DeterministicFallbackPlanner,
    OpenRouterPlanner,
    PlannerDecision,
    PlannerError,
)
from .agent_tools import LocalResearchTools, TOOL_CONTRACTS
from .schemas import Candidate, EvidenceChunk, ResearchRequest


class AgentPolicyError(RuntimeError):
    """Raised when the bounded controller rejects an action."""


PROHIBITED_JUDGMENT = re.compile(r"\b(?:correct|compliant|appropriate)\b", re.IGNORECASE)


@dataclass(frozen=True)
class AgentTraceEntry:
    step: int
    action: str
    reason: str
    arguments: dict[str, Any]
    result_summary: str
    planner_mode: str
    elapsed_ms: float


class BoundedAgentController:
    def __init__(self, tools: LocalResearchTools, *, max_steps: int = 6, planner_mode: str):
        self.tools = tools
        self.max_steps = max_steps
        self.planner_mode = planner_mode
        self.trace: list[AgentTraceEntry] = []
        self.seen_calls: set[str] = set()
        self.guardrails: list[str] = []
        self.stopped = False

    @staticmethod
    def _result_summary(tool: str, result: dict[str, Any]) -> str:
        if tool == "analyse_audit_scenario":
            return (
                f"Identified {len(result.get('accounting_topics', []))} accounting topic(s) and "
                f"{len(result.get('evidence_needs', []))} evidence need(s)."
            )
        if tool == "search_private_corpus":
            companies = sorted({item["company"] for item in result.get("results", [])})
            return f"Returned {result.get('result_count', 0)} metadata-only hit(s) across {len(companies)} company candidate(s)."
        if tool == "inspect_candidate_metadata":
            return f"Inspected permitted metadata for {len(result.get('profiles', []))} candidate company profile(s)."
        if tool == "assess_comparability":
            ratings = CounterLike(item["rating"] for item in result.get("assessments", []))
            return "Comparability ratings: " + ", ".join(f"{name}={count}" for name, count in ratings.items())
        if tool == "check_authority":
            return (
                f"Present authority classes: {', '.join(result.get('present_authority_classes', [])) or 'none'}; "
                f"missing: {', '.join(result.get('missing_authority_classes', [])) or 'none'}."
            )
        if tool == "request_more_evidence":
            return f"Requested {len(result.get('evidence_types', []))} additional evidence type(s)."
        if tool == "stop_and_summarise":
            return f"Stopped with status {result.get('status', 'unknown')} and human review required."
        return "Tool completed with a bounded structured result."

    def execute(
        self,
        decision: PlannerDecision,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if self.stopped:
            raise AgentPolicyError("Research run is already stopped.")
        if decision.tool not in TOOL_CONTRACTS:
            raise AgentPolicyError(f"Tool is not allowlisted: {decision.tool}")
        if len(self.trace) >= self.max_steps:
            raise AgentPolicyError(f"Six-step cap reached ({self.max_steps}).")
        signature = json.dumps(
            {"tool": decision.tool, "arguments": decision.arguments},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if signature in self.seen_calls:
            raise AgentPolicyError("Duplicate tool call with identical arguments blocked.")
        self.seen_calls.add(signature)
        reason = decision.reason.strip()[:300] or "Bounded planner selected this action."
        if PROHIBITED_JUDGMENT.search(reason):
            reason = "Planner reason withheld because it attempted a prohibited audit judgment."
            self.guardrails.append("Prohibited audit-judgment wording removed from planner reason.")
        started = time.perf_counter()
        result = self.tools.execute(decision.tool, decision.arguments, state)
        elapsed = (time.perf_counter() - started) * 1000
        self.trace.append(
            AgentTraceEntry(
                step=len(self.trace) + 1,
                action=decision.tool,
                reason=reason,
                arguments=decision.arguments,
                result_summary=self._result_summary(decision.tool, result),
                planner_mode=self.planner_mode,
                elapsed_ms=round(elapsed, 3),
            )
        )
        state.setdefault("completed_tools", []).append(decision.tool)
        state.setdefault("observations", {})[decision.tool] = result
        if decision.tool == "stop_and_summarise":
            self.stopped = True
        return result


def CounterLike(values):
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


@dataclass(frozen=True)
class AgentResearchResult:
    mode: str
    planner_model: str | None
    step_count: int
    step_limit: int
    stopped_early: bool
    trace: list[dict[str, Any]]
    evidence_needs: list[str]
    candidates: list[dict[str, Any]]
    comparability: list[dict[str, Any]]
    retrieved_evidence: list[dict[str, Any]]
    authority: dict[str, Any]
    missing_evidence: list[str]
    handoff: dict[str, Any]
    guardrails_triggered: list[str]
    human_review_required: bool
    planner_input_tokens: int
    planner_output_tokens: int
    provider_cost_usd: float
    approximate_latency_ms: float
    tool_registry: list[str]

    def safe_export(self) -> dict[str, Any]:
        output = asdict(self)
        for item in output["retrieved_evidence"]:
            item.pop("text", None)
        output["export_notice"] = (
            "Private annual-report text is omitted. This is a research handoff, not an audit conclusion."
        )
        return output


def run_bounded_agent(
    request: ResearchRequest,
    *,
    chunks: list[EvidenceChunk],
    candidates: list[Candidate],
    planner: DeterministicFallbackPlanner | OpenRouterPlanner | Any | None = None,
    max_steps: int = 6,
) -> AgentResearchResult:
    if max_steps != 6:
        raise ValueError("Gate 4 research runs use an exact six-step maximum.")
    started = time.perf_counter()
    tools = LocalResearchTools(chunks, candidates)
    active_planner = planner or OpenRouterPlanner.from_environment() or DeterministicFallbackPlanner()
    mode = active_planner.mode
    model = getattr(active_planner, "model", None)
    metered_planners = [active_planner]
    controller = BoundedAgentController(tools, max_steps=max_steps, planner_mode=mode)
    state: dict[str, Any] = {
        "request": {
            "scenario": request.scenario,
            "topic": request.topic,
            "industry": request.industry,
            "transaction_type": request.transaction_type,
            "reporting_period": request.reporting_period,
            "required_framework": request.required_framework,
            "search_text": request.search_text(),
        },
        "completed_tools": [],
        "observations": {},
    }
    forbidden_texts = [chunk.text for chunk in chunks]
    while not controller.stopped and len(controller.trace) < max_steps:
        remaining = max_steps - len(controller.trace)
        try:
            decision = active_planner.choose_next(
                state,
                tools.registry,
                remaining,
                forbidden_texts,
            )
        except PlannerError as exc:
            controller.guardrails.append(f"Model planner failed safely: {exc}")
            active_planner = DeterministicFallbackPlanner()
            metered_planners.append(active_planner)
            mode = "deterministic fallback after model-planner error"
            controller.planner_mode = mode
            decision = active_planner.choose_next(
                state,
                tools.registry,
                remaining,
                forbidden_texts,
            )
        if remaining == 1 and decision.tool != "stop_and_summarise":
            decision = PlannerDecision(
                "stop_and_summarise",
                {"reason": "The six-step research budget has been reached."},
                "Reserve the final allowed step for a structured human-review handoff.",
            )
            controller.guardrails.append("Final step reserved for stop_and_summarise.")
        try:
            controller.execute(decision, state)
        except AgentPolicyError as exc:
            controller.guardrails.append(str(exc))
            if len(controller.trace) < max_steps:
                controller.execute(
                    PlannerDecision(
                        "stop_and_summarise",
                        {"reason": "Controller policy blocked the planner action."},
                        "Stop safely after a controller policy intervention.",
                    ),
                    state,
                )
            break
        except (KeyError, TypeError, ValueError) as exc:
            controller.guardrails.append(
                f"Invalid planner tool arguments blocked ({type(exc).__name__})."
            )
            if len(controller.trace) < max_steps:
                controller.execute(
                    PlannerDecision(
                        "stop_and_summarise",
                        {"reason": "Planner supplied an invalid tool sequence or argument set."},
                        "Stop safely after invalid planner-supplied tool input.",
                    ),
                    state,
                )
            break

    handoff = state.get("observations", {}).get("stop_and_summarise", {})
    if not handoff:
        handoff = tools.stop_and_summarise(
            "The research budget ended before an explicit stop action.", state=state
        )
        controller.guardrails.append("Controller created a safe handoff at the step limit.")
    serialized_handoff = json.dumps(handoff, ensure_ascii=False)
    if PROHIBITED_JUDGMENT.search(serialized_handoff):
        raise AgentPolicyError("Structured handoff contains prohibited audit-judgment wording.")
    observations = state.get("observations", {})
    analysis = observations.get("analyse_audit_scenario", {})
    profiles = observations.get("inspect_candidate_metadata", {}).get("profiles", [])
    comparisons = observations.get("assess_comparability", {}).get("assessments", [])
    authority = observations.get("check_authority", {})
    elapsed = (time.perf_counter() - started) * 1000
    return AgentResearchResult(
        mode=mode,
        planner_model=model,
        step_count=len(controller.trace),
        step_limit=max_steps,
        stopped_early=len(controller.trace) < max_steps,
        trace=[asdict(entry) for entry in controller.trace],
        evidence_needs=analysis.get("evidence_needs", []),
        candidates=profiles,
        comparability=comparisons,
        retrieved_evidence=tools.local_selected_evidence(),
        authority=authority,
        missing_evidence=handoff.get("missing_evidence", []),
        handoff=handoff,
        guardrails_triggered=controller.guardrails,
        human_review_required=True,
        planner_input_tokens=sum(
            int(getattr(item, "total_input_tokens", 0)) for item in metered_planners
        ),
        planner_output_tokens=sum(
            int(getattr(item, "total_output_tokens", 0)) for item in metered_planners
        ),
        provider_cost_usd=sum(
            float(getattr(item, "total_cost_usd", 0.0)) for item in metered_planners
        ),
        approximate_latency_ms=round(elapsed, 3),
        tool_registry=list(TOOL_CONTRACTS),
    )
