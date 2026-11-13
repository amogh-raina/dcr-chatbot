"""Tests for FAQ semantic retriever and Lean DCR XML graph validation."""
import os
import unittest
from pathlib import Path

from faq_search.retriever import get_retriever


@unittest.skipUnless(os.getenv("RUN_RETRIEVAL_EVAL") == "1", "set RUN_RETRIEVAL_EVAL=1 for embedding integration tests")
class TestFAQRetriever(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = get_retriever()

    def test_eu_worker_retrieval(self):
        results = self.retriever.retrieve("Can I get handicaptillæg if I am from Germany?", top_k=3)
        self.assertTrue(len(results) > 0)
        top_ids = [r.id for r in results]
        self.assertIn("FAQ_05b", top_ids)
        self.assertGreaterEqual(results[0].score, 0.75)

    def test_work_hours_retrieval(self):
        results = self.retriever.retrieve("How many hours can I work on the side per week?", top_k=3)
        self.assertTrue(len(results) > 0)
        top_ids = [r.id for r in results]
        self.assertIn("FAQ_16", top_ids)
        self.assertGreaterEqual(results[0].score, 0.70)

    def test_medical_docs_retrieval(self):
        results = self.retriever.retrieve("What medical documentation is required?", top_k=3)
        self.assertTrue(len(results) > 0)
        top_ids = [r.id for r in results]
        self.assertTrue(any(fid in ("FAQ_21", "FAQ_23") for fid in top_ids))
        self.assertGreaterEqual(results[0].score, 0.80)

    def test_appeals_retrieval(self):
        results = self.retriever.retrieve("How do I appeal a decision?", top_k=3)
        self.assertTrue(len(results) > 0)
        top_ids = [r.id for r in results]
        self.assertTrue(any(fid in ("FAQ_41", "FAQ_42") for fid in top_ids))

    def test_rank_candidates_interface(self):
        candidates = [
            {"candidate_key": "global:5b", "question": "Can I get handicaptillæg if I'm not a Danish citizen?", "value": "5b"},
            {"candidate_key": "global:6", "question": "Which education programmes qualify for handicaptillæg?", "value": "6"},
            {"candidate_key": "global:16", "question": "How much work capacity typically counts against getting the supplement?", "value": "16"},
        ]
        decision, rows = self.retriever.rank_candidates("Can I get handicaptillæg if I am from Germany?", candidates)
        self.assertIn(decision, ("single_match", "clarify_match"))
        self.assertTrue(len(rows) > 0)
        self.assertEqual(rows[0]["candidate_key"], "global:5b")

    def test_lean_xml_graph_invariants(self):
        lean_path = Path("xml graphs/SU_handicaptillaeg_FAQ_Application_Lean.xml")
        self.assertTrue(lean_path.exists())
        import importlib.util
        spec = importlib.util.spec_from_file_location("validate_dcr_xml", ".agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        errors, warnings = mod.validate(lean_path)
        self.assertEqual(len(errors), 0, f"Lean XML graph had errors: {errors}")


if __name__ == "__main__":
    unittest.main()
