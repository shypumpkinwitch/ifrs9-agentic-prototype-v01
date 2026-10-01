from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

from .retrieval import BM25Index, tokenize
from .schemas import Candidate, EvidenceChunk, ResearchRequest
from .scenario_routing import authority_coverage
from .authority_registry import load_authority_registry, retrieve_authority_cards


TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "analyse_audit_scenario": {
        "description": "Identify topics, business features, instrument types, and evidence needs.",
        "arguments": {"scenario": "string"},
    },
    "search_private_corpus": {
        "description": "Run local BM25 and return metadata, ranks, scores, and non-verbatim features only.",
        "arguments": {"query": "string", "top_k": "integer 1-10"},
    },
    "inspect_candidate_metadata": {
        "description": "Aggregate permitted provenance and local non-verbatim features by company.",
        "arguments": {"companies": "list of company names returned by search"},
    },
    "assess_comparability": {
        "description": "Rate candidates strong, partial, weak, or insufficient across explicit dimensions.",
        "arguments": {"companies": "list of inspected company names"},
    },
    "check_authority": {
        "description": "Identify present and missing authority classes without fabrication.",
        "arguments": {},
    },
    "request_more_evidence": {
        "description": "Record one structured unresolved evidence gap; the same gap cannot be requested twice.",
        "arguments": {
            "gap": {
                "missing_authority_types": "list of authority class strings",
                "missing_business_comparability_evidence": "boolean",
                "missing_instrument_specific_evidence": "boolean",
                "missing_reporting_framework_evidence": "boolean",
            },
            "evidence_types": "list of strings",
            "reason": "string",
        },
    },
    "stop_and_summarise": {
        "description": "Produce a structured research handoff requiring human review, never an audit conclusion.",
        "arguments": {"reason": "string"},
    },
}


FEATURE_TERMS = {
    "property_development": ("property", "development", "construction", "leasing"),
    "loan_receivable": ("loan", "loans", "receivable", "receivables"),
    "borrower_financial_condition": (
        "borrower",
        "financial condition",
        "credit quality",
        "covenant",
    ),
    "collateral": ("collateral", "secured", "security", "mortgage"),
    "construction_leasing": ("construction", "leasing", "lease-up", "lease up"),
    "significant_increase_credit_risk": (
        "significant increase in credit risk",
        "sicr",
        "stage 2",
    ),
    "ecl_methodology": (
        "expected credit loss",
        "expected credit losses",
        "ecl",
        "probability of default",
        "loss given default",
    ),
    "bank_portfolio": ("bank", "portfolio", "retail lending", "wholesale lending"),
}


def extract_local_features(text: str, company: str) -> dict[str, int]:
    """Create non-verbatim counts; source text never leaves this local function."""
    lowered = text.casefold()
    features = {
        name: sum(lowered.count(term) for term in terms)
        for name, terms in FEATURE_TERMS.items()
    }
    features["development_loan"] = int(
        bool(re.search(r"development|project|construction|joint arrangement|joint venture|partner", lowered))
        and bool(re.search(r"\bloan\b|\bloans\b|credit facility", lowered))
    )
    features["trade_receivables"] = int(bool(re.search(r"trade receivabl|accounts receivabl|customer receivabl", lowered)))
    features["lease_receivables"] = int(bool(re.search(r"lease receivabl|leasing receivabl|rent(?:al)? receivabl", lowered)))
    features["debt_investments"] = int(bool(re.search(r"debt investment|debt securit|bond investment|bonds? .*amorti[sz]ed cost", lowered)))
    features["guarantees_commitments"] = int(bool(re.search(r"financial guarantee|loan commitment|undrawn (?:loan|credit)|unfunded (?:loan|credit)", lowered)))
    if company.casefold() == "royal bank of canada":
        features["bank_portfolio"] += 1
    return features


def _chunk_metadata(chunk: EvidenceChunk, *, rank: int | None = None, score: float | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "company": chunk.company,
        "year": chunk.year,
        "pdf_page": chunk.pdf_page,
        "topic": chunk.topic,
        "source_type": chunk.source_type,
        "authority_label": chunk.authority_level,
        "authority_class": chunk.authority_class,
    }
    if rank is not None:
        metadata["rank"] = rank
    if score is not None:
        metadata["score"] = round(score, 6)
    return metadata


