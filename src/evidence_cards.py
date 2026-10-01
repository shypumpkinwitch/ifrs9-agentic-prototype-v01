from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from .schemas import DataValidationError, EvidenceCard


ABSTENTION = "Insufficient approved generation context—human review needed"
SENSITIVE_PATTERN = re.compile(
    r"(?:[A-Za-z]:\\|/Users/|/home/|sk-[A-Za-z0-9_-]{12,}|api[_-]?key)",
    re.IGNORECASE,
)


class OutboundGateError(PermissionError):
    """Raised when content is not permitted to cross the API boundary."""


def load_evidence_cards(path: str | Path) -> list[EvidenceCard]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise DataValidationError("Evidence cards must contain a JSON list.")
    cards = [EvidenceCard.from_dict(record) for record in payload]
    card_ids = [card.card_id for card in cards]
    if len(card_ids) != len(set(card_ids)):
        raise DataValidationError("Duplicate evidence card IDs.")
    return cards


def build_outbound_payload(cards: list[EvidenceCard]) -> dict[str, Any]:
    if not cards:
        raise OutboundGateError("No evidence cards were supplied.")
    safe_cards = []
    for card in cards:
        if not card.verified_against_original or not card.approved_for_external_api:
            raise OutboundGateError(
                f"Card {card.card_id} is not both verified and approved for external API use."
            )
        serialized = " ".join(
            str(value)
            for value in (card.fact_summary, card.original_source_url, card.pdf_page, card.chunk_id)
        )
        if SENSITIVE_PATTERN.search(serialized):
            raise OutboundGateError(f"Card {card.card_id} contains a path or possible secret.")
        safe_cards.append(
            {
                "card_id": card.card_id,
                "fact_summary": card.fact_summary,
                "original_source_url": card.original_source_url,
                "pdf_page": card.pdf_page,
                "chunk_id": card.chunk_id,
                "authority_level": card.authority_level,
            }
        )
    return {"evidence_cards": safe_cards}


def send_approved_cards(
    cards: list[EvidenceCard], transport: Callable[[dict[str, Any]], Any]
) -> Any:
    """Call a supplied transport only after the outbound payload passes the gate."""
    return transport(build_outbound_payload(cards))


def draft_local_note(cards: list[EvidenceCard], retrieved_chunk_ids: set[str]) -> str:
    eligible = [
        card
        for card in cards
        if card.verified_against_original and card.chunk_id in retrieved_chunk_ids
    ]
    if not eligible:
        return ABSTENTION
    return "\n\n".join(
        f"{card.fact_summary} [Source: {card.chunk_id}]" for card in eligible
    )
