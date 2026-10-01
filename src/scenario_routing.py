"""Conservative scenario routing, independent of evaluation cases and issuer names."""
from __future__ import annotations

import re
from typing import Any


GENERAL_TOPICS = [
    "expected credit loss recognition scope",
    "ECL measurement and forward-looking information",
    "reasonable and supportable forward-looking information",
]
GENERAL_APPROACH_TOPICS = [
    "12-month and lifetime expected credit losses", "significant increase in credit risk",
]
INSTRUMENT_QUESTIONS = {
    "trade_receivables": "Trade-receivable simplified-approach / lifetime-ECL official authority, including historical-loss or provision-matrix applicability",
    "debt_investments": "Amortised-cost debt-investment impairment scope and instrument-specific official authority",
    "lease_receivables": "Lease-receivable lifetime-ECL accounting-policy election and its applicability: sufficient official authority",
    "guarantees_commitments": "Financial-guarantee / undrawn loan-commitment impairment scope and instrument-specific official authority",
}


def normalise(value: str) -> str:
    return re.sub(r"[\s_\-–—]+", " ", value.casefold()).strip()


def route_scenario(scenario: str, selected_topic: str = "") -> dict[str, Any]:
    content = normalise(scenario)
    topic = normalise(selected_topic)
    outside = bool(re.search(r"revenue recognition|recogn(?:ise|ize|ising|izing) revenue|income tax|inventory costing|share based payment", content))
    ecl = bool(re.search(r"\becl\b|expected credit|credit loss|impairment|credit risk|overdue|delinquen|default risk", content))
    banking = bool(re.search(r"\bbank(?:ing)?\b|credit institution|deposit taking", content))
    property_business = bool(re.search(r"property|real estate|\breit\b|development partner", content))
    instruments = []
    if re.search(r"trade receivabl|accounts receivabl|customer receivabl|merchant receivabl|trade debtor|invoices? (?:are |remain )?(?:unpaid|overdue)", content):
        instruments.append("trade_receivables")
    if re.search(r"lease receivabl|leasing receivabl|rent(?:al)? receivabl", content):
        instruments.append("lease_receivables")
    if re.search(r"debt investment|debt securit|bond investment|bonds? .*amorti[sz]ed cost|amorti[sz]ed cost.*bonds?", content):
        instruments.append("debt_investments")
    if re.search(r"financial guarantee|credit guarantee|loan commitment|undrawn (?:loan|credit)|unfunded (?:loan|credit)|guarantee.*credit loss", content):
        instruments.append("guarantees_commitments")
    if not instruments and banking and re.search(r"loan|lending|portfolio", content):
        instruments.append("banking_loans")
    if not instruments and re.search(r"development|project|construction|development partner", content) and re.search(r"loan|lend|financ", content):
        instruments.append("development_loans")
    instrument = instruments[0] if len(instruments) == 1 else "unspecified"
    topic_ecl = bool(re.search(r"expected credit|\becl\b|impairment", topic))
    if outside:
        status = "clarification_required" if ecl or instruments else "out_of_scope"
        message = (
            "Scope mismatch: this scenario concerns a different accounting-standard research scope. "
            "The current implementation supports IFRS 9 impairment research only; no revenue-recognition "
            "or other-standard requirement is provided."
        )
        if ecl or instruments:
            message += " Clarify the mixed accounting subjects before research."
    elif len(instruments) > 1:
        status, message = "clarification_required", "Multiple distinct credit exposures were identified; clarify the instrument to research before comparing disclosures."
    elif instrument != "unspecified" or ecl:
        status, message = "in_scope", "IFRS 9 impairment research scope identified from the scenario; applicability remains subject to official-source and auditor review."
    else:
        status, message = "clarification_required", "No supported IFRS 9 impairment exposure was established by the scenario. Request a clarified IFRS 9 accounting question."
    business = (
        "banking" if banking else "manufacturing" if re.search(r"manufactur|industrial producer|factory", content)
        else "ecommerce" if re.search(r"e commerce|online (?:retail|marketplace)|merchant|internet retailer", content)
        else "property" if property_business else "treasury" if re.search(r"treasury", content)
        else "unspecified"
    )
    topics = []
    if status == "in_scope":
        topics = list(GENERAL_TOPICS)
        if instrument in {"development_loans", "banking_loans", "debt_investments", "unspecified"}:
            topics += GENERAL_APPROACH_TOPICS
        if re.search(r"collateral|secured|security|mortgage", content):
            topics.append("collateral and credit enhancements in ECL measurement")
    return {
        "scope_status": status, "in_scope": status == "in_scope",
        "instrument": instrument, "business_category": business,
        "selected_topic_conflict": outside and topic_ecl,
        "scope_message": message, "authority_topics": topics,
        "instrument_authority_question": INSTRUMENT_QUESTIONS.get(instrument),
        "human_review_required": True,
    }


def authority_coverage(route: dict[str, Any], cards: list) -> dict[str, Any]:
    """Use curated topic metadata only; do not derive missing requirements or paragraphs."""
    question = route["instrument_authority_question"]
    needles = {
        "trade_receivables": ("trade receivable", "simplified approach"),
        "lease_receivables": ("lease receivable", "policy election"),
        "debt_investments": ("debt investment", "amortised cost debt"),
        "guarantees_commitments": ("financial guarantee", "loan commitment"),
    }.get(route["instrument"], ())
    specific_support = bool(needles) and any(
        any(term in normalise(card.topic) for term in needles) for card in cards
    )
    gaps = [question] if route["in_scope"] and question and not specific_support else []
    return {
        "scope_status": route["scope_status"],
        "available_authority_ids": [card.authority_id for card in cards] if route["in_scope"] else [],
        "instrument_specific_authority_gaps": gaps,
        "full_standard_text_indexed": False, "professional_interpretation_indexed": False,
        "abstention": (
            "Abstain from an instrument-specific accounting conclusion until the identified official-authority gap is resolved."
            if gaps else route["scope_message"] if not route["in_scope"]
            else "Research starting point only; no final accounting or audit conclusion."
        ),
    }
