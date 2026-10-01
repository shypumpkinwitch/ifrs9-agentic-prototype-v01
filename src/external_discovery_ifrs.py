from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .agent_planner import (
    OpenRouterPlanner,
    PlannerDecision,
    PlannerError,
    PlannerResponseError,
    PlannerTransportError,
)
from .external_discovery import (
    ANNUAL_FORMS,
    ExternalDiscoveryError,
    ExternalDiscoveryTools,
    ExternalNetworkError,
    ExternalPolicyError,
    Gate5DeterministicPlanner,
    SecEdgarClient,
    derive_external_features,
    extract_visible_text,
    parse_sec_search_response,
    verify_framework_from_text,
)
from .schemas import Candidate, EvidenceChunk, ResearchRequest


IFRS_ACCEPTED_STATUSES = {
    "IFRS_AS_ISSUED_BY_IASB_VERIFIED",
    "IFRS_AS_ADOPTED_BY_JURISDICTION_VERIFIED",
}

PROPERTY_SIC_CODES = {
    "1521", "1531", "1541", "1542", "6500", "6512", "6513", "6519",
    "6531", "6552", "6798",
}
FINANCIAL_SIC_PREFIXES = ("60", "61", "62")


def classify_candidate_business_from_sic(raw_sic: str) -> dict[str, Any]:
    codes = re.findall(r"\d{4}", str(raw_sic))
    if any(code in PROPERTY_SIC_CODES for code in codes):
        return {
            "status": "property_or_real_estate",
            "eligible_for_deep_property_comparison": True,
            "sic_codes": codes,
        }
    if any(code.startswith(FINANCIAL_SIC_PREFIXES) for code in codes):
        return {
            "status": "financial_institution_business_mismatch",
            "eligible_for_deep_property_comparison": False,
            "sic_codes": codes,
        }
    return {
        "status": "business_classification_pending",
        "eligible_for_deep_property_comparison": False,
        "sic_codes": codes,
    }


