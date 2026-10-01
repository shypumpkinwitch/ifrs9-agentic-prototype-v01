from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class PlannerError(RuntimeError):
    """Raised when a planner response is invalid or unsafe."""


class PlannerTransportError(PlannerError):
    """Raised when the configured planner provider is unavailable."""


class PlannerResponseError(PlannerError):
    """Raised when a planner response violates the controller contract."""


@dataclass(frozen=True)
class PlannerDecision:
    tool: str
    arguments: dict[str, Any]
    reason: str


class DeterministicFallbackPlanner:
    """Truthfully labelled offline fallback; it does not simulate model planning."""

    mode = "deterministic fallback workflow"
    model = None

    def choose_next(
        self,
        state: dict[str, Any],
        tool_registry: dict[str, dict[str, Any]],
        remaining_steps: int,
        forbidden_texts: list[str],
    ) -> PlannerDecision:
        observations = state.get("observations", {})
        legal = set(tool_registry)
        if "analyse_audit_scenario" in legal:
            return PlannerDecision(
                "analyse_audit_scenario",
                {"scenario": state["request"]["scenario"]},
                "Structure the scenario before searching for evidence.",
            )
        if "search_private_corpus" in legal:
            return PlannerDecision(
                "search_private_corpus",
                {"query": state["request"]["search_text"], "top_k": 10},
                "Search the verified local corpus using the analysed scenario.",
            )
        search_results = observations.get("search_private_corpus", {}).get("results", [])
        if "inspect_candidate_metadata" in legal:
            companies: list[str] = []
            for item in search_results:
                if item["company"] not in companies:
                    companies.append(item["company"])
                if len(companies) == 5:
                    break
            return PlannerDecision(
                "inspect_candidate_metadata",
                {"companies": companies},
                "Inspect every serious candidate returned by the bounded search.",
            )
        if "assess_comparability" in legal:
            profiles = observations.get("inspect_candidate_metadata", {}).get("profiles", [])
            return PlannerDecision(
                "assess_comparability",
                {"companies": [profile["company"] for profile in profiles]},
                "Assess every inspected candidate across the required comparability dimensions.",
            )
        if "check_authority" in legal:
            return PlannerDecision(
                "check_authority",
                {},
                "Verify authority classes before any research handoff.",
            )
        if "request_more_evidence" in legal:
            authority = observations.get("check_authority", {})
            missing_authorities = authority.get("missing_authority_classes", [])
            analysis = observations.get("analyse_audit_scenario", {})
            supported_topic = bool(analysis.get("accounting_topics"))
            gap = {
                "missing_authority_types": missing_authorities,
                "missing_business_comparability_evidence": not supported_topic,
                "missing_instrument_specific_evidence": not supported_topic,
                "missing_reporting_framework_evidence": False,
            }
            return PlannerDecision(
                "request_more_evidence",
                {
                    "gap": gap,
                    "evidence_types": missing_authorities
                    or [
                        "clarified IFRS 9 accounting question",
                        "transaction-specific source material",
                    ],
                    "reason": "The current bounded evidence state cannot support further research without the identified material.",
                },
                "Record the unresolved evidence gap once before stopping.",
            )
        if "stop_and_summarise" in legal:
            return PlannerDecision(
                "stop_and_summarise",
                {"reason": "The controller-defined workflow is complete or cannot continue safely."},
                "Stop with a structured research handoff for human review.",
            )
        raise PlannerResponseError("Controller exposed no legal deterministic action.")


Transport = Callable[[dict[str, Any], dict[str, str], str], dict[str, Any]]


