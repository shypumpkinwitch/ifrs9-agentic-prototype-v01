from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval import BM25Index, search_candidates  # noqa: E402
from src.schemas import DataValidationError  # noqa: E402
from src.source_registry import (  # noqa: E402
    hash_file,
    load_candidates,
    load_corpus,
    load_guidance_links,
    load_private_corpus_read_only,
)


PUBLIC = PROJECT_ROOT / "data" / "public_demo"


class RegistryAndRetrievalTests(unittest.TestCase):
    def test_public_records_validate_and_ids_are_unique(self):
        candidates = load_candidates(PUBLIC / "candidate_registry_v01.json")
        chunks = load_corpus(PUBLIC / "disclosures_v01.json")
        links = load_guidance_links(PUBLIC / "guidance_links_v01.json")

        self.assertEqual(len({item.candidate_id for item in candidates}), len(candidates))
        self.assertEqual(len({item.chunk_id for item in chunks}), len(chunks))
        self.assertEqual(len({item.guidance_id for item in links}), len(links))

    def test_duplicate_chunk_ids_are_rejected(self):
        source = json.loads((PUBLIC / "disclosures_v01.json").read_text(encoding="utf-8"))
        source.append(dict(source[0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "Duplicate chunk IDs"):
                load_corpus(path)

    def test_private_corpus_is_not_changed_by_loader(self):
        source_bytes = (PUBLIC / "disclosures_v01.json").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            path.write_bytes(source_bytes)
            before = hash_file(path)
            chunks, recorded = load_private_corpus_read_only(path, expected_count=None)
            after = hash_file(path)
        self.assertGreater(len(chunks), 0)
        self.assertEqual(before, recorded)
        self.assertEqual(before, after)

    def test_private_working_corpus_requires_76_records_by_default(self):
        source_bytes = (PUBLIC / "disclosures_v01.json").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "working_corpus_v01.json"
            path.write_bytes(source_bytes)
            with self.assertRaisesRegex(DataValidationError, "Expected 76"):
                load_private_corpus_read_only(path)

    def test_bm25_returns_local_project_note_for_flagship_terms(self):
        chunks = load_corpus(PUBLIC / "disclosures_v01.json")
        hits = BM25Index(chunks).search("property development project loans ECL", top_k=5)
        self.assertTrue(hits)
        self.assertEqual(hits[0].chunk.authority_level, "PROJECT_EDUCATIONAL_NOTE")

    def test_bm25_unsupported_scenario_returns_no_evidence(self):
        chunks = load_corpus(PUBLIC / "disclosures_v01.json")
        hits = BM25Index(chunks).search("space launch cryptographic token minting", top_k=5)
        self.assertEqual(hits, [])

    def test_pending_candidate_is_not_promoted_to_confirmed(self):
        candidates = load_candidates(PUBLIC / "candidate_registry_v01.json")
        results = search_candidates(candidates, "Allied property development loans", 5)
        self.assertTrue(results)
        self.assertEqual(results[0].framework_status, "pending")
        self.assertNotEqual(results[0].framework_status, "confirmed")


if __name__ == "__main__":
    unittest.main()