class Gate51Tools(ExternalDiscoveryTools):
    """IFRS-targeted SEC lane that verifies framework before deep retrieval."""

    def discover_ifrs_candidates(self, *, max_candidates: int = 3) -> dict[str, Any]:
        if max_candidates < 1 or max_candidates > 3:
            raise ExternalPolicyError("At most three IFRS-targeted candidates may be discovered.")
        query_specs = [
            ("expected credit loss property development", "ecl-property-development"),
            ("development loans real estate IFRS 9", "development-loans-ifrs9"),
        ]
        merged: dict[str, dict[str, Any]] = {}
        search_urls = []
        for query, label in query_specs:
            params = urllib.parse.urlencode(
                {
                    "q": query,
                    "forms": "20-F",
                    "dateRange": "custom",
                    "startdt": "2022-01-01",
                    "enddt": "2026-09-30",
                    "from": 0,
                    "size": 20,
                }
            )
            url = f"https://efts.sec.gov/LATEST/search-index?{params}"
            search_urls.append(url)
            payload = self.sec.get_json(url, purpose=f"IFRS-targeted candidate discovery: {label}")
            for candidate in parse_sec_search_response(payload, query_label=label):
                if not candidate["discovery_form"].startswith("20-F"):
                    continue
                candidate["discovery_reason"] = (
                    "SEC 20-F full-text result for property-development, lending, and ECL features; "
                    "20-F status is only a search constraint and is not framework evidence."
                )
                candidate["required_reporting_framework"] = "IFRS"
                previous = merged.get(candidate["cik"])
                if previous is None or candidate["sec_relevance_score"] > previous["sec_relevance_score"]:
                    merged[candidate["cik"]] = candidate
        candidates = sorted(
            merged.values(),
            key=lambda item: (-float(item["sec_relevance_score"]), item["company"]),
        )[:max_candidates]
        return {
            "source": "SEC EDGAR Full-Text Search",
            "form_search_constraint": "20-F",
            "form_is_framework_evidence": False,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "query_count": len(query_specs),
            "search_urls": search_urls,
            "bounded_to_sec": True,
        }

    def locate_public_filing(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        result = super().locate_public_filing(candidates)
        by_cik = {item["cik"]: item for item in candidates}
        for filing in result["filings"]:
            candidate = by_cik.get(filing["cik"], {})
            filing["discovery_sic"] = candidate.get("sic", "")
            filing["discovery_reason"] = candidate.get("discovery_reason", "")
            filing["business_classification"] = classify_candidate_business_from_sic(
                filing["discovery_sic"]
            )
        return result

    def download_framework_filings(
        self, filings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        eligible = [item for item in filings if item.get("filing_found")][:3]
        downloads = []
        for filing in eligible:
            body, content_type = self.sec.get_bytes(
                filing["filing_url"],
                purpose=f"framework-verification filing {filing['accession_number']}",
            )
            accession_key = filing["accession_number"].replace("-", "")
            doc_id = f"SEC-{filing['cik']}-{accession_key}"
            suffix = Path(filing["primary_document"]).suffix or ".bin"
            path = self.runtime_root / "raw" / filing["cik"] / accession_key / f"primary{suffix}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            text = extract_visible_text(body, content_type)
            self._documents[doc_id] = {"filing": dict(filing), "path": path, "sha256": digest}
            self._texts[doc_id] = text
            downloads.append(
                {
                    "local_document_id": doc_id,
                    "company": filing["company"],
                    "cik": filing["cik"],
                    "form": filing["form"],
                    "accession_number": filing["accession_number"],
                    "filing_url": filing["filing_url"],
                    "sha256": digest,
                    "byte_count": len(body),
                    "content_type": content_type.split(";", 1)[0],
                    "raw_text_returned_to_planner": False,
                }
            )
        return {
            "downloads": downloads,
            "download_count": len(downloads),
            "filings_per_candidate": 1,
            "per_accepted_candidate_limit": 2,
            "storage_boundary": "external_runtime/raw (gitignored)",
        }

    def verify_candidate_frameworks(
        self, document_ids: list[str]
    ) -> dict[str, Any]:
        if not document_ids or len(document_ids) > 3:
            raise ExternalPolicyError("Verify between one and three downloaded candidate filings.")
        results = []
        accepted_ids = []
        for doc_id in document_ids:
            record = self._documents.get(doc_id)
            if not record:
                raise ExternalPolicyError("Framework verification requires a downloaded filing.")
            filing = record["filing"]
            result = verify_framework_from_text(self._texts[doc_id], form=filing["form"])
            status = result["status"]
            business = filing.get("business_classification") or classify_candidate_business_from_sic(
                filing.get("discovery_sic", "")
            )
            if status in IFRS_ACCEPTED_STATUSES and business["eligible_for_deep_property_comparison"]:
                decision = "accepted_for_deep_analysis"
                accepted_ids.append(doc_id)
            elif status in IFRS_ACCEPTED_STATUSES and business["status"] == "financial_institution_business_mismatch":
                decision = "rejected_business_before_deep_analysis"
            elif status in IFRS_ACCEPTED_STATUSES:
                decision = "pending_business_not_deeply_analysed"
            elif status == "PENDING_INSUFFICIENT_EVIDENCE":
                decision = "pending_framework_not_deeply_analysed"
            else:
                decision = "rejected_framework_before_deep_analysis"
            result.update(
                {
                    "local_document_id": doc_id,
                    "company": filing["company"],
                    "cik": filing["cik"],
                    "form": filing["form"],
                    "accession_number": filing["accession_number"],
                    "filing_url": filing["filing_url"],
                    "evidence_type": "issuer-specific filing basis/auditor phrase pattern",
                    "decision": decision,
                    "business_classification": business,
                    "form_is_not_framework_evidence": True,
                    "raw_text_returned_to_planner": False,
                }
            )
            results.append(result)
        return {
            "framework_results": results,
            "accepted_document_ids": accepted_ids,
            "accepted_count": len(accepted_ids),
            "early_rejection_count": sum(
                item["decision"] == "rejected_framework_before_deep_analysis"
                for item in results
            ),
            "pending_count": sum(
                item["decision"] == "pending_framework_not_deeply_analysed"
                for item in results
            ),
        }

    def search_verified_ifrs_filings(
        self, document_ids: list[str], *, query_features: list[str]
    ) -> dict[str, Any]:
        if len(document_ids) > 3:
            raise ExternalPolicyError("At most three verified IFRS candidates may be searched.")
        if not document_ids:
            return {
                "searches": [],
                "searched_document_count": 0,
                "reason": "No candidate had verified IFRS framework evidence.",
            }
        searches = []
        for doc_id in document_ids:
            record = self._documents.get(doc_id)
            if not record:
                raise ExternalPolicyError("Verified IFRS filing must be downloaded before local search.")
            filing = record["filing"]
            derived = derive_external_features(self._texts[doc_id])
            derived.update(
                {
                    "local_document_id": doc_id,
                    "company": filing["company"],
                    "cik": filing["cik"],
                    "form": filing["form"],
                    "accession_number": filing["accession_number"],
                    "filing_url": filing["filing_url"],
                    "query_features": list(query_features),
                    "authority_class": "COMPANY_DISCLOSURE",
                }
            )
            searches.append(derived)
        return {"searches": searches, "searched_document_count": len(document_ids)}

    def assess_ifrs_comparability(
        self,
        *,
        discovered_candidates: list[dict[str, Any]],
        framework_results: list[dict[str, Any]],
        searches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        framework_by_cik = {item["cik"]: item for item in framework_results}
        search_by_cik = {item["cik"]: item for item in searches}
        assessments = []
        for candidate in discovered_candidates:
            framework = framework_by_cik.get(candidate["cik"])
            status = framework["status"] if framework else "PENDING_INSUFFICIENT_EVIDENCE"
            framework_decision = framework.get("decision") if framework else "pending_framework_not_deeply_analysed"
            if framework_decision != "accepted_for_deep_analysis":
                pending = framework_decision.startswith("pending")
                if framework_decision == "rejected_business_before_deep_analysis":
                    reason = "SEC SIC metadata identifies a financial-institution business model, not a property-development issuer; deep property comparability was skipped."
                elif pending and status in IFRS_ACCEPTED_STATUSES:
                    reason = "IASB IFRS was verified, but issuer business classification was insufficient for deep property comparability."
                elif pending:
                    reason = "Issuer-specific framework evidence was insufficient; 20-F status alone was not accepted."
                else:
                    reason = f"Issuer-specific framework evidence established {status}, not a qualifying IFRS basis."
                assessments.append(
                    {
                        "company": framework["company"] if framework else candidate["company"],
                        "cik": candidate["cik"],
                        "filing_form": framework.get("form") if framework else candidate["discovery_form"],
                        "accession_number": framework.get("accession_number") if framework else candidate.get("discovery_accession"),
                        "discovery_reason": candidate["discovery_reason"],
                        "framework_status": status,
                        "framework_evidence_type": framework.get("evidence_type") if framework else "none",
                        "decision": "pending" if pending else "rejected",
                        "deep_comparability_performed": False,
                        "rating": "insufficient",
                        "weighted_score": 0.0,
                        "rejection_reason": (
                            reason
                        ),
                        "authority_class": "COMPANY_DISCLOSURE",
                    }
                )
                continue
            search = search_by_cik.get(candidate["cik"])
            if not search:
                assessments.append(
                    {
                        "company": framework["company"],
                        "cik": candidate["cik"],
                        "filing_form": framework["form"],
                        "accession_number": framework["accession_number"],
                        "discovery_reason": candidate["discovery_reason"],
                        "framework_status": status,
                        "framework_evidence_type": framework["evidence_type"],
                        "decision": "pending",
                        "deep_comparability_performed": False,
                        "rating": "insufficient",
                        "weighted_score": 0.0,
                        "rejection_reason": "Verified IFRS candidate lacked a completed local disclosure search.",
                        "authority_class": "COMPANY_DISCLOSURE",
                    }
                )
                continue
            parent = super().assess_external_comparability(
                discovered_candidates=[candidate],
                framework_results=[framework],
                searches=[search],
            )["assessments"][0]
            if (
                search["feature_counts"].get("development_partner_financing", 0) == 0
                and parent["rating"] == "strong"
            ):
                parent["rating"] = "partial"
                parent["comparability_rationale"] = (
                    "The issuer is a property/real-estate business under verified IASB IFRS and has relevant ECL features, "
                    "but only generic loan/receivable evidence was detected; development-partner financing was not established."
                )
            useful = parent["status"] == "useful_with_limitations"
            assessments.append(
                {
                    **parent,
                    "filing_form": framework["form"],
                    "discovery_reason": candidate["discovery_reason"],
                    "framework_evidence_type": framework["evidence_type"],
                    "decision": "accepted" if useful else "rejected",
                    "deep_comparability_performed": True,
                    "rejection_reason": None if useful else "; ".join(parent.get("rejection_reasons", [])),
                }
            )
        assessments.sort(key=lambda item: (-item["weighted_score"], item["company"]))
        return {
            "assessments": assessments,
            "verified_ifrs_candidate_found": any(
                item["framework_status"] in IFRS_ACCEPTED_STATUSES for item in assessments
            ),
            "useful_ifrs_comparator_found": any(
                item["decision"] == "accepted"
                and item["framework_status"] in IFRS_ACCEPTED_STATUSES
                for item in assessments
            ),
        }

    def verify_allied_framework_separately(self) -> dict[str, Any]:
        allied = [chunk for chunk in self.private_chunks if chunk.company == "Allied_REIT"]
        combined = " ".join(chunk.text for chunk in allied)
        result = verify_framework_from_text(combined, form="annual-report-extracts")
        generic_refs = []
        for chunk in allied:
            lowered = chunk.text.casefold()
            count = lowered.count("ifrs") + lowered.count("international financial reporting standards")
            if count:
                generic_refs.append(
                    {
                        "chunk_id": chunk.chunk_id,
                        "pdf_page": chunk.pdf_page,
                        "generic_ifrs_reference_count": count,
                    }
                )
        if result["status"] == "PENDING_INSUFFICIENT_EVIDENCE":
            result = {
                "status": "PENDING_INSUFFICIENT_EVIDENCE",
                "verified": False,
                "evidence_type": "available frozen annual-report extracts",
                "verified_basis": "Generic IFRS terminology is present, but no exact issuer basis-of-preparation or auditor-report evidence establishing IASB IFRS is available in the 11 Allied_REIT chunks.",
                "generic_reference_metadata": generic_refs,
                "source_record_count": len(allied),
                "frozen_corpus_modified": False,
            }
        else:
            result.update(
                {
                    "evidence_type": "available frozen annual-report extracts",
                    "verified_basis": result["status"],
                    "generic_reference_metadata": generic_refs,
                    "source_record_count": len(allied),
                    "frozen_corpus_modified": False,
                }
            )
        artifact = {
            "classification": "separate runtime source-registry result; not part of the frozen corpus",
            "company": "Allied_REIT",
            **result,
        }
        path = self.runtime_root / "source_registry" / "allied_framework_verification_v01.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            **artifact,
            "runtime_artifact": "source_registry/allied_framework_verification_v01.json",
            "raw_text_returned_to_planner": False,
        }


GATE51_TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "analyse_audit_scenario": {"intent": "Extract scenario features.", "arguments": {}},
    "discover_ifrs_candidates": {"intent": "Find up to three SEC 20-F candidates; form is not framework proof.", "arguments": {}},
    "locate_public_filing": {"intent": "Locate each issuer's official annual filing.", "arguments": {}},
    "download_framework_filings": {"intent": "Download one filing per candidate locally for framework verification.", "arguments": {}},
    "verify_candidate_frameworks": {"intent": "Verify framework from issuer-specific filing evidence and reject non-IFRS early.", "arguments": {}},
    "search_verified_ifrs_filings": {"intent": "Search only verified IFRS filings locally.", "arguments": {}},
    "assess_ifrs_comparability": {"intent": "Assess verified IFRS candidates and preserve all rejection/pending decisions.", "arguments": {}},
    "verify_allied_framework_separately": {"intent": "Verify Allied_REIT separately without changing the frozen corpus.", "arguments": {}},
    "check_authority": {"intent": "Separate company disclosure from missing authoritative IFRS guidance.", "arguments": {}},
    "stop_and_summarise": {"intent": "Create the auditor-review handoff.", "arguments": {}},
}


class Gate51State(str, Enum):
    START = "START"
    SCENARIO_ANALYSED = "SCENARIO_ANALYSED"
    IFRS_CANDIDATES_DISCOVERED = "IFRS_CANDIDATES_DISCOVERED"
    FILINGS_LOCATED = "FILINGS_LOCATED"
    FRAMEWORK_FILINGS_DOWNLOADED = "FRAMEWORK_FILINGS_DOWNLOADED"
    FRAMEWORKS_VERIFIED_AND_FILTERED = "FRAMEWORKS_VERIFIED_AND_FILTERED"
    VERIFIED_IFRS_EVIDENCE_SEARCHED = "VERIFIED_IFRS_EVIDENCE_SEARCHED"
    IFRS_COMPARABILITY_ASSESSED = "IFRS_COMPARABILITY_ASSESSED"
    ALLIED_FRAMEWORK_CHECKED = "ALLIED_FRAMEWORK_CHECKED"
    AUTHORITY_CHECKED = "AUTHORITY_CHECKED"
    STOPPED = "STOPPED"


GATE51_SEQUENCE: list[tuple[Gate51State, str, Gate51State]] = [
    (Gate51State.START, "analyse_audit_scenario", Gate51State.SCENARIO_ANALYSED),
    (Gate51State.SCENARIO_ANALYSED, "discover_ifrs_candidates", Gate51State.IFRS_CANDIDATES_DISCOVERED),
    (Gate51State.IFRS_CANDIDATES_DISCOVERED, "locate_public_filing", Gate51State.FILINGS_LOCATED),
    (Gate51State.FILINGS_LOCATED, "download_framework_filings", Gate51State.FRAMEWORK_FILINGS_DOWNLOADED),
    (Gate51State.FRAMEWORK_FILINGS_DOWNLOADED, "verify_candidate_frameworks", Gate51State.FRAMEWORKS_VERIFIED_AND_FILTERED),
    (Gate51State.FRAMEWORKS_VERIFIED_AND_FILTERED, "search_verified_ifrs_filings", Gate51State.VERIFIED_IFRS_EVIDENCE_SEARCHED),
    (Gate51State.VERIFIED_IFRS_EVIDENCE_SEARCHED, "assess_ifrs_comparability", Gate51State.IFRS_COMPARABILITY_ASSESSED),
    (Gate51State.IFRS_COMPARABILITY_ASSESSED, "verify_allied_framework_separately", Gate51State.ALLIED_FRAMEWORK_CHECKED),
    (Gate51State.ALLIED_FRAMEWORK_CHECKED, "check_authority", Gate51State.AUTHORITY_CHECKED),
    (Gate51State.AUTHORITY_CHECKED, "stop_and_summarise", Gate51State.STOPPED),
]


@dataclass(frozen=True)
class Gate51Result:
    mode: str
    planner_model: str | None
    step_count: int
    step_limit: int
    state_transition_sequence: list[str]
    trace: list[dict[str, Any]]
    external_request_log: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    filings: list[dict[str, Any]]
    framework_results: list[dict[str, Any]]
    deep_searches: list[dict[str, Any]]
    comparability: list[dict[str, Any]]
    allied_framework: dict[str, Any]
    authority: dict[str, Any]
    handoff: dict[str, Any]
    guardrails_triggered: list[str]
    network_failures: list[dict[str, Any]]
    planner_input_tokens: int
    planner_output_tokens: int
    provider_cost_usd: float

    def safe_export(self) -> dict[str, Any]:
        return asdict(self)


class Gate51Controller:
    def __init__(self, tools: Gate51Tools, *, max_steps: int = 10):
        if max_steps < 1 or max_steps > 10:
            raise ValueError("Gate 5.1 permits between one and ten total tool steps.")
        self.tools = tools
        self.max_steps = max_steps
        self.current = Gate51State.START
        self.states = [self.current.value]
        self.trace: list[dict[str, Any]] = []
        self.guardrails: list[str] = []
        self.seen_signatures: set[str] = set()

    def allowed_registry(self) -> dict[str, dict[str, Any]]:
        for before, tool, _ in GATE51_SEQUENCE:
            if before is self.current:
                return {tool: GATE51_TOOL_CONTRACTS[tool]}
        return {}

    def bind(self, decision: PlannerDecision, state: dict[str, Any]) -> PlannerDecision:
        observations = state["observations"]
        tool = decision.tool
        if tool == "analyse_audit_scenario":
            arguments = {"scenario": state["request"]["scenario"]}
        elif tool == "discover_ifrs_candidates":
            arguments = {"max_candidates": 3}
        elif tool == "locate_public_filing":
            arguments = {"candidates": observations["discover_ifrs_candidates"]["candidates"]}
        elif tool == "download_framework_filings":
            arguments = {"filings": observations["locate_public_filing"]["filings"]}
        elif tool == "verify_candidate_frameworks":
            arguments = {"document_ids": [item["local_document_id"] for item in observations["download_framework_filings"]["downloads"]]}
        elif tool == "search_verified_ifrs_filings":
            arguments = {
                "document_ids": observations["verify_candidate_frameworks"]["accepted_document_ids"],
                "query_features": observations["analyse_audit_scenario"]["evidence_needs"],
            }
        elif tool == "assess_ifrs_comparability":
            arguments = {
                "discovered_candidates": observations["discover_ifrs_candidates"]["candidates"],
                "framework_results": observations["verify_candidate_frameworks"]["framework_results"],
                "searches": observations["search_verified_ifrs_filings"]["searches"],
            }
        elif tool in {"verify_allied_framework_separately", "check_authority"}:
            arguments = {}
        elif tool == "stop_and_summarise":
            arguments = {"reason": "The bounded IFRS-targeted discovery workflow is complete; auditor review is required."}
        else:
            raise ExternalPolicyError("Unknown Gate 5.1 action.")
        if decision.arguments != arguments:
            self.guardrails.append(f"Controller bound {tool} arguments to compact workflow state.")
        return PlannerDecision(tool, arguments, decision.reason[:300])

    def execute(self, decision: PlannerDecision, state: dict[str, Any]) -> None:
        if decision.tool not in self.allowed_registry():
            raise ExternalPolicyError("Illegal Gate 5.1 state transition blocked.")
        signature = hashlib.sha256(
            json.dumps({"tool": decision.tool, "arguments": decision.arguments}, sort_keys=True).encode()
        ).hexdigest()
        if signature in self.seen_signatures:
            raise ExternalPolicyError("Duplicate Gate 5.1 request blocked.")
        self.seen_signatures.add(signature)
        before = self.current
        request_start = len(self.tools.sec.request_log)
        if decision.tool == "stop_and_summarise":
            result = self._handoff(state, decision.arguments["reason"])
        else:
            result = getattr(self.tools, decision.tool)(**decision.arguments)
        after = next(
            target for source, action, target in GATE51_SEQUENCE
            if source is before and action == decision.tool
        )
        self.current = after
        self.states.append(after.value)
        state["observations"][decision.tool] = result
        state["completed_tools"].append(decision.tool)
        state["workflow"]["current_state"] = after.value
        self.trace.append(
            {
                "step": len(self.trace) + 1,
                "state_before": before.value,
                "action": decision.tool,
                "reason_summary": decision.reason,
                "state_after": after.value,
                "external_requests": self.tools.sec.request_log[request_start:],
            }
        )

    @staticmethod
    def _handoff(state: dict[str, Any], reason: str) -> dict[str, Any]:
        comparisons = state["observations"]["assess_ifrs_comparability"]
        accepted = [item for item in comparisons["assessments"] if item["decision"] == "accepted"]
        return {
            "status": "ifrs_targeted_research_handoff" if accepted else "no_useful_ifrs_comparator_found_within_bounds",
            "stop_reason": reason,
            "verified_ifrs_candidate_found": comparisons["verified_ifrs_candidate_found"],
            "useful_ifrs_comparator_found": comparisons["useful_ifrs_comparator_found"],
            "accepted_candidates": [
                {"company": item["company"], "rating": item["rating"], "score": item["weighted_score"]}
                for item in accepted
            ],
            "authority_boundary": "External and Allied evidence are company disclosures; authoritative IFRS guidance remains missing.",
            "auditor_review_required": True,
            "final_audit_judgment_provided": False,
        }


def compact_gate51_planner_state(state: dict[str, Any], action: str) -> dict[str, Any]:
    observations = state["observations"]
    selected: dict[str, Any] = {}
    mapping = {
        "discover_ifrs_candidates": ["analyse_audit_scenario"],
        "locate_public_filing": ["discover_ifrs_candidates"],
        "download_framework_filings": ["locate_public_filing"],
        "verify_candidate_frameworks": ["download_framework_filings"],
        "search_verified_ifrs_filings": ["analyse_audit_scenario", "verify_candidate_frameworks"],
        "assess_ifrs_comparability": ["discover_ifrs_candidates", "verify_candidate_frameworks", "search_verified_ifrs_filings"],
        "verify_allied_framework_separately": ["assess_ifrs_comparability"],
        "check_authority": ["assess_ifrs_comparability", "verify_allied_framework_separately"],
        "stop_and_summarise": ["assess_ifrs_comparability", "verify_allied_framework_separately", "check_authority"],
    }
    for name in mapping.get(action, []):
        value = observations.get(name)
        if value is None:
            continue
        if name == "discover_ifrs_candidates":
            selected[name] = {"candidates": value["candidates"]}
        elif name == "locate_public_filing":
            selected[name] = {"filings": value["filings"]}
        elif name == "download_framework_filings":
            selected[name] = {"downloads": value["downloads"]}
        elif name == "verify_candidate_frameworks":
            selected[name] = {
                "framework_results": value["framework_results"],
                "accepted_document_ids": value["accepted_document_ids"],
            }
        elif name == "search_verified_ifrs_filings":
            selected[name] = {"searches": value["searches"]}
        elif name == "assess_ifrs_comparability":
            selected[name] = {
                "assessments": [
                    {
                        key: item.get(key)
                        for key in (
                            "company", "cik", "framework_status", "decision",
                            "rating", "weighted_score", "rejection_reason",
                        )
                    }
                    for item in value["assessments"]
                ],
                "verified_ifrs_candidate_found": value["verified_ifrs_candidate_found"],
                "useful_ifrs_comparator_found": value["useful_ifrs_comparator_found"],
            }
        elif name == "verify_allied_framework_separately":
            selected[name] = {
                key: value.get(key)
                for key in ("company", "status", "verified", "evidence_type", "verified_basis")
            }
        else:
            selected[name] = value
    return {
        "request": dict(state["request"]),
        "completed_tools": list(state["completed_tools"]),
        "observations": selected,
        "workflow": {
            "lane": "ifrs_targeted_external_discovery",
            "current_state": state["workflow"]["current_state"],
            "required_reporting_framework": "IFRS",
            "candidate_limit": 3,
            "step_limit": state["workflow"]["step_limit"],
            "available_tools": [action],
        },
    }


def _safe_handoff(reason: str) -> dict[str, Any]:
    return {
        "status": "ifrs_targeted_discovery_stopped_safely",
        "stop_reason": reason,
        "verified_ifrs_candidate_found": False,
        "useful_ifrs_comparator_found": False,
        "accepted_candidates": [],
        "auditor_review_required": True,
        "final_audit_judgment_provided": False,
    }


def run_gate51_discovery(
    request: ResearchRequest,
    *,
    private_chunks: list[EvidenceChunk],
    local_candidates: list[Candidate],
    sec_client: SecEdgarClient,
    runtime_root: str | Path,
    jurisdiction_context_path: str | Path,
    planner: Gate5DeterministicPlanner | OpenRouterPlanner | Any | None = None,
    max_steps: int = 10,
) -> Gate51Result:
    active_planner = planner or Gate5DeterministicPlanner()
    metered = [active_planner]
    mode = active_planner.mode
    model = getattr(active_planner, "model", None)
    tools = Gate51Tools(
        sec_client=sec_client,
        runtime_root=runtime_root,
        private_chunks=private_chunks,
        local_candidates=local_candidates,
        jurisdiction_context_path=jurisdiction_context_path,
    )
    controller = Gate51Controller(tools, max_steps=max_steps)
    state: dict[str, Any] = {
        "request": {
            "scenario": request.scenario,
            "topic": request.topic,
            "industry": request.industry,
            "transaction_type": request.transaction_type,
            "required_reporting_framework": "IFRS",
        },
        "completed_tools": [],
        "observations": {},
        "workflow": {
            "current_state": Gate51State.START.value,
            "step_limit": max_steps,
        },
    }
    failures = []
    handoff: dict[str, Any] = {}
    while controller.current is not Gate51State.STOPPED and len(controller.trace) < max_steps:
        registry = controller.allowed_registry()
        if not registry:
            handoff = _safe_handoff("No legal Gate 5.1 action remained.")
            break
        action = next(iter(registry))
        planner_state = compact_gate51_planner_state(state, action)
        forbidden = [chunk.text for chunk in private_chunks] + tools.raw_external_texts()
        try:
            decision = active_planner.choose_next(
                planner_state, registry, max_steps - len(controller.trace), forbidden
            )
        except PlannerTransportError as exc:
            controller.guardrails.append(f"Model planner transport failed safely: {exc}")
            active_planner = Gate5DeterministicPlanner()
            metered.append(active_planner)
            mode = "deterministic Gate 5.1 fallback after planner transport error"
            decision = active_planner.choose_next(
                planner_state, registry, max_steps - len(controller.trace), forbidden
            )
        except (PlannerResponseError, PlannerError) as exc:
            controller.guardrails.append(f"Invalid planner response blocked: {exc}")
            handoff = _safe_handoff("The planner returned an invalid Gate 5.1 action.")
            break
        try:
            controller.execute(controller.bind(decision, state), state)
        except (ExternalDiscoveryError, KeyError, TypeError, ValueError) as exc:
            failures.append(
                {"step": len(controller.trace) + 1, "error_type": type(exc).__name__, "message": str(exc)}
            )
            controller.guardrails.append(f"Gate 5.1 stopped safely: {type(exc).__name__}")
            handoff = _safe_handoff("A bounded Gate 5.1 tool failed; no unsupported evidence was promoted.")
            break
    if not handoff:
        handoff = state["observations"].get("stop_and_summarise", {})
    if not handoff:
        controller.guardrails.append("Gate 5.1 step cap reached before a normal handoff.")
        handoff = _safe_handoff("The Gate 5.1 step cap was reached.")
    observations = state["observations"]
    return Gate51Result(
        mode=mode,
        planner_model=model,
        step_count=len(controller.trace),
        step_limit=max_steps,
        state_transition_sequence=controller.states,
        trace=controller.trace,
        external_request_log=list(sec_client.request_log),
        candidates=observations.get("discover_ifrs_candidates", {}).get("candidates", []),
        filings=observations.get("locate_public_filing", {}).get("filings", []),
        framework_results=observations.get("verify_candidate_frameworks", {}).get("framework_results", []),
        deep_searches=observations.get("search_verified_ifrs_filings", {}).get("searches", []),
        comparability=observations.get("assess_ifrs_comparability", {}).get("assessments", []),
        allied_framework=observations.get("verify_allied_framework_separately", {}),
        authority=observations.get("check_authority", {}),
        handoff=handoff,
        guardrails_triggered=controller.guardrails,
        network_failures=failures,
        planner_input_tokens=sum(int(getattr(item, "total_input_tokens", 0)) for item in metered),
        planner_output_tokens=sum(int(getattr(item, "total_output_tokens", 0)) for item in metered),
        provider_cost_usd=sum(float(getattr(item, "total_cost_usd", 0.0)) for item in metered),
    )