def assert_safe_planner_payload(
    body: dict[str, Any], forbidden_texts: list[str]
) -> dict[str, Any]:
    """Validate the outbound planner envelope and return its structured context."""
    if set(body) != {"model", "temperature", "response_format", "messages"}:
        raise PlannerResponseError("Planner payload contains an unexpected top-level field.")
    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise PlannerResponseError("Planner payload must contain exactly two messages.")
    if [message.get("role") for message in messages] != ["system", "user"]:
        raise PlannerResponseError("Planner payload roles are invalid.")
    try:
        context = json.loads(messages[1]["content"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise PlannerResponseError("Planner user context must be structured JSON.") from exc
    if set(context) != {"remaining_steps", "tools", "research_state"}:
        raise PlannerResponseError("Planner context contains an unexpected field.")
    state = context.get("research_state")
    if not isinstance(state, dict) or set(state) != {
        "request",
        "completed_tools",
        "observations",
        "workflow",
    }:
        raise PlannerResponseError("Planner research state contains an unexpected field.")

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            prohibited = {
                "api_key",
                "authorization",
                "secret",
                "source_body",
                "raw_source_text",
                "text",
            }
            offending = {str(key).casefold() for key in value} & prohibited
            if offending:
                raise PlannerResponseError(
                    "Planner context contains a prohibited source or secret field."
                )
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(context)
    serialized = json.dumps(body, ensure_ascii=False)
    leaked = [text for text in forbidden_texts if len(text) >= 40 and text in serialized]
    if leaked:
        raise PlannerResponseError("Raw local source text was blocked from the planner payload.")
    return context


def _default_transport(body: dict[str, Any], headers: dict[str, str], endpoint: str) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PlannerTransportError(
            f"Planner request failed safely: {type(exc).__name__}"
        ) from exc


class OpenRouterPlanner:
    mode = "model-planned bounded agent"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "openai/gpt-4o-mini",
        base_url: str = "https://openrouter.ai/api/v1",
        transport: Transport | None = None,
    ):
        if not api_key:
            raise ValueError("OpenRouter API key is required for model planning.")
        self.api_key = api_key
        self.model = model
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.transport = transport or _default_transport
        self.payloads: list[dict[str, Any]] = []
        self.audit_events: list[dict[str, Any]] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0

    @classmethod
    def from_environment(cls, *, transport: Transport | None = None) -> "OpenRouterPlanner | None":
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            return None
        return cls(
            key,
            model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            transport=transport,
        )

    @staticmethod
    def _parse_json_content(content: Any) -> dict[str, Any]:
        if not isinstance(content, str):
            raise PlannerResponseError("Planner content must be a JSON string.")
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PlannerResponseError("Planner returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise PlannerResponseError("Planner decision must be a JSON object.")
        return parsed

    def choose_next(
        self,
        state: dict[str, Any],
        tool_registry: dict[str, dict[str, Any]],
        remaining_steps: int,
        forbidden_texts: list[str],
    ) -> PlannerDecision:
        planner_context = {
            "remaining_steps": remaining_steps,
            "tools": tool_registry,
            "research_state": state,
        }
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a bounded research planner. Choose exactly one currently available read-only tool. "
                        "The controller exposes only legal tools for the current workflow state; unavailable tools are invalid. "
                        "Return JSON with tool, arguments, and a concise business-facing reason. Do not provide "
                        "hidden reasoning, an accounting conclusion, or a claim that client treatment is correct, "
                        "compliant, or appropriate. Company disclosure is not authoritative IFRS guidance. "
                        "Use the structured state and exact argument contract. Never repeat an unresolved evidence-gap "
                        "signature. Stop when the controller exposes only the stop tool."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(planner_context, ensure_ascii=False, sort_keys=True),
                },
            ],
        }
        validated_context = assert_safe_planner_payload(body, forbidden_texts)
        serialized = json.dumps(body, ensure_ascii=False, sort_keys=True)
        self.payloads.append(body)
        response = self.transport(
            body,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            self.endpoint,
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PlannerResponseError("Planner response is missing message content.") from exc
        decision = self._parse_json_content(content)
        tool = decision.get("tool")
        arguments = decision.get("arguments", {})
        reason = decision.get("reason", "Planner selected the next bounded research action.")
        if tool not in tool_registry:
            raise PlannerResponseError(
                f"Planner selected a tool unavailable in the current state: {tool}"
            )
        if not isinstance(arguments, dict) or not isinstance(reason, str):
            raise PlannerResponseError(
                "Planner decision has invalid argument or reason types."
            )
        usage = response.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        provider_cost_available = usage.get("cost") is not None
        provider_cost = float(usage.get("cost") or 0.0)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += provider_cost
        choice = response.get("choices", [{}])[0]
        self.audit_events.append(
            {
                "request": {
                    "request_number": len(self.audit_events) + 1,
                    "model": self.model,
                    "payload_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                    "remaining_steps": validated_context["remaining_steps"],
                    "scenario": state.get("request", {}).get("scenario", ""),
                    "registered_tools": list(tool_registry),
                    "completed_tools": list(state.get("completed_tools", [])),
                    "structured_observations": sorted(state.get("observations", {})),
                    "outbound_categories": [
                        "audit scenario",
                        "tool contracts",
                        "structured metadata",
                        "retrieval ranks and scores",
                        "authority labels",
                        "locally derived non-verbatim features",
                        "current loop state",
                    ],
                    "raw_annual_report_text_included": False,
                    "authorization_header_saved": False,
                },
                "response": {
                    "response_id": response.get("id"),
                    "provider_model": response.get("model"),
                    "finish_reason": choice.get("finish_reason"),
                    "action": tool,
                    "arguments": arguments,
                    "reason_summary": reason.strip()[:300],
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "provider_reported_cost_available": provider_cost_available,
                    "provider_reported_cost_usd": provider_cost,
                },
            }
        )
        return PlannerDecision(tool=tool, arguments=arguments, reason=reason)
