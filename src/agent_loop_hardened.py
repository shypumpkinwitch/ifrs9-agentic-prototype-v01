from __future__ import annotations

import json
import re
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .agent_planner import (
    DeterministicFallbackPlanner,
    OpenRouterPlanner,
    PlannerDecision,
    PlannerError,
    PlannerResponseError,
    PlannerTransportError,
)
from .agent_tools import LocalResearchTools, TOOL_CONTRACTS
from .schemas import Candidate, EvidenceChunk, ResearchRequest


class AgentPolicyError(RuntimeError):
    """Raised when the hardened controller rejects an action."""


class WorkflowState(str, Enum):
    START = "START"
    SCENARIO_ANALYSED = "SCENARIO_ANALYSED"
    EVIDENCE_SEARCHED = "EVIDENCE_SEARCHED"
    CANDIDATES_INSPECTED = "CANDIDATES_INSPECTED"
    COMPARABILITY_ASSESSED = "COMPARABILITY_ASSESSED"
    AUTHORITY_CHECKED = "AUTHORITY_CHECKED"
    EVIDENCE_GAP_IDENTIFIED = "EVIDENCE_GAP_IDENTIFIED"
    READY_TO_STOP = "READY_TO_STOP"
    STOPPED = "STOPPED"


PROHIBITED_JUDGMENT = re.compile(r"\b(?:correct|compliant|appropriate)\b", re.IGNORECASE)


@dataclass(frozen=True)
class AgentTraceEntry:
    step: int
    state_before: str
    action: str
    reason: str
    arguments: dict[str, Any]
    result_summary: str
    state_after: str
    planner_mode: str
    elapsed_ms: float


def _scenario_flags(request: dict[str, Any]) -> dict[str, bool]:
    combined = " ".join(
        str(request.get(name, ""))
        for name in ("scenario", "topic", "industry", "transaction_type")
    ).casefold()
    authoritative = any(
        term in combined
        for term in (
            "authoritative",
            "official ifrs",
            "iasb publication",
            "ifrs requirement",
            "what ifrs requires",
        )
    )
    comparable = any(
        term in combined
        for term in (
            "comparable",
            "comparables",
            "property",
            "real estate",
            "bank",
            "loan portfolio",
        )
    ) and not authoritative
    return {
        "comparable_company_research": comparable,
        "authoritative_guidance_request": authoritative,
    }


