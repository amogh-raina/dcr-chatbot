"""Checks on the FAQ knowledge base files (no embedding model needed).

If test_embeddings_match_records fails, the JSON was rebuilt without recomputing the vectors.
Fix: python faq_search/build_faq_data.py && python faq_search/embed_faq_data.py
"""
import json
import re
import unittest
from pathlib import Path

from faq_search.embed_faq_data import collect_texts

DATA = Path(__file__).resolve().parent.parent / "faq_search" / "data"
RECORDS = json.loads((DATA / "faq_qa_records.json").read_text(encoding="utf-8"))
META_PATH = DATA / "faq_embeddings_meta.json"
TOPIC_IDS = {t["id"] for t in RECORDS["topics"]}
LEAKS = re.compile(
    r"Ask the applicant|\*\*|^\s*-?\s*If (yes|no)\b|\[FAQ:|\[reference|Follow[\s-]*up (question|determination)",
    re.IGNORECASE | re.MULTILINE)


class TestRecords(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [r["id"] for r in RECORDS["records"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_expected_record_counts(self):
        ids = [r["id"] for r in RECORDS["records"]]
        self.assertEqual(sum(i.startswith("FAQ_P") for i in ids), 12)
        self.assertEqual(sum(not i.startswith("FAQ_P") for i in ids), 43)

    def test_answers_are_clean_and_substantial(self):
        for r in RECORDS["records"]:
            with self.subTest(r["id"]):
                self.assertGreaterEqual(len(r["answer_text"].split()), 15)
                self.assertIsNone(LEAKS.search(r["answer_text"]))
                self.assertNotRegex(r["answer_text"], r"(?m)^Section \d")

    def test_topics_and_availability_are_valid(self):
        for r in RECORDS["records"]:
            with self.subTest(r["id"]):
                self.assertIn(r["topic"], TOPIC_IDS)
                self.assertIn(r["availability"], {"suggested", "typed_only"})

    def test_questions_are_distinct_within_a_record(self):
        for r in RECORDS["records"]:
            with self.subTest(r["id"]):
                texts = [r["canonical_question"], *r["question_variants"]]
                self.assertGreaterEqual(len(r["question_variants"]), 3)
                self.assertEqual(len({t.casefold() for t in texts}), len(texts))

    def test_guideline_citations_name_a_section(self):
        for r in RECORDS["records"]:
            if r["id"].startswith("FAQ_P"):
                continue
            with self.subTest(r["id"]):
                self.assertRegex(r["citation"], r"^Vejledning nr 9577(, Section \d.*| af 25/06/2025)$")

    def test_drafted_answers_are_flagged_for_review(self):
        by_id = {r["id"]: r for r in RECORDS["records"]}
        for rid in ("FAQ_25", "FAQ_42", "FAQ_43"):
            with self.subTest(rid):
                self.assertEqual(by_id[rid]["status"], "drafted_needs_review")
                self.assertTrue(by_id[rid]["gap_note"])


@unittest.skipUnless(META_PATH.exists(), "faq_embeddings_meta.json not built yet")
class TestEmbeddingsInSync(unittest.TestCase):
    def test_embeddings_match_records(self):
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        expected = [(r["id"], r["kind"], r["text"]) for r in collect_texts(RECORDS["records"], False)]
        actual = [(r["id"], r["kind"], r["text"]) for r in meta["rows"]]
        self.assertEqual(
            actual, expected,
            "Embeddings are out of date. Run: python faq_search/embed_faq_data.py")

    def test_vector_file_has_one_row_per_meta_row(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        vectors = np.load(DATA / "faq_embeddings.npy", mmap_mode="r")
        self.assertEqual(vectors.shape[0], len(meta["rows"]))


if __name__ == "__main__":
    unittest.main()
