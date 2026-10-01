from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .schemas import DataValidationError, ResearchRequest


AUTHORITY_LEVEL_STANDARD = "IFRS_STANDARD_OFFICIAL_AUTHORITY"
AUTHORITY_LEVEL_SUPPORTING = "IFRS_FOUNDATION_SUPPORTING_OR_EDUCATIONAL"
AUTHORITY_LEVELS = {AUTHORITY_LEVEL_STANDARD, AUTHORITY_LEVEL_SUPPORTING}
STANDARD_SOURCE_TYPES = {
    "IFRS_STANDARD_OFFICIAL_PAGE",
    "IFRS_STANDARD_PARAGRAPH_REFERENCE",
}
SUPPORTING_SOURCE_TYPES = {
    "IFRS_FOUNDATION_EDUCATIONAL_MATERIAL",
    "IFRIC_AGENDA_DECISION",
}
ALLOWED_SOURCE_TYPES = STANDARD_SOURCE_TYPES | SUPPORTING_SOURCE_TYPES
PLANNER_CARD_FIELDS = (
    "authority_id",
    "standard",
    "topic",
    "paragraph_reference",
    "source_type",
    "non_verbatim_verified_summary",
    "official_url",
    "authority_level",
    "review_status",
)
SOURCE_TYPE_DISPLAY_LABELS = {
    "IFRS_STANDARD_OFFICIAL_PAGE": "Official IFRS 9 source page",
    "IFRS_STANDARD_PARAGRAPH_REFERENCE": "IFRS 9 paragraph reference",
    "IFRS_FOUNDATION_EDUCATIONAL_MATERIAL": "IFRS Foundation educational material",
    "IFRIC_AGENDA_DECISION": "IFRIC agenda decision / supporting material",
}
CARD_TITLE_DISPLAY_OVERRIDES = {
    "IFRS9-AUTH-OVERVIEW-001": "Official IFRS 9 source and implementation support",
}


@dataclass(frozen=True)
class IFRSAuthorityCard:
    authority_id: str
    standard: str
    topic: str
    paragraph_reference: str
    source_type: str
    non_verbatim_verified_summary: str
    official_url: str
    authority_level: str
    review_status: str

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> "IFRSAuthorityCard":
        expected = set(PLANNER_CARD_FIELDS)
        if set(record) != expected:
            missing = sorted(expected - record.keys())
            extra = sorted(record.keys() - expected)
            raise DataValidationError(
                f"Authority card fields invalid; missing={missing}, extra={extra}."
            )
        if record["source_type"] not in ALLOWED_SOURCE_TYPES:
            raise DataValidationError(f"Unsupported authority source type: {record['source_type']}")
        if record["authority_level"] not in AUTHORITY_LEVELS:
            raise DataValidationError(f"Unsupported authority level: {record['authority_level']}")
        if (
            record["source_type"] in SUPPORTING_SOURCE_TYPES
            and record["authority_level"] != AUTHORITY_LEVEL_SUPPORTING
        ):
            raise DataValidationError(
                "Supporting or educational material cannot be labelled as IFRS Standard text."
            )
        if (
            record["source_type"] in STANDARD_SOURCE_TYPES
            and record["authority_level"] != AUTHORITY_LEVEL_STANDARD
        ):
            raise DataValidationError("An IFRS Standard source must use the official-authority level.")
        parsed = urlparse(str(record["official_url"]))
        if parsed.scheme != "https" or parsed.hostname not in {"ifrs.org", "www.ifrs.org"}:
            raise DataValidationError("Every authority card must use an official IFRS Foundation URL.")
        paragraph = str(record["paragraph_reference"]).strip()
        if not paragraph:
            raise DataValidationError("Use 'pending' rather than fabricating or omitting a paragraph reference.")
        if paragraph == "pending" and "paragraph_pending" not in record["review_status"]:
            raise DataValidationError("A pending paragraph reference must remain explicitly pending in review status.")
        if paragraph != "pending" and "paragraph_verified" not in record["review_status"]:
            raise DataValidationError("A paragraph reference requires an explicit verified review status.")
        summary = str(record["non_verbatim_verified_summary"]).strip()
        if not summary or len(summary) > 700:
            raise DataValidationError("Authority summaries must be concise and non-empty.")
        return cls(**record)

    def planner_payload(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in PLANNER_CARD_FIELDS}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def display_title(self) -> str:
        return CARD_TITLE_DISPLAY_OVERRIDES.get(self.authority_id, self.topic)

    @property
    def display_source_type(self) -> str:
        return SOURCE_TYPE_DISPLAY_LABELS[self.source_type]

    @property
    def display_paragraph_reference(self) -> str:
        return (
            "Paragraph reference not assigned"
            if self.paragraph_reference == "pending"
            else self.paragraph_reference
        )


