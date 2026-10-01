from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evidence_cards import (  # noqa: E402
    OutboundGateError,
    build_outbound_payload,
    send_approved_cards,
)
from src.guardrails import GuardrailViolation, validate_claim_source_ids  # noqa: E402
from src.schemas import EvidenceCard, EvidenceChunk  # noqa: E402


def make_card(**overrides):
    values = {
        "card_id": "CARD-1",
        "fact_summary": "A project-authored, source-verified summary.",
        "original_source_url": "https://example.invalid/report",
        "pdf_page": 10,
        "chunk_id": "CHUNK-1",
        "authored_by": "Project team",
        "verified_against_original": True,
        "approved_for_external_api": True,
    }
    values.update(overrides)
    return EvidenceCard(**values)


def make_chunk(authority="COMPANY_DISCLOSURE"):
    return EvidenceChunk(
        chunk_id="CHUNK-1",
        source_id="SOURCE-1",
        source_type="annual_report",
        authority_level=authority,
        company="Example issuer",
        year=2025,
        pdf_page=10,
        topic="expected credit losses",
        text="Local-only copyrighted source text.",
    )


class OutboundAndAuthorityGuardrailTests(unittest.TestCase):
    def test_unapproved_card_never_calls_transport(self):
        calls = []
        card = make_card(approved_for_external_api=False)
        with self.assertRaises(OutboundGateError):
            send_approved_cards([card], calls.append)
        self.assertEqual(calls, [])

    def test_unverified_card_never_calls_transport(self):
        calls = []
        card = make_card(verified_against_original=False)
        with self.assertRaises(OutboundGateError):
            send_approved_cards([card], calls.append)
        self.assertEqual(calls, [])

    def test_approved_payload_contains_cards_not_raw_source_text(self):
        captured = []
        send_approved_cards([make_card()], captured.append)
        self.assertEqual(len(captured), 1)
        payload = captured[0]
        serialized = str(payload)
        self.assertIn("fact_summary", serialized)
        self.assertNotIn("Local-only copyrighted source text", serialized)
        self.assertNotIn("text'", serialized)

    def test_possible_secret_or_private_path_is_blocked(self):
        for summary in ("secret sk-ABCDEFGHIJKLMNOP", r"see C:\\private\\report.pdf"):
            with self.subTest(summary=summary):
                with self.assertRaises(OutboundGateError):
                    build_outbound_payload([make_card(fact_summary=summary)])

    def test_invented_source_id_is_rejected(self):
        with self.assertRaisesRegex(GuardrailViolation, "not retrieved"):
            validate_claim_source_ids("Issuer reported a policy.", ["MADE-UP"], [make_chunk()])

    def test_company_only_evidence_cannot_support_general_ifrs_requirement(self):
        with self.assertRaisesRegex(GuardrailViolation, "general IFRS requirement"):
            validate_claim_source_ids(
                "IFRS 9 requires this treatment.", ["CHUNK-1"], [make_chunk()]
            )

    def test_official_evidence_can_support_requirement_after_source_validation(self):
        validate_claim_source_ids(
            "IFRS 9 requires this treatment.",
            ["CHUNK-1"],
            [make_chunk(authority="IFRS_FOUNDATION_OFFICIAL")],
        )


if __name__ == "__main__":
    unittest.main()
