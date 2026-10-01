from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit is not installed")
class StreamlitAppTests(unittest.TestCase):
    @patch.dict("os.environ", {"OPENROUTER_API_KEY": ""})
    def test_app_loads_and_runs_flagship_form(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        app.run(timeout=30)
        self.assertEqual(list(app.exception), [])
        self.assertGreaterEqual(len(app.button), 1)

        app.button[0].click().run(timeout=30)
        self.assertEqual(list(app.exception), [])
        self.assertEqual(len(app.tabs), 10)
        self.assertEqual(app.tabs[0].label, "Evidence needs")
        self.assertEqual(app.tabs[1].label, "Official IFRS authority")
        self.assertEqual(app.tabs[-1].label, "Evaluation")
        self.assertTrue(
            any("fallback workflow" in item.value.lower() for item in app.success)
        )

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": ""})
    def test_public_fixture_mode_remains_available_without_private_input(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        app.run(timeout=30)
        self.assertEqual(list(app.exception), [])
        self.assertGreaterEqual(len(app.checkbox), 1)

        app.checkbox[0].uncheck().run(timeout=30)
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any("public-fixture mode" in item.value.lower() for item in app.warning)
        )
        app.button[0].click().run(timeout=30)
        self.assertEqual(list(app.exception), [])

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": ""})
    def test_research_handoff_renders_authority_cards(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        app.run(timeout=30)
        self.assertEqual(list(app.exception), [])

        app.button[0].click().run(timeout=30)
        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.tabs[8].label, "Research handoff")

        handoff = app.tabs[8]
        self.assertEqual(len(handoff.json), 0)
        markdown_values = [str(item.value) for item in handoff.markdown]
        visible_text = "\n".join(markdown_values)
        self.assertIn("Reporting-framework verification status: pending", visible_text)
        self.assertNotIn("Logistic Properties of the Americas", visible_text)
        self.assertIn("Evidence gaps / limitations", visible_text)
        self.assertIn("Professional interpretation is not indexed", visible_text)
        self.assertIn("Allied_REIT reporting framework remains unverified", visible_text)
        self.assertIn("disclosures do not themselves establish IFRS requirements", visible_text)
        self.assertNotIn("SHINHAN", visible_text)
        self.assertNotIn("Inter & Co", visible_text)
        historical_text = "\n".join(item.value for item in app.tabs[9].markdown)
        self.assertIn("IFRS as issued by IASB — verified", historical_text)
        self.assertIn("Partial comparator", historical_text)
        self.assertIn("development-partner financing was not established", historical_text)
        self.assertIn("SHINHAN FINANCIAL GROUP CO LTD: Rejected.", historical_text)
        for internal_field in ("source_id", "authority_class", "stop_reason", "Candidate page - not yet verified"):
            self.assertNotIn(internal_field, visible_text)
        captions = "\n".join(str(item.value) for item in handoff.caption)
        self.assertIn("Current run: deterministic fallback", captions)
        self.assertIn("Recorded Gate 4.6 and Gate 5.1", captions)
        from src.private_runtime import default_private_bundle

        if (default_private_bundle(PROJECT_ROOT) / "working_corpus_v01.json").is_file():
            self.assertIn("Business comparability: Strong", visible_text)
            self.assertIn("A development-partner loan disclosure", visible_text)
            self.assertIn("Report year: 2025", visible_text)
            self.assertIn("PDF page: 150", captions)
            self.assertIn("ALLIED_REIT2025_P150_C01", captions)
        self.assertTrue(
            any("What official IFRS sources indicate" in value for value in markdown_values)
        )
        self.assertTrue(
            any(
                "Official IFRS 9 source and implementation support" in value
                for value in markdown_values
            )
        )
        self.assertTrue(
            any(
                "How comparable companies disclosed similar exposures" in value
                for value in markdown_values
            )
        )
        self.assertTrue(
            any(
                "Auditor judgement / further review required" in str(item.value)
                for item in handoff.error
            )
        )

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": ""})
    def test_public_handoff_does_not_claim_reviewed_allied_disclosures(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        app.run(timeout=30)
        app.checkbox[0].uncheck().run(timeout=30)
        app.button[0].click().run(timeout=30)
        self.assertEqual(list(app.exception), [])
        handoff = app.tabs[8]
        self.assertEqual(len(handoff.json), 0)
        self.assertTrue(any("No Allied_REIT disclosure was selected" in item.value for item in handoff.info))
        self.assertFalse(any("A development-partner loan disclosure" in item.value for item in handoff.markdown))

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": ""})
    def test_cosmetic_presentation_and_final_ui_smoke(self):
        from streamlit.testing.v1 import AppTest
        from src.private_runtime import default_private_bundle

        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
        app.run(timeout=30)
        self.assertEqual(list(app.exception), [])
        if (default_private_bundle(PROJECT_ROOT) / "working_corpus_v01.json").is_file():
            self.assertTrue(any(item.value == "Private local corpus: loaded" for item in app.sidebar.caption))
            self.assertTrue(any(item.value == "Validated 76 records and 76 unique chunk IDs." for item in app.sidebar.success))
            self.assertEqual(app.sidebar.text_input[0].proto.type, 1)  # Password/masked input.
            self.assertFalse(app.sidebar.expander[0].proto.expanded)
            self.assertTrue(any(
                item.value == (
                    "Private local corpus enabled. Annual-report text may be previewed locally but is "
                    "excluded from downloads and model payloads. Some local-source reporting-framework "
                    "verification remains pending."
                ) for item in app.warning
            ))
        app.button[0].click().run(timeout=30)
        self.assertEqual(list(app.exception), [])
        visible_text = "\n".join(
            str(item.value)
            for group in (app.markdown, app.caption, app.info, app.warning, app.error, app.success)
            for item in group
        )
        self.assertNotIn(str(PROJECT_ROOT), visible_text)
        self.assertNotIn("E:\\Documents\\Project", visible_text)
        self.assertNotIn("IFRS_AS_ISSUED_BY_IASB_VERIFIED", visible_text)
        self.assertNotIn("PENDING_INSUFFICIENT_EVIDENCE", visible_text)
        self.assertIn("Status: IFRS as issued by IASB — verified", visible_text)
        self.assertIn("Status: Pending — insufficient evidence", visible_text)
        self.assertTrue(any("Official IFRS 9 source and implementation support" in item.value for item in app.tabs[1].markdown))
        self.assertEqual(len(app.tabs[8].json), 0)
        self.assertGreater(len(app.tabs[9].metric), 0)
        cost_table = app.tabs[9].dataframe[0].value
        self.assertIn("Provider-reported API cost (USD)", cost_table.columns)
        self.assertNotIn("provider_reported_api_cost_usd", cost_table.columns)
        self.assertEqual(len(app.tabs[3].dataframe), 0)
        self.assertTrue(any("not current results" in item.label for item in app.tabs[9].expander))
        for item in app.tabs[6].expander:
            self.assertIn("Company disclosure", item.label)
            self.assertRegex(item.label, r"BM25 retrieval score \d+\.\d{3}$")
        self.assertTrue(any("deterministic fallback" in item.value for item in app.success))


if __name__ == "__main__":
    unittest.main()