def load_authority_registry(path: str | Path) -> list[IFRSAuthorityCard]:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise DataValidationError("IFRS Authority Registry must be a JSON list.")
    cards = [IFRSAuthorityCard.from_dict(record) for record in records]
    ids = [card.authority_id for card in cards]
    if len(ids) != len(set(ids)):
        raise DataValidationError("IFRS Authority Registry contains duplicate authority IDs.")
    return cards


def identify_ifrs9_research_topics(request: ResearchRequest) -> list[str]:
    return request.scenario_routing()["authority_topics"]


def retrieve_authority_cards(
    cards: list[IFRSAuthorityCard], topics: list[str]
) -> list[IFRSAuthorityCard]:
    if not topics:
        return []
    topic_set = {topic.casefold() for topic in topics}
    selected = [
        card
        for card in cards
        if card.topic.casefold() in topic_set
        or card.source_type == "IFRS_STANDARD_OFFICIAL_PAGE"
    ]
    return selected


def authority_cards_for_planner(cards: list[IFRSAuthorityCard]) -> list[dict[str, Any]]:
    """Return only structured, non-verbatim cards; no source body is stored or accepted."""
    return [card.planner_payload() for card in cards]


def authority_index_status(cards: list[IFRSAuthorityCard]) -> dict[str, Any]:
    return {
        "status_message": (
            "Curated official IFRS 9 authority cards are indexed for the flagship ECL topics. "
            "Full IFRS Standard text is not stored or reproduced."
            if cards else "No applicable official IFRS 9 cards selected for this scenario. Full Standard text and professional interpretation are not indexed."
        ),
        "present_source_levels": [
            "IFRS Standard / official authority",
            "IFRS Foundation supporting or educational material",
            "company disclosure",
        ],
        "missing_source_levels": ["professional interpretation"],
        "standard_text_stored": False,
        "structured_authority_cards_indexed": bool(cards),
        "card_count": len(cards),
    }


def build_separated_research_handoff(
    authority_cards: list[IFRSAuthorityCard],
    company_handoff: dict[str, Any],
    recorded_comparables: list[dict[str, Any]],
    *,
    request: ResearchRequest | None = None,
) -> dict[str, Any]:
    from .scenario_routing import authority_coverage

    route = request.scenario_routing() if request else company_handoff.get("scenario_routing")
    if route:
        authority_cards = retrieve_authority_cards(authority_cards, route["authority_topics"]) if route["in_scope"] else []
    company_only_handoff = deepcopy(company_handoff)
    company_only_handoff["missing_evidence"] = [
        item
        for item in company_only_handoff.get("missing_evidence", [])
        if item != "IFRS_FOUNDATION_OFFICIAL"
    ]
    company_only_handoff["authority_boundary"] = (
        "This section contains company-disclosure evidence only; official IFRS authority "
        "cards are presented separately."
    )
    company_only_handoff["research_handoff"] = (
        "Use company-disclosure evidence as a comparable-practice starting point alongside "
        "the separately presented official authority cards. Obtain professional interpretation "
        "where needed and complete independent human review."
    )
    coverage = authority_coverage(route, authority_cards) if route else None
    if coverage:
        company_only_handoff["missing_evidence"] = sorted(set(
            company_only_handoff.get("missing_evidence", [])
            + coverage["instrument_specific_authority_gaps"]
        ))
        company_only_handoff["authority_coverage"] = coverage
        if not route["in_scope"]:
            company_only_handoff["selected_candidates"] = []
            company_only_handoff["evidence"] = []
            company_only_handoff["research_handoff"] = route["scope_message"]
        elif coverage["instrument_specific_authority_gaps"]:
            company_only_handoff["research_handoff"] += " " + coverage["abstention"]
    company_summaries = [
        {
            "company": item["company"],
            "rating": item["comparability_rating"],
            "decision": item["decision"],
            "authority_level": "COMPANY_DISCLOSURE",
            "rationale": item["rationale"],
        }
        for item in (recorded_comparables if route is None else [])
    ]
    return {
        "What official IFRS sources indicate": [card.planner_payload() for card in authority_cards],
        "How comparable companies disclosed similar exposures": {
            "current_company_disclosure_handoff": company_only_handoff,
            "recorded_comparable_summaries": company_summaries,
        },
        "Auditor judgement / further review required": True,
        "professional_interpretation_indexed": False,
        "company_disclosure_promoted_to_official_authority": False,
    }
