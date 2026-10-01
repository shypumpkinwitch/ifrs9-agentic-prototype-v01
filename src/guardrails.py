from __future__ import annotations

import re
from typing import Iterable

from .schemas import EvidenceChunk


class GuardrailViolation(ValueError):
    """Raised when a proposed claim lacks retrieved or authoritative support."""


GENERAL_REQUIREMENT_PATTERN = re.compile(
    r"\b(?:ifrs(?:\s+9)?\s+(?:requires?|mandates?)|entities?\s+must|the\s+standard\s+requires?)\b",
    re.IGNORECASE,
)


def validate_claim_source_ids(
    sentence: str,
    source_ids: Iterable[str],
    retrieved: Iterable[EvidenceChunk],
) -> None:
    cited = set(source_ids)
    evidence = {chunk.chunk_id: chunk for chunk in retrieved}
    if not cited:
        raise GuardrailViolation("Every factual sentence needs at least one source ID.")
    invented = cited - evidence.keys()
    if invented:
        raise GuardrailViolation(f"Source IDs were not retrieved: {sorted(invented)}")
    if GENERAL_REQUIREMENT_PATTERN.search(sentence):
        authorities = {evidence[source_id].authority_class for source_id in cited}
        if "IFRS_FOUNDATION_OFFICIAL" not in authorities:
            raise GuardrailViolation(
                "A general IFRS requirement cannot be supported by company-only or project-note evidence."
            )
