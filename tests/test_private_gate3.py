from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evidence_cards import ABSTENTION, load_evidence_cards  # noqa: E402
from src.private_runtime import (  # noqa: E402
    audit_private_bundle,
    default_private_bundle,
    load_private_baseline,
)
from src.research_agent import run_offline_workflow  # noqa: E402
from src.schemas import ResearchRequest  # noqa: E402
from src.source_registry import (  # noqa: E402
    hash_file,
    load_candidates,
    load_guidance_links,
    load_private_corpus_read_only,
)


BUNDLE = default_private_bundle(PROJECT_ROOT)
PUBLIC = PROJECT_ROOT / "data" / "public_demo"


@unittest.skipUnless(BUNDLE.is_dir(), "Private Gate 3 bundle is not installed")
class PrivateGate3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files_before = {
            path.name: hash_file(path)
            for path in BUNDLE.iterdir()
            if path.is_file()
        }
        cls.audit = audit_private_bundle(BUNDLE)
        cls.chunks, cls.corpus_hash = load_private_corpus_read_only(
            BUNDLE / "working_corpus_v01.json"
        )

    @classmethod
    def tearDownClass(cls):
        files_after = {
            path.name: hash_file(path)
            for path in BUNDLE.iterdir()
            if path.is_file()
        }
        if cls.files_before != files_after:
            raise AssertionError("A private or frozen artifact changed during the Gate 3 tests.")

    def run_flagship(self):
        return run_offline_workflow(
            ResearchRequest(
                scenario=(
                    "A property company has made secured development and project loans, and "
                    "the auditor wants relevant ECL topics and comparable public disclosure examples."
                ),
                topic="expected credit losses",
                industry="Property / REIT",
                transaction_type="Development/project loans",
                reporting_period="2025",
            ),
            candidates=load_candidates(PUBLIC / "candidate_registry_v01.json"),
            chunks=self.chunks,
            guidance_links=load_guidance_links(PUBLIC / "guidance_links_v01.json"),
            evidence_cards=load_evidence_cards(PUBLIC / "evidence_cards_v01.json"),
            private_corpus_hash=self.corpus_hash,
        )

    def test_actual_corpus_has_76_unique_records_and_exact_metadata(self):
        self.assertEqual(len(self.chunks), 76)
        self.assertEqual(len({chunk.chunk_id for chunk in self.chunks}), 76)
        self.assertEqual({chunk.source_type for chunk in self.chunks}, {"Company Annual Report"})
        self.assertEqual({chunk.authority_level for chunk in self.chunks}, {"Company disclosure"})
        self.assertEqual({chunk.authority_class for chunk in self.chunks}, {"COMPANY_DISCLOSURE"})
        self.assertEqual(sum(chunk.source_id is not None for chunk in self.chunks), 28)

    def test_raw_and_canonical_corpus_hashes_are_distinguished(self):
        self.assertEqual(
            self.audit["manifest_corpus_sha256"],
            "5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e",
        )
        self.assertEqual(
            self.audit["raw_corpus_sha256"],
            "105eefbdff84fdca8f7b0ad82f8f3756352b6c4394f73eded983cf0e578be76d",
        )
        self.assertEqual(
            self.audit["canonical_corpus_sha256"],
            "5510608d47202afe75f875eaa8fbaf28933c92d84d9aed2dab18912c8410768e",
        )
        self.assertTrue(self.audit["canonical_hash_matches_manifest"])

    def test_all_frozen_files_match_manifest(self):
        present = [item for item in self.audit["frozen_file_checks"] if item["present"]]
        self.assertEqual(len(present), 5)
        self.assertTrue(all(item["hash_matches"] for item in present))
        self.assertEqual(self.audit["mismatched_frozen_files"], [])
        self.assertEqual(self.audit["missing_manifest_files"], [])
        label_audit = next(
            item
            for item in present
            if item["name"] == "all_76_chunk_label_audit_frozen_v01.csv"
        )
        self.assertEqual(
            label_audit["actual_sha256"],
            "cbc1b2c7799a3cb368c61bfa8f045d89749047af0a5d939063eecebb8bb4ef0a",
        )

    def test_historical_metrics_are_read_from_supplied_summary(self):
        metrics = load_private_baseline(BUNDLE / "holdout_summary_v02.csv")
        self.assertEqual(metrics["bm25"]["hit_at_1_count"], "27/38")
        self.assertEqual(metrics["bm25"]["hit_at_5_count"], "37/38")
        self.assertEqual(metrics["semantic"]["hit_at_1_count"], "13/38")
        self.assertEqual(metrics["semantic"]["hit_at_5_count"], "28/38")
        self.assertIn("not recomputed", metrics["source_note"])

    def test_flagship_retrieves_allied_and_does_not_use_rbc_as_comparable(self):
        result = self.run_flagship()
        self.assertEqual(len(result.evidence), 5)
        self.assertTrue(all(item["company"] == "Allied_REIT" for item in result.evidence))
        self.assertTrue(all(item["chunk_id"].startswith("ALLIED_REIT2025_") for item in result.evidence))
        self.assertTrue(all("loan" in item["text"].lower() for item in result.evidence))
        self.assertTrue(
            any(
                "development" in item["text"].lower()
                and "receivable" in item["text"].lower()
                for item in result.evidence
            )
        )
        allied = next(item for item in result.candidates if item["company_name"] == "Allied_REIT")
        rbc = next(item for item in result.candidates if item["company_name"] == "RBC")
        self.assertEqual(allied["evidence_status"], "indexed_and_inspected")
        self.assertEqual(allied["framework_status"], "pending")
        self.assertEqual(rbc["evidence_status"], "candidate_only")
        self.assertIn("not presumed economically comparable", rbc["business_relevance"])
        self.assertEqual(result.draft_note, ABSTENTION)

    def test_safe_trace_export_contains_metadata_but_no_annual_report_text(self):
        result = self.run_flagship()
        exported = result.safe_export()
        serialized = json.dumps(exported, ensure_ascii=False)
        self.assertTrue(exported["evidence"])
        self.assertTrue(all("text" not in item for item in exported["evidence"]))
        for item in result.evidence:
            self.assertNotIn(item["text"], serialized)
        self.assertEqual(result.token_count, 0)
        self.assertEqual(result.provider_cost_usd, 0.0)

    def test_rbc_is_inspected_for_a_genuinely_banking_relevant_scenario(self):
        result = run_offline_workflow(
            ResearchRequest(
                scenario=(
                    "A bank auditor is comparing portfolio expected credit loss policy "
                    "disclosures and staging."
                ),
                topic="expected credit losses",
                industry="Banking",
                transaction_type="loan portfolio",
            ),
            candidates=load_candidates(PUBLIC / "candidate_registry_v01.json"),
            chunks=self.chunks,
            guidance_links=load_guidance_links(PUBLIC / "guidance_links_v01.json"),
            evidence_cards=load_evidence_cards(PUBLIC / "evidence_cards_v01.json"),
            private_corpus_hash=self.corpus_hash,
        )
        self.assertEqual(result.candidates[0]["company_name"], "RBC")
        self.assertEqual(result.candidates[0]["evidence_status"], "indexed_and_inspected")
        self.assertTrue(
            all(item["company"] == "Royal Bank of Canada" for item in result.evidence)
        )


if __name__ == "__main__":
    unittest.main()
