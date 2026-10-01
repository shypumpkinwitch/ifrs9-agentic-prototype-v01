from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.authority_registry import (
    AUTHORITY_LEVEL_STANDARD,
    AUTHORITY_LEVEL_SUPPORTING,
    IFRSAuthorityCard,
    PLANNER_CARD_FIELDS,
    authority_cards_for_planner,
    build_separated_research_handoff,
    identify_ifrs9_research_topics,
    load_authority_registry,
    retrieve_authority_cards,
)
from src.schemas import DataValidationError, ResearchRequest


REGISTRY_PATH = PROJECT_ROOT / "data" / "public_demo" / "ifrs_authority_registry_v01.json"


class Gate61AuthorityLayerTests(unittest.TestCase):
    def setUp(self):
        self.cards = load_authority_registry(REGISTRY_PATH)

    def test_every_card_has_official_ifrs_foundation_url(self):
        self.assertEqual(len(self.cards), 7)
        for card in self.cards:
            self.assertTrue(card.official_url.startswith("https://www.ifrs.org/"))

    def test_company_disclosure_cannot_be_promoted_to_official_authority(self):
        record = self.cards[0].to_dict()
        record["source_type"] = "COMPANY_DISCLOSURE"
        record["authority_level"] = AUTHORITY_LEVEL_STANDARD
        with self.assertRaises(DataValidationError):
            IFRSAuthorityCard.from_dict(record)

    def test_supporting_material_cannot_be_mislabeled_as_standard_text(self):
        supporting = next(
            card for card in self.cards
            if card.authority_level == AUTHORITY_LEVEL_SUPPORTING
        )
        record = supporting.to_dict()
        record["authority_level"] = AUTHORITY_LEVEL_STANDARD
        with self.assertRaisesRegex(DataValidationError, "cannot be labelled"):
            IFRSAuthorityCard.from_dict(record)

    def test_missing_paragraph_reference_remains_pending(self):
        pending = [card for card in self.cards if card.paragraph_reference == "pending"]
        self.assertGreaterEqual(len(pending), 2)
        self.assertTrue(all("paragraph_pending" in card.review_status for card in pending))
        self.assertTrue(
            all(
                "paragraph_verified" in card.review_status
                for card in self.cards
                if card.paragraph_reference != "pending"
            )
        )

    def test_user_facing_labels_are_human_readable_without_changing_enums(self):
        overview = next(card for card in self.cards if card.authority_id == "IFRS9-AUTH-OVERVIEW-001")
        educational = next(
            card for card in self.cards
            if card.source_type == "IFRS_FOUNDATION_EDUCATIONAL_MATERIAL"
        )
        ifric = next(card for card in self.cards if card.source_type == "IFRIC_AGENDA_DECISION")
        self.assertEqual(
            overview.display_title,
            "Official IFRS 9 source and implementation support",
        )
        self.assertEqual(overview.topic, "official standard overview and implementation support")
        self.assertEqual(overview.display_paragraph_reference, "Paragraph reference not assigned")
        self.assertEqual(overview.paragraph_reference, "pending")
        self.assertEqual(educational.display_source_type, "IFRS Foundation educational material")
        self.assertEqual(ifric.display_source_type, "IFRIC agenda decision / supporting material")
        self.assertEqual(ifric.source_type, "IFRIC_AGENDA_DECISION")

    def test_collateral_card_distinguishes_standard_paragraph_from_ifric_observation(self):
        card = next(card for card in self.cards if card.authority_id == "IFRS9-AUTH-COLLATERAL-007")
        self.assertEqual(card.paragraph_reference, "B5.5.55")
        self.assertEqual(card.source_type, "IFRIC_AGENDA_DECISION")
        self.assertEqual(card.authority_level, AUTHORITY_LEVEL_SUPPORTING)
        self.assertIn("IFRS 9 paragraph B5.5.55", card.non_verbatim_verified_summary)
        self.assertIn("IFRS Interpretations Committee observed", card.non_verbatim_verified_summary)
        self.assertIn("Separate-recognition requirements", card.non_verbatim_verified_summary)

    def test_raw_ifrs_source_text_never_enters_planner_payload(self):
        sentinel = "RAW_IFRS_SOURCE_TEXT_SENTINEL"
        record = self.cards[0].to_dict()
        record["raw_source_text"] = sentinel
        with self.assertRaises(DataValidationError):
            IFRSAuthorityCard.from_dict(record)
        payload = authority_cards_for_planner(self.cards)
        self.assertTrue(all(set(item) == set(PLANNER_CARD_FIELDS) for item in payload))
        self.assertNotIn(sentinel, json.dumps(payload))
        self.assertTrue(all("raw" not in key for item in payload for key in item))

    def test_flagship_retrieves_minimum_official_topic_coverage(self):
        request = ResearchRequest(
            scenario=(
                "A property company has made secured development and project loans and needs "
                "ECL, SICR, forward-looking and collateral research."
            ),
            topic="expected credit losses",
            industry="Property / REIT",
            transaction_type="secured development loans",
        )
        topics = identify_ifrs9_research_topics(request)
        selected = retrieve_authority_cards(self.cards, topics)
        selected_topics = {card.topic for card in selected}
        self.assertIn("12-month and lifetime expected credit losses", selected_topics)
        self.assertIn("significant increase in credit risk", selected_topics)
        self.assertIn("ECL measurement and forward-looking information", selected_topics)
        self.assertIn("collateral and credit enhancements in ECL measurement", selected_topics)

    def test_final_handoff_visibly_separates_authority_and_company_practice(self):
        handoff = build_separated_research_handoff(
            self.cards,
            {
                "evidence": [{"chunk_id": "COMPANY-CHUNK", "authority_class": "COMPANY_DISCLOSURE"}],
                "missing_evidence": ["IFRS_FOUNDATION_OFFICIAL", "PROFESSIONAL_COMMENTARY"],
            },
            [
                {
                    "company": "Example Issuer",
                    "comparability_rating": "partial",
                    "decision": "retain for review",
                    "rationale": "Non-verbatim company-practice summary.",
                }
            ],
        )
        self.assertIn("What official IFRS sources indicate", handoff)
        self.assertIn("How comparable companies disclosed similar exposures", handoff)
        self.assertTrue(handoff["Auditor judgement / further review required"])
        self.assertFalse(handoff["company_disclosure_promoted_to_official_authority"])
        official = handoff["What official IFRS sources indicate"]
        self.assertTrue(
            all(item["authority_level"] in {AUTHORITY_LEVEL_STANDARD, AUTHORITY_LEVEL_SUPPORTING} for item in official)
        )
        company = handoff["How comparable companies disclosed similar exposures"]
        self.assertEqual(
            company["current_company_disclosure_handoff"]["missing_evidence"],
            ["PROFESSIONAL_COMMENTARY"],
        )
        self.assertEqual(
            company["recorded_comparable_summaries"][0]["authority_level"],
            "COMPANY_DISCLOSURE",
        )

    def test_app_orders_authority_before_comparable_discovery(self):
        app_text = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertLess(
            app_text.index("authority_cards = retrieve_authority_cards"),
            app_text.index("result = run_bounded_agent"),
        )


if __name__ == "__main__":
    unittest.main()