class LocalResearchTools:
    """Read-only tools with a private local plane and a metadata-only planner plane."""

    def __init__(self, chunks: list[EvidenceChunk], candidates: list[Candidate], request: ResearchRequest | None = None):
        self.chunks = list(chunks)
        self.candidates = list(candidates)
        self.index = BM25Index(self.chunks)
        self.last_search_chunks: list[EvidenceChunk] = []
        self.selected_chunk_ids: list[str] = []
        self.request = request
        self._prepare_scope(request or ResearchRequest(scenario=""))

    def _prepare_scope(self, request: ResearchRequest) -> None:
        self.routing = request.scenario_routing()
        registry = load_authority_registry(
            Path(__file__).resolve().parents[1] / "data/public_demo/ifrs_authority_registry_v01.json"
        )
        self.authority_cards = retrieve_authority_cards(registry, self.routing["authority_topics"])
        self.coverage = authority_coverage(self.routing, self.authority_cards)

    @property
    def registry(self) -> dict[str, dict[str, Any]]:
        return TOOL_CONTRACTS

    def execute(self, tool: str, arguments: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "analyse_audit_scenario": self.analyse_audit_scenario,
            "search_private_corpus": self.search_private_corpus,
            "inspect_candidate_metadata": self.inspect_candidate_metadata,
            "assess_comparability": lambda **kwargs: self.assess_comparability(state=state, **kwargs),
            "check_authority": lambda **kwargs: self.check_authority(state=state, **kwargs),
            "request_more_evidence": self.request_more_evidence,
            "stop_and_summarise": lambda **kwargs: self.stop_and_summarise(state=state, **kwargs),
        }
        if tool not in handlers:
            raise KeyError(f"Unknown research tool: {tool}")
        return handlers[tool](**arguments)

    def analyse_audit_scenario(self, scenario: str) -> dict[str, Any]:
        self._prepare_scope(self.request or ResearchRequest(scenario=scenario))
        route = self.routing
        property_case = route["in_scope"] and route["instrument"] == "development_loans"
        banking_case = route["in_scope"] and route["instrument"] == "banking_loans"
        evidence_needs = list(route["authority_topics"]) + self.coverage["instrument_specific_authority_gaps"]
        if property_case:
            evidence_needs += ["development-loan terms and purpose", "borrower or counterparty financial condition", "collateral and security", "construction and leasing status"]
        if route["instrument"] == "trade_receivables":
            evidence_needs += ["historical loss experience / provision matrix", "forward-looking adjustments", "customer concentration and delinquency"]
        if not route["in_scope"]:
            evidence_needs = [route["scope_message"]]
        return {
            "accounting_topics": ["expected credit losses"] if route["in_scope"] else [],
            "scenario_routing": route,
            "authority_coverage": self.coverage,
            "business_features": {
                "property_development_lending": property_case,
                "banking_portfolio": banking_case,
                "unfamiliar_transaction_research": True,
            },
            "financial_instrument_types": [route["instrument"]] if route["in_scope"] else [],
            "evidence_needs": evidence_needs,
            "required_framework": "IASB_IFRS",
            "final_judgment_reserved_for_human": True,
        }

    def search_private_corpus(self, query: str, top_k: int = 10) -> dict[str, Any]:
        if top_k < 1 or top_k > 10:
            raise ValueError("top_k must be between 1 and 10.")
        hits = self.index.search(query, top_k=top_k)
        self.last_search_chunks = [hit.chunk for hit in hits]
        results = []
        for rank, hit in enumerate(hits, start=1):
            item = _chunk_metadata(hit.chunk, rank=rank, score=hit.score)
            item["local_feature_flags"] = sorted(
                key
                for key, value in extract_local_features(hit.chunk.text, hit.chunk.company).items()
                if value > 0
            )
            results.append(item)
        return {
            "query_terms": tokenize(query),
            "result_count": len(results),
            "results": results,
            "raw_text_returned_to_planner": False,
        }

    def _candidate_registry_record(self, company: str) -> Candidate | None:
        company_key = company.strip().casefold()
        for candidate in self.candidates:
            names = [candidate.company_name, *candidate.corpus_company_names]
            if company_key in {name.strip().casefold() for name in names}:
                return candidate
        return None

    def inspect_candidate_metadata(self, companies: list[str]) -> dict[str, Any]:
        if not companies or len(companies) > 5:
            raise ValueError("Inspect between 1 and 5 candidate companies.")
        allowed = {chunk.company for chunk in self.last_search_chunks}
        if not set(companies).issubset(allowed):
            raise ValueError("Candidates must come from the preceding local search results.")
        profiles = []
        for company in companies:
            company_chunks = [chunk for chunk in self.chunks if chunk.company == company]
            feature_counts: Counter[str] = Counter()
            for chunk in company_chunks:
                feature_counts.update(extract_local_features(chunk.text, chunk.company))
            registry_record = self._candidate_registry_record(company)
            profiles.append(
                {
                    "company": company,
                    "industry": registry_record.industry if registry_record else "not supplied",
                    "framework_status": registry_record.framework_status if registry_record else "pending",
                    "evidence_status": "indexed_and_inspected",
                    "years": sorted({chunk.year for chunk in company_chunks if chunk.year is not None}),
                    "pdf_pages": sorted({chunk.pdf_page for chunk in company_chunks if chunk.pdf_page is not None}),
                    "authority_labels": sorted({chunk.authority_level for chunk in company_chunks}),
                    "authority_classes": sorted({chunk.authority_class for chunk in company_chunks}),
                    "topics": sorted({chunk.topic for chunk in company_chunks}),
                    "retrieved_chunk_ids": [
                        chunk.chunk_id for chunk in self.last_search_chunks if chunk.company == company
                    ],
                    "local_feature_counts": dict(sorted(feature_counts.items())),
                    "source_body_shared_with_planner": False,
                }
            )
        return {"profiles": profiles}

    @staticmethod
    def _dimension(value: float, reason: str) -> dict[str, Any]:
        return {"score": value, "reason": reason}

    def assess_comparability(self, companies: list[str], *, state: dict[str, Any]) -> dict[str, Any]:
        profiles = state.get("observations", {}).get("inspect_candidate_metadata", {}).get("profiles", [])
        profile_map = {profile["company"]: profile for profile in profiles}
        if not companies or not set(companies).issubset(profile_map):
            raise ValueError("Comparability candidates must first be inspected.")
        analysis = state.get("observations", {}).get("analyse_audit_scenario", {})
        property_case = bool(analysis.get("business_features", {}).get("property_development_lending"))
        banking_case = bool(analysis.get("business_features", {}).get("banking_portfolio"))
        route = analysis.get("scenario_routing", self.routing)
        query = state["request"]["scenario"]
        assessments = []
        for company in companies:
            profile = profile_map[company]
            features = profile["local_feature_counts"]
            industry = str(profile["industry"]).casefold()
            is_property = "property" in industry or "reit" in industry or company.casefold() == "allied_reit"
            is_bank = "bank" in industry or company.casefold() == "royal bank of canada"
            if property_case:
                business_match = is_property and route["business_category"] == "property"
                business = self._dimension(1.0 if business_match else 0.0, "Property-development business features present." if business_match else "Business comparability is not established for the development-loan scenario.")
            elif banking_case:
                business = self._dimension(1.0 if is_bank else 0.0, "Banking portfolio context present." if is_bank else "Business model differs from the banking scenario.")
            else:
                business_terms = {
                    "manufacturing": ("manufactur", "industrial producer"),
                    "ecommerce": ("e-commerce", "e commerce", "online retail", "marketplace"),
                    "property": ("property", "reit", "real estate"),
                    "banking": ("bank",),
                    "treasury": ("treasury",),
                }.get(route["business_category"], ())
                matched_business = bool(business_terms) and any(term in industry for term in business_terms)
                business = self._dimension(1.0 if matched_business else 0.0, "Business characteristics match supplied issuer metadata." if matched_business else "Business comparability has not been established from available metadata.")
            development_loan = features.get("development_loan", 0) > 0
            generic_loan = features.get("loan_receivable", 0) > 0
            if property_case:
                instrument_value = 1.0 if development_loan else (0.5 if generic_loan else 0.0)
                instrument_key = "development_loan"
            elif banking_case:
                instrument_value = 1.0 if generic_loan else 0.0
                instrument_key = "loan_receivable"
            else:
                instrument_key = route["instrument"]
                instrument_value = 1.0 if features.get(instrument_key, 0) else 0.0
            instrument_chunks = [
                chunk for chunk in self.chunks if chunk.company == company
                and extract_local_features(chunk.text, company).get(instrument_key, 0)
            ]
            exposure_supported = bool(instrument_chunks) and instrument_value == 1.0
            dimensions = {
                "business_model": business,
                "instrument_type": self._dimension(instrument_value, f"Explicit {route['instrument'].replace('_', ' ')} evidence identified locally." if exposure_supported else "Scenario-specific instrument evidence has not been established; generic ECL or receivable terminology is insufficient."),
                "borrower_or_counterparty": self._dimension(1.0 if features.get("borrower_financial_condition", 0) else 0.0, "Borrower or counterparty condition features present." if features.get("borrower_financial_condition", 0) else "Borrower-condition evidence not identified."),
                "collateral": self._dimension(1.0 if features.get("collateral", 0) else 0.0, "Collateral or security features present." if features.get("collateral", 0) else "Collateral evidence not identified."),
                "construction_and_leasing": self._dimension(1.0 if features.get("construction_leasing", 0) else 0.0, "Construction or leasing status features present." if features.get("construction_leasing", 0) else "Construction or leasing evidence not identified."),
                "ecl_treatment": self._dimension(1.0 if features.get("ecl_methodology", 0) else 0.0, "ECL methodology features present." if features.get("ecl_methodology", 0) else "ECL methodology evidence not identified."),
                "reporting_framework_status": self._dimension(
                    1.0
                    if profile["framework_status"] == "confirmed"
                    else (0.5 if profile["framework_status"] == "pending" else 0.0),
                    (
                        "IASB IFRS reporting framework confirmed from candidate metadata."
                        if profile["framework_status"] == "confirmed"
                        else (
                            "Reporting-framework verification remains pending."
                            if profile["framework_status"] == "pending"
                            else "Candidate reporting framework is excluded."
                        )
                    ),
                ),
            }
            weights = {
                "business_model": 0.22,
                "instrument_type": 0.22,
                "borrower_or_counterparty": 0.14,
                "collateral": 0.14,
                "construction_and_leasing": 0.08,
                "ecl_treatment": 0.12,
                "reporting_framework_status": 0.08,
            }
            score = sum(dimensions[name]["score"] * weight for name, weight in weights.items())
            if property_case and business["score"] == 0:
                rating = "partial" if is_bank and features.get("ecl_methodology", 0) else ("weak" if score > 0 else "insufficient")
            elif banking_case and business["score"] == 0:
                rating = "weak" if score > 0 else "insufficient"
            elif score >= 0.70 and business["score"] >= 0.75 and instrument_value >= 0.5:
                rating = "strong"
            elif score >= 0.35:
                rating = "partial"
            elif score > 0:
                rating = "weak"
            else:
                rating = "insufficient"
            suitable = (
                route["in_scope"] and business["score"] == 1.0
                and exposure_supported and features.get("ecl_methodology", 0) > 0
            )
            if not suitable:
                # Retain the historic banking-policy partial rating in a property
                # scenario as context, but never select it as a suitable comparator.
                rating = "partial" if property_case and is_bank and features.get("ecl_methodology", 0) else ("weak" if score else "insufficient")
            elif route["instrument"] not in {"development_loans", "banking_loans"}:
                # Instrument-specific applicability is not established by the
                # curated general cards; matching company practice is partial only.
                rating = "partial"
            company_chunks = [chunk for chunk in self.chunks if chunk.company == company]
            evidence_hits = BM25Index(company_chunks).search(query, top_k=min(5, len(company_chunks)))
            evidence = [
                _chunk_metadata(hit.chunk, rank=index, score=hit.score)
                for index, hit in enumerate(evidence_hits, start=1)
            ]
            assessments.append(
                {
                    "company": company,
                    "suitable_for_scenario": suitable,
                    "instrument_evidence_chunk_ids": [chunk.chunk_id for chunk in instrument_chunks],
                    "rating": rating,
                    "weighted_score": round(score, 3),
                    "dimensions": dimensions,
                    "evidence": evidence,
                    "caution": "Shared IFRS 9 or ECL terminology alone does not establish economic comparability.",
                    "comparability_explanation": (
                        "Materially useful because the property-development business model, development-loan exposure, borrower condition, collateral, construction/leasing, and ECL features align."
                        if property_case and is_property and rating == "strong"
                        else (
                            "Relevant to a banking ECL portfolio because the banking business model, loan exposure, borrower risk, collateral, and ECL methodology align."
                            if banking_case and is_bank and rating == "strong"
                            else "Use only with the stated dimensional limitations; shared ECL terminology alone is insufficient."
                        )
                    ),
                }
            )
        rating_order = {"strong": 0, "partial": 1, "weak": 2, "insufficient": 3}
        assessments.sort(key=lambda item: (rating_order[item["rating"]], -item["weighted_score"], item["company"]))
        return {"assessments": assessments}

    def check_authority(self, *, state: dict[str, Any]) -> dict[str, Any]:
        search = state.get("observations", {}).get("search_private_corpus", {})
        present = sorted({item["authority_class"] for item in search.get("results", [])})
        missing = [
            authority
            for authority in ("IFRS_FOUNDATION_OFFICIAL", "PROFESSIONAL_COMMENTARY")
            if authority not in present
        ]
        return {
            "present_authority_classes": present,
            "authority_class_scope": "company_disclosure_corpus_only",
            "missing_authority_classes": missing,
            "company_disclosure_can_establish_general_ifrs_requirements": False,
            "official_guidance_text_indexed": False,
            "registered_official_authority_ids": self.coverage["available_authority_ids"],
            "instrument_specific_authority_gaps": self.coverage["instrument_specific_authority_gaps"],
            "required_message": "The company corpus is disclosure evidence only. Curated official cards are separate; full Standard text and professional interpretation are not indexed.",
        }

    def request_more_evidence(
        self, gap: dict[str, Any], evidence_types: list[str], reason: str
    ) -> dict[str, Any]:
        required_gap_fields = {
            "missing_authority_types",
            "missing_business_comparability_evidence",
            "missing_instrument_specific_evidence",
            "missing_reporting_framework_evidence",
        }
        if not isinstance(gap, dict) or set(gap) != required_gap_fields:
            raise ValueError("Evidence gap must contain the four required structured fields.")
        if not isinstance(gap["missing_authority_types"], list) or not all(
            isinstance(item, str) for item in gap["missing_authority_types"]
        ):
            raise ValueError("Missing authority types must be a list of strings.")
        if not all(
            isinstance(gap[field], bool)
            for field in required_gap_fields - {"missing_authority_types"}
        ):
            raise ValueError("Structured evidence-gap flags must be booleans.")
        if not evidence_types:
            raise ValueError("At least one additional evidence type is required.")
        return {
            "gap": gap,
            "evidence_types": evidence_types[:5],
            "reason": reason[:300],
            "status": "human research required",
        }

    def stop_and_summarise(self, reason: str, *, state: dict[str, Any]) -> dict[str, Any]:
        assessments = state.get("observations", {}).get("assess_comparability", {}).get("assessments", [])
        authority = state.get("observations", {}).get("check_authority", {})
        requests = state.get("observations", {}).get("request_more_evidence")
        strong = [item for item in assessments if item["rating"] == "strong" and item.get("suitable_for_scenario", True)]
        partial = [item for item in assessments if item["rating"] == "partial" and item.get("suitable_for_scenario", True)]
        emergency_stop = bool(state.get("workflow", {}).get("emergency_stop"))
        selected = [] if emergency_stop or not self.routing["in_scope"] else (strong or partial[:1])
        evidence = []
        for assessment in selected:
            evidence.extend(assessment["evidence"])
        seen: set[str] = set()
        evidence = [item for item in evidence if not (item["chunk_id"] in seen or seen.add(item["chunk_id"]))]
        self.selected_chunk_ids = [item["chunk_id"] for item in evidence]
        status = "sufficient_for_research_handoff" if selected else "insufficient_evidence"
        missing_evidence = []
        if authority.get("missing_authority_classes"):
            missing_evidence.extend(authority["missing_authority_classes"])
        elif not authority:
            missing_evidence.extend(
                ["IFRS_FOUNDATION_OFFICIAL", "PROFESSIONAL_COMMENTARY"]
            )
        if requests:
            missing_evidence.extend(requests["evidence_types"])
        if not selected:
            missing_evidence.append("more transaction-specific comparable company evidence")
        missing_evidence.extend(self.coverage["instrument_specific_authority_gaps"])
        if self.routing["scope_status"] == "out_of_scope":
            missing_evidence = ["different accounting-standard research scope"]
        return {
            "scenario_routing": self.routing,
            "authority_coverage": self.coverage,
            "abstention": self.coverage["abstention"],
            "comparator_status": "supported local comparator for auditor review" if selected else "no verified suitable comparator within available evidence",
            "status": status,
            "stop_reason": reason[:300],
            "selected_candidates": [
                {"company": item["company"], "rating": item["rating"], "score": item["weighted_score"]}
                for item in selected
            ],
            "evidence": evidence,
            "authority_boundary": (
                "Retrieved evidence is company disclosure, not authoritative IFRS guidance."
                if evidence
                else "No scenario-supported company disclosure was selected; review the separate structured authority coverage."
            ),
            "missing_evidence": sorted(set(missing_evidence)),
            "research_handoff": (
                "Use the identified company-disclosure evidence as a research starting point. "
                "Obtain missing authoritative material and complete independent human review."
                if evidence
                else self.routing["scope_message"] if not self.routing["in_scope"]
                else "No verified suitable comparator within available evidence. Obtain the requested evidence and complete independent human review."
            ),
            "human_review_required": True,
            "final_audit_judgment_provided": False,
        }

    def local_selected_evidence(self) -> list[dict[str, Any]]:
        by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        return [
            by_id[chunk_id].to_dict(include_text=True)
            for chunk_id in self.selected_chunk_ids
            if chunk_id in by_id
        ]
