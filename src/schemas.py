from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


AUTHORITY_LEVELS = {
    "IFRS_FOUNDATION_OFFICIAL",
    "PROFESSIONAL_COMMENTARY",
    "COMPANY_DISCLOSURE",
    "PROJECT_EDUCATIONAL_NOTE",
}
FRAMEWORK_STATUSES = {"confirmed", "pending", "excluded"}
EVIDENCE_STATUSES = {"candidate_only", "indexed_and_inspected"}
REQUIRED_CORPUS_FIELDS = {
    "chunk_id",
    "source_type",
    "authority_level",
    "company",
    "year",
    "pdf_page",
    "topic",
    "text",
}


class DataValidationError(ValueError):
    """Raised when a local registry or corpus record is invalid."""


def canonical_authority(value: str) -> str:
    """Map a supplied display label to a policy class without altering source data."""
    normalized = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    if normalized not in AUTHORITY_LEVELS:
        raise DataValidationError(f"Unknown authority level: {value}")
    return normalized


def _require_keys(record: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - record.keys())
    if missing:
        raise DataValidationError(f"{label} is missing fields: {', '.join(missing)}")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    company_name: str
    industry: str
    business_relevance: str
    issuer_report_year: int | None
    report_title: str | None
    framework_status: str
    framework_evidence_url: str | None
    framework_evidence_page: str | int | None
    source_url: str | None
    evidence_status: str
    tags: list[str]
    corpus_company_names: list[str] = field(default_factory=list)
    fixture_notice: str | None = None

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> "Candidate":
        required = {
            "candidate_id",
            "company_name",
            "industry",
            "business_relevance",
            "issuer_report_year",
            "report_title",
            "framework_status",
            "framework_evidence_url",
            "framework_evidence_page",
            "source_url",
            "evidence_status",
            "tags",
        }
        _require_keys(record, required, "candidate")
        if record["framework_status"] not in FRAMEWORK_STATUSES:
            raise DataValidationError(
                f"Unknown framework status: {record['framework_status']}"
            )
        if record["evidence_status"] not in EVIDENCE_STATUSES:
            raise DataValidationError(
                f"Unknown evidence status: {record['evidence_status']}"
            )
        if record["framework_status"] == "confirmed" and not (
            record["framework_evidence_url"] and record["framework_evidence_page"]
        ):
            raise DataValidationError(
                "A confirmed framework requires an evidence URL and page/reference."
            )
        return cls(
            **{
                key: record[key]
                for key in cls.__dataclass_fields__
                if key in record
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    source_id: str | None
    source_type: str
    authority_level: str
    company: str
    year: int | None
    pdf_page: str | int | None
    topic: str
    text: str
    source_url: str | None = None
    redistributable: bool = False

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> "EvidenceChunk":
        _require_keys(record, REQUIRED_CORPUS_FIELDS, "corpus record")
        canonical_authority(record["authority_level"])
        if not isinstance(record["text"], str) or not record["text"].strip():
            raise DataValidationError("Corpus text must be a non-empty string.")
        return cls(**{key: record.get(key) for key in cls.__dataclass_fields__})

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        output = asdict(self)
        output["authority_class"] = self.authority_class
        if not include_text:
            output.pop("text", None)
        return output

    @property
    def authority_class(self) -> str:
        return canonical_authority(self.authority_level)


@dataclass(frozen=True)
class GuidanceLink:
    guidance_id: str
    title: str
    authority_level: str
    url: str
    topic: str
    content_indexed: bool
    verification_note: str

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> "GuidanceLink":
        _require_keys(record, set(cls.__dataclass_fields__), "guidance link")
        if canonical_authority(record["authority_level"]) != "IFRS_FOUNDATION_OFFICIAL":
            raise DataValidationError("Guidance registry entry has wrong authority class.")
        return cls(**record)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceCard:
    card_id: str
    fact_summary: str
    original_source_url: str | None
    pdf_page: str | int | None
    chunk_id: str
    authored_by: str
    verified_against_original: bool
    approved_for_external_api: bool
    authority_level: str = "PROJECT_EDUCATIONAL_NOTE"

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> "EvidenceCard":
        _require_keys(record, set(cls.__dataclass_fields__) - {"authority_level"}, "evidence card")
        card = cls(**record)
        if canonical_authority(card.authority_level) != "PROJECT_EDUCATIONAL_NOTE":
            raise DataValidationError("Outbound evidence cards must be project-authored notes.")
        return card


@dataclass(frozen=True)
class ResearchRequest:
    scenario: str
    topic: str = ""
    industry: str = ""
    transaction_type: str = ""
    reporting_period: str = ""
    required_framework: str = "IASB_IFRS"

    def scenario_routing(self) -> dict[str, Any]:
        from .scenario_routing import route_scenario

        return route_scenario(self.scenario, self.topic)

    def search_text(self) -> str:
        return " ".join(
            item
            for item in (
                self.scenario,
                self.topic,
                self.industry,
                self.transaction_type,
                self.reporting_period,
            )
            if item
        )