class BoundedAgentController:
    def __init__(self, tools: LocalResearchTools, *, max_steps: int = 6, planner_mode: str):
        self.tools = tools
        self.max_steps = max_steps
        self.planner_mode = planner_mode
        self.trace: list[AgentTraceEntry] = []
        self.seen_calls: set[str] = set()
        self.seen_gap_signatures: set[str] = set()
        self.guardrails: list[str] = []
        self.state_history: list[str] = []
        self.menu_history: list[dict[str, Any]] = []
        self.stopped = False

    def initialize(self, state: dict[str, Any]) -> None:
        if "workflow" in state:
            return
        flags = _scenario_flags(state.get("request", {}))
        state["workflow"] = {
            "current_state": WorkflowState.START.value,
            "state_history": [WorkflowState.START.value],
            "comparable_company_research": flags["comparable_company_research"],
            "authoritative_guidance_request": flags["authoritative_guidance_request"],
            "emergency_stop": False,
        }
        self.state_history = state["workflow"]["state_history"]

    def _record_state(self, state: dict[str, Any], new_state: WorkflowState) -> None:
        workflow = state["workflow"]
        workflow["current_state"] = new_state.value
        if workflow["state_history"][-1] != new_state.value:
            workflow["state_history"].append(new_state.value)
        self.state_history = workflow["state_history"]

    def allowed_tools(
        self, state: dict[str, Any], *, record: bool = True
    ) -> list[str]:
        self.initialize(state)
        current = WorkflowState(state["workflow"]["current_state"])
        observations = state.get("observations", {})
        if current is WorkflowState.START:
            allowed = ["analyse_audit_scenario"]
        elif current is WorkflowState.SCENARIO_ANALYSED:
            analysis = observations.get("analyse_audit_scenario", {})
            allowed = (
                ["search_private_corpus"]
                if analysis.get("accounting_topics") and analysis.get("scenario_routing", {}).get("in_scope", True)
                else ["request_more_evidence", "stop_and_summarise"]
            )
        elif current is WorkflowState.EVIDENCE_SEARCHED:
            search = observations.get("search_private_corpus", {})
            if not search.get("results"):
                allowed = ["request_more_evidence", "stop_and_summarise"]
            elif state["workflow"]["authoritative_guidance_request"]:
                allowed = ["check_authority"]
            else:
                allowed = ["inspect_candidate_metadata"]
        elif current is WorkflowState.CANDIDATES_INSPECTED:
            allowed = ["assess_comparability"]
        elif current is WorkflowState.COMPARABILITY_ASSESSED:
            allowed = ["check_authority"]
        elif current is WorkflowState.AUTHORITY_CHECKED:
            authority = observations.get("check_authority", {})
            if (
                state["workflow"]["authoritative_guidance_request"]
                and authority.get("missing_authority_classes")
            ):
                allowed = ["request_more_evidence", "stop_and_summarise"]
            else:
                allowed = ["stop_and_summarise"]
        elif current in {
            WorkflowState.EVIDENCE_GAP_IDENTIFIED,
            WorkflowState.READY_TO_STOP,
        }:
            allowed = ["stop_and_summarise"]
        else:
            allowed = []
        if record:
            self.menu_history.append(
                {
                    "step": len(self.trace) + 1,
                    "state": current.value,
                    "available_tools": allowed,
                }
            )
        return allowed

    def allowed_registry(self, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        registry = {
            name: deepcopy(TOOL_CONTRACTS[name]) for name in self.allowed_tools(state)
        }
        if "inspect_candidate_metadata" in registry:
            registry["inspect_candidate_metadata"]["arguments"]["companies"] = {
                "required_exact_values": self._serious_candidates(state)
            }
        if "assess_comparability" in registry:
            profiles = state.get("observations", {}).get(
                "inspect_candidate_metadata", {}
            ).get("profiles", [])
            registry["assess_comparability"]["arguments"]["companies"] = {
                "required_exact_values": [profile["company"] for profile in profiles]
            }
        return registry

    @staticmethod
    def _serious_candidates(state: dict[str, Any]) -> list[str]:
        companies: list[str] = []
        search = state.get("observations", {}).get("search_private_corpus", {})
        for item in search.get("results", []):
            company = item["company"]
            if company not in companies:
                companies.append(company)
            if len(companies) == 5:
                break
        return companies

    def _validate_arguments(self, decision: PlannerDecision, state: dict[str, Any]) -> None:
        if decision.tool == "analyse_audit_scenario":
            if decision.arguments.get("scenario") != state.get("request", {}).get("scenario"):
                raise AgentPolicyError(
                    "Scenario analysis must use the submitted audit scenario unchanged."
                )
        elif decision.tool == "inspect_candidate_metadata":
            if decision.arguments.get("companies") != self._serious_candidates(state):
                raise AgentPolicyError(
                    "Candidate inspection must cover every serious candidate returned by search."
                )
        elif decision.tool == "assess_comparability":
            profiles = state.get("observations", {}).get(
                "inspect_candidate_metadata", {}
            ).get("profiles", [])
            expected = [profile["company"] for profile in profiles]
            if decision.arguments.get("companies") != expected:
                raise AgentPolicyError(
                    "Comparability assessment must cover every inspected serious candidate."
                )

    def bind_state_derived_arguments(
        self, decision: PlannerDecision, state: dict[str, Any]
    ) -> PlannerDecision:
        """Bind controller-owned scope so a legal action cannot omit required candidates."""
        arguments = dict(decision.arguments)
        if decision.tool == "analyse_audit_scenario":
            required = state["request"]["scenario"]
            if arguments.get("scenario") != required:
                self.guardrails.append(
                    "Controller bound scenario analysis to the submitted audit scenario."
                )
            arguments["scenario"] = required
        elif decision.tool == "inspect_candidate_metadata":
            required = self._serious_candidates(state)
            if arguments.get("companies") != required:
                self.guardrails.append(
                    "Controller bound candidate inspection to every serious retrieved candidate."
                )
            arguments["companies"] = required
        elif decision.tool == "assess_comparability":
            profiles = state.get("observations", {}).get(
                "inspect_candidate_metadata", {}
            ).get("profiles", [])
            required = [profile["company"] for profile in profiles]
            if arguments.get("companies") != required:
                self.guardrails.append(
                    "Controller bound comparability assessment to every inspected serious candidate."
                )
            arguments["companies"] = required
        elif decision.tool == "check_authority":
            arguments = {}
        elif decision.tool == "request_more_evidence" and getattr(self.tools, "routing", {}).get("scope_status") == "out_of_scope":
            arguments = {
                "gap": {
                    "missing_authority_types": [],
                    "missing_business_comparability_evidence": False,
                    "missing_instrument_specific_evidence": False,
                    "missing_reporting_framework_evidence": False,
                },
                "evidence_types": ["different accounting-standard research scope"],
                "reason": self.tools.routing["scope_message"],
            }
        return PlannerDecision(decision.tool, arguments, decision.reason)

    @staticmethod
    def _gap_signature(arguments: dict[str, Any]) -> str:
        gap = arguments.get("gap")
        if not isinstance(gap, dict):
            raise AgentPolicyError(
                "request_more_evidence requires a structured gap signature."
            )
        return json.dumps(gap, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

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
            counts: dict[str, int] = {}
            for item in result.get("assessments", []):
                counts[item["rating"]] = counts.get(item["rating"], 0) + 1
            return "Comparability ratings: " + ", ".join(
                f"{name}={count}" for name, count in counts.items()
            )
        if tool == "check_authority":
            return (
                f"Present authority classes: {', '.join(result.get('present_authority_classes', [])) or 'none'}; "
                f"missing: {', '.join(result.get('missing_authority_classes', [])) or 'none'}."
            )
        if tool == "request_more_evidence":
            return f"Recorded one structured gap requesting {len(result.get('evidence_types', []))} evidence type(s)."
        if tool == "stop_and_summarise":
            return f"Stopped with status {result.get('status', 'unknown')} and human review required."
        return "Tool completed with a bounded structured result."

    def _transition(self, tool: str, result: dict[str, Any], state: dict[str, Any]) -> None:
        if tool == "analyse_audit_scenario":
            self._record_state(state, WorkflowState.SCENARIO_ANALYSED)
        elif tool == "search_private_corpus":
            self._record_state(state, WorkflowState.EVIDENCE_SEARCHED)
        elif tool == "inspect_candidate_metadata":
            self._record_state(state, WorkflowState.CANDIDATES_INSPECTED)
        elif tool == "assess_comparability":
            self._record_state(state, WorkflowState.COMPARABILITY_ASSESSED)
        elif tool == "check_authority":
            self._record_state(state, WorkflowState.AUTHORITY_CHECKED)
            if not (
                state["workflow"]["authoritative_guidance_request"]
                and result.get("missing_authority_classes")
            ):
                self._record_state(state, WorkflowState.READY_TO_STOP)
        elif tool == "request_more_evidence":
            self._record_state(state, WorkflowState.EVIDENCE_GAP_IDENTIFIED)
            self._record_state(state, WorkflowState.READY_TO_STOP)
        elif tool == "stop_and_summarise":
            self._record_state(state, WorkflowState.STOPPED)
            self.stopped = True

    def execute(
        self,
        decision: PlannerDecision,
        state: dict[str, Any],
        *,
        emergency: bool = False,
    ) -> dict[str, Any]:
        self.initialize(state)
        if len(self.trace) >= self.max_steps:
            raise AgentPolicyError(f"Six-step cap reached ({self.max_steps}).")
        if self.stopped:
            raise AgentPolicyError("Research run is already stopped.")
        if decision.tool not in TOOL_CONTRACTS:
            raise AgentPolicyError(f"Tool is not allowlisted: {decision.tool}")
        signature = json.dumps(
            {"tool": decision.tool, "arguments": decision.arguments},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if signature in self.seen_calls:
            raise AgentPolicyError("Duplicate tool call with identical arguments blocked.")
        gap_signature = None
        if decision.tool == "request_more_evidence":
            gap_signature = self._gap_signature(decision.arguments)
            if gap_signature in self.seen_gap_signatures:
                raise AgentPolicyError(
                    "Duplicate unresolved evidence-gap signature blocked."
                )
        legal = self.allowed_tools(state, record=False)
        if not emergency and decision.tool not in legal:
            raise AgentPolicyError(
                f"Illegal state transition blocked: {state['workflow']['current_state']} -> {decision.tool}."
            )
        if emergency and decision.tool != "stop_and_summarise":
            raise AgentPolicyError(
                "Only stop_and_summarise may execute as an emergency action."
            )
        self._validate_arguments(decision, state)
        reason = decision.reason.strip()[:300] or "Bounded planner selected this action."
        if PROHIBITED_JUDGMENT.search(reason):
            reason = "Planner reason withheld because it attempted a prohibited audit judgment."
            self.guardrails.append(
                "Prohibited audit-judgment wording removed from planner reason."
            )
        state_before = state["workflow"]["current_state"]
        started = time.perf_counter()
        result = self.tools.execute(decision.tool, decision.arguments, state)
        elapsed = (time.perf_counter() - started) * 1000
        self.seen_calls.add(signature)
        if gap_signature is not None:
            self.seen_gap_signatures.add(gap_signature)
        state.setdefault("completed_tools", []).append(decision.tool)
        state.setdefault("observations", {})[decision.tool] = result
        self._transition(decision.tool, result, state)
        self.trace.append(
            AgentTraceEntry(
                step=len(self.trace) + 1,
                state_before=state_before,
                action=decision.tool,
                reason=reason,
                arguments=decision.arguments,
                result_summary=self._result_summary(decision.tool, result),
                state_after=state["workflow"]["current_state"],
                planner_mode=self.planner_mode,
                elapsed_ms=round(elapsed, 3),
            )
        )
        return result

    def emergency_stop(self, state: dict[str, Any], reason: str) -> dict[str, Any]:
        self.initialize(state)
        state["workflow"]["emergency_stop"] = True
        return self.execute(
            PlannerDecision(
                "stop_and_summarise",
                {"reason": reason},
                "Stop safely after a controller policy intervention.",
            ),
            state,
            emergency=True,
        )


def _comparison_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "assessments": [
            {
                "company": item["company"],
                "rating": item["rating"],
                "weighted_score": item["weighted_score"],
                "dimension_scores": {
                    name: dimension["score"]
                    for name, dimension in item.get("dimensions", {}).items()
                },
            }
            for item in result.get("assessments", [])
        ]
    }


def _search_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "result_count": result.get("result_count", 0),
        "companies": list(
            dict.fromkeys(item["company"] for item in result.get("results", []))
        ),
        "authority_classes": sorted(
            {item["authority_class"] for item in result.get("results", [])}
        ),
        "raw_text_returned_to_planner": False,
    }


def _planner_state_view(
    state: dict[str, Any], allowed_tools: list[str]
) -> dict[str, Any]:
    observations = state.get("observations", {})
    selected: dict[str, Any] = {}
    allowed = set(allowed_tools)
    if "search_private_corpus" in allowed:
        selected["analyse_audit_scenario"] = observations.get(
            "analyse_audit_scenario", {}
        )
    if "inspect_candidate_metadata" in allowed:
        selected["search_private_corpus"] = observations.get(
            "search_private_corpus", {}
        )
    if "assess_comparability" in allowed:
        selected["analyse_audit_scenario"] = observations.get(
            "analyse_audit_scenario", {}
        )
        selected["inspect_candidate_metadata"] = observations.get(
            "inspect_candidate_metadata", {}
        )
    if "check_authority" in allowed:
        selected["search_private_corpus"] = _search_summary(
            observations.get("search_private_corpus", {})
        )
        if "assess_comparability" in observations:
            selected["assess_comparability"] = _comparison_summary(
                observations["assess_comparability"]
            )
    if "request_more_evidence" in allowed:
        selected["analyse_audit_scenario"] = observations.get(
            "analyse_audit_scenario", {}
        )
        if "check_authority" in observations:
            selected["check_authority"] = observations["check_authority"]
        elif "search_private_corpus" in observations:
            selected["search_private_corpus"] = _search_summary(
                observations["search_private_corpus"]
            )
    if "stop_and_summarise" in allowed:
        if "assess_comparability" in observations:
            selected["assess_comparability"] = _comparison_summary(
                observations["assess_comparability"]
            )
        for name in ("check_authority", "request_more_evidence"):
            if name in observations:
                selected[name] = observations[name]
    workflow = dict(state["workflow"])
    workflow["available_tools"] = allowed_tools
    return {
        "request": dict(state["request"]),
        "completed_tools": list(state.get("completed_tools", [])),
        "observations": selected,
        "workflow": workflow,
    }


@dataclass(frozen=True)
class AgentResearchResult:
    mode: str
    planner_model: str | None
    step_count: int
    step_limit: int
    stopped_early: bool
    state_transition_sequence: list[str]
    dynamic_tool_menus: list[dict[str, Any]]
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
    tools = LocalResearchTools(chunks, candidates, request=request)
    active_planner = (
        planner or OpenRouterPlanner.from_environment() or DeterministicFallbackPlanner()
    )
    mode = active_planner.mode
    model = getattr(active_planner, "model", None)
    metered_planners = [active_planner]
    controller = BoundedAgentController(
        tools, max_steps=max_steps, planner_mode=mode
    )
    state: dict[str, Any] = {
        "request": {
            "scenario": request.scenario,
            "topic": request.topic,
            "industry": request.industry,
            "transaction_type": request.transaction_type,
            "reporting_period": request.reporting_period,
            "required_framework": request.required_framework,
            "search_text": request.search_text(),
            "scenario_routing": tools.routing,
            "authority_coverage": tools.coverage,
            "official_authority_cards": [card.planner_payload() for card in tools.authority_cards],
        },
        "completed_tools": [],
        "observations": {},
    }
    controller.initialize(state)
    forbidden_texts = [chunk.text for chunk in chunks]
    while not controller.stopped and len(controller.trace) < max_steps:
        remaining = max_steps - len(controller.trace)
        registry = controller.allowed_registry(state)
        allowed_tools = list(registry)
        if not allowed_tools:
            controller.guardrails.append(
                "No legal tool remained; controller stopped safely."
            )
            controller.emergency_stop(state, "No legal workflow action remained.")
            break
        if remaining == 1 and "stop_and_summarise" not in registry:
            controller.guardrails.append(
                "Final step reserved for an emergency stop because the workflow was incomplete."
            )
            controller.emergency_stop(
                state,
                "The six-step budget ended before required workflow checks completed.",
            )
            break
        planner_state = _planner_state_view(state, allowed_tools)
        try:
            decision = active_planner.choose_next(
                planner_state, registry, remaining, forbidden_texts
            )
        except PlannerTransportError as exc:
            controller.guardrails.append(
                f"Model planner transport failed safely: {exc}"
            )
            active_planner = DeterministicFallbackPlanner()
            metered_planners.append(active_planner)
            mode = "deterministic fallback after model-planner transport error"
            controller.planner_mode = mode
            decision = active_planner.choose_next(
                planner_state, registry, remaining, forbidden_texts
            )
        except (PlannerResponseError, PlannerError) as exc:
            controller.guardrails.append(f"Invalid planner response blocked: {exc}")
            controller.emergency_stop(
                state, "The planner returned an invalid workflow action."
            )
            break
        try:
            decision = controller.bind_state_derived_arguments(decision, state)
            controller.execute(decision, state)
        except AgentPolicyError as exc:
            controller.guardrails.append(str(exc))
            if len(controller.trace) < max_steps:
                controller.emergency_stop(
                    state, "Controller policy blocked the planner action."
                )
            break
        except (KeyError, TypeError, ValueError) as exc:
            controller.guardrails.append(
                f"Invalid planner tool arguments blocked ({type(exc).__name__})."
            )
            if len(controller.trace) < max_steps:
                controller.emergency_stop(
                    state, "Planner supplied invalid tool arguments."
                )
            break

    handoff = state.get("observations", {}).get("stop_and_summarise", {})
    if not handoff:
        state["workflow"]["emergency_stop"] = True
        handoff = tools.stop_and_summarise(
            "The research budget ended before an explicit stop action.", state=state
        )
        controller.guardrails.append(
            "Controller created a safe handoff at the step limit."
        )
    serialized_handoff = json.dumps(handoff, ensure_ascii=False)
    if PROHIBITED_JUDGMENT.search(serialized_handoff):
        raise AgentPolicyError(
            "Structured handoff contains prohibited audit-judgment wording."
        )
    observations = state.get("observations", {})
    analysis = observations.get("analyse_audit_scenario", {})
    profiles = observations.get("inspect_candidate_metadata", {}).get("profiles", [])
    comparisons = observations.get("assess_comparability", {}).get(
        "assessments", []
    )
    authority = observations.get("check_authority", {})
    elapsed = (time.perf_counter() - started) * 1000
    return AgentResearchResult(
        mode=mode,
        planner_model=model,
        step_count=len(controller.trace),
        step_limit=max_steps,
        stopped_early=len(controller.trace) < max_steps,
        state_transition_sequence=list(controller.state_history),
        dynamic_tool_menus=controller.menu_history,
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
