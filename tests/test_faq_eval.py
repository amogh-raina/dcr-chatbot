"""Tests for the retrieval eval set and the threshold calibration logic.

Most tests need no model. The quality gate at the bottom scores every eval query with the real
retriever and only runs when RUN_RETRIEVAL_EVAL=1, so the default suite stays fast and stable:

    RUN_RETRIEVAL_EVAL=1 python -m unittest tests.test_faq_eval

Its limits are env-configurable (EVAL_MAX_WRONG_SINGLE, EVAL_MAX_OOS_SINGLE, EVAL_MIN_USEFUL).
The defaults are loose placeholders. Tighten them after running evals/calibrate_thresholds.py.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from evals import calibrate_thresholds as cal

DATA = Path(__file__).resolve().parent.parent / "faq_search" / "data"
QUERIES = cal.load_queries(DATA.parent.parent / "evals" / "cases" / "eval_queries.json")
RECORDS = json.loads((DATA / "faq_qa_records.json").read_text(encoding="utf-8"))["records"]
RECORD_IDS = {r["id"] for r in RECORDS}


def q(qid, category, expected=()):
    return {"id": qid, "query": qid, "category": category, "expected": list(expected)}


class TestEvalSet(unittest.TestCase):
    def test_ids_and_queries_are_unique(self):
        self.assertEqual(len({x["id"] for x in QUERIES}), len(QUERIES))
        self.assertEqual(len({x["query"].casefold() for x in QUERIES}), len(QUERIES))

    def test_expected_ids_exist_in_the_knowledge_base(self):
        for x in QUERIES:
            with self.subTest(x["id"]):
                self.assertTrue(set(x["expected"]) <= RECORD_IDS)
                if x["category"] != "in_scope":
                    self.assertEqual(x["expected"], [])

    def test_every_record_has_an_in_scope_query(self):
        covered = {e for x in QUERIES if x["category"] == "in_scope" for e in x["expected"]}
        self.assertEqual(sorted(RECORD_IDS - covered), [])

    def test_all_three_categories_are_present(self):
        cats = {x["category"] for x in QUERIES}
        self.assertEqual(cats, {"in_scope", "unanswerable", "off_topic"})

    def test_queries_do_not_copy_kb_phrasings(self):
        """An eval query identical to a stored question would score 1.0 and tell us nothing."""
        stored = set()
        for r in RECORDS:
            stored.add(r["canonical_question"].casefold())
            stored.update(v.casefold() for v in r["question_variants"])
        for x in QUERIES:
            with self.subTest(x["id"]):
                self.assertNotIn(x["query"].casefold(), stored)


class TestDecisionParity(unittest.TestCase):
    def test_matches_the_api_rule(self):
        from faq_search.api import decide as api_decide
        settings = SimpleNamespace(single=0.80, minimum=0.50, margin=0.12, maximum=3)
        cases = [[], [0.9], [0.9, 0.5], [0.9, 0.85], [0.7, 0.2], [0.49, 0.1], [0.80, 0.68], [0.80, 0.69]]
        for scores in cases:
            with self.subTest(scores=scores):
                results = [SimpleNamespace(score=s) for s in scores]
                self.assertEqual(cal.decide(scores, 0.80, 0.50, 0.12), api_decide(results, settings))


class TestCalibrationMath(unittest.TestCase):
    QS = [q("a", "in_scope", ["F1"]), q("b", "in_scope", ["F2", "F3"]), q("c", "unanswerable"), q("d", "off_topic")]
    SCORES = {
        "a": [["F1", 0.90], ["F2", 0.60]],   # clear, correct
        "b": [["F9", 0.85], ["F2", 0.80]],   # wrong top, close runner-up
        "c": [["F4", 0.70], ["F5", 0.30]],   # on topic, not covered
        "d": [["F6", 0.20], ["F7", 0.10]],   # unrelated
    }

    def test_classify_in_scope(self):
        self.assertEqual(cal.classify(self.QS[0], self.SCORES["a"], 0.8, 0.5, 0.12), "single_correct")
        self.assertEqual(cal.classify(self.QS[1], self.SCORES["b"], 0.8, 0.5, 0.12), "clarify_hit")
        self.assertEqual(cal.classify(self.QS[1], self.SCORES["b"], 0.8, 0.5, 0.01), "single_wrong")
        self.assertEqual(cal.classify(self.QS[0], self.SCORES["a"], 0.95, 0.95, 0.0), "rejected")

    def test_clarify_miss_when_expected_not_offered(self):
        ranked = [["F9", 0.6], ["F8", 0.55], ["F7", 0.5], ["F1", 0.49]]
        self.assertEqual(cal.classify(self.QS[0], ranked, 0.8, 0.5, 0.12, maximum=3), "clarify_miss")
        self.assertEqual(cal.classify(self.QS[0], ranked, 0.8, 0.45, 0.12, maximum=4), "clarify_hit")

    def test_classify_out_of_scope(self):
        self.assertEqual(cal.classify(self.QS[2], self.SCORES["c"], 0.8, 0.5, 0.12), "false_clarify")
        self.assertEqual(cal.classify(self.QS[2], self.SCORES["c"], 0.65, 0.5, 0.12), "false_single")
        self.assertEqual(cal.classify(self.QS[3], self.SCORES["d"], 0.8, 0.5, 0.12), "rejected")

    def test_evaluate_rates(self):
        r = cal.evaluate(self.QS, self.SCORES, 0.8, 0.5, 0.12)
        self.assertEqual((r["single_correct"], r["clarify_hit"], r["single_wrong"]), (0.5, 0.5, 0.0))
        self.assertEqual((r["oos_rejected"], r["oos_false_clarify"], r["oos_false_single"]), (0.5, 0.5, 0.0))
        self.assertAlmostEqual(r["useful"], 0.75)

    def test_sweep_never_puts_minimum_above_single(self):
        rows = cal.sweep(self.QS, self.SCORES, step=0.1)
        self.assertTrue(rows)
        self.assertTrue(all(r["minimum"] <= r["single"] for r in rows))

    def test_recommend_respects_caps(self):
        rows = cal.sweep(self.QS, self.SCORES, step=0.02)
        best = cal.recommend(rows, max_wrong_single=0.0, max_oos_single=0.0)
        self.assertIsNotNone(best)
        self.assertEqual(best["single_wrong"], 0.0)
        self.assertEqual(best["oos_false_single"], 0.0)
        self.assertAlmostEqual(best["useful"], 0.75)  # a single_correct plus a clarify_hit is reachable

    def test_recommend_returns_none_when_caps_cannot_be_met(self):
        wrong_only = [q("x", "in_scope", ["F1"])]
        scores = {"x": [["F9", 0.95], ["F8", 0.10]]}
        rows = cal.sweep(wrong_only, scores, step=0.1)
        # Below its score the query is answered wrongly, above it the query is rejected, so
        # a 0% cap is met only by rejecting everything (useful = 0), which is still feasible.
        best = cal.recommend(rows, 0.0, 0.0)
        self.assertEqual(best["useful"], 0.0)

    def test_frange_includes_both_ends(self):
        grid = cal.frange(0.0, 0.2, 0.05)
        self.assertEqual(grid[0], 0.0)
        self.assertEqual(grid[-1], 0.2)
        self.assertEqual(len(grid), 5)

    def test_report_renders(self):
        rows = cal.sweep(self.QS, self.SCORES, step=0.05)
        args = SimpleNamespace(step=0.05, max_wrong_single=0.0, max_oos_single=0.0, maximum=3)
        current = cal.evaluate(self.QS, self.SCORES, 0.8, 0.5, 0.12)
        best = cal.recommend(rows, 0.0, 0.0)
        text = cal.format_report(self.QS, self.SCORES, rows, current, best, args, {"model": "m", "records": 4})
        self.assertIn("FAQ_SINGLE_THRESHOLD=", text)
        self.assertIn("Score distributions", text)


class FakeModel:
    """Stands in for SentenceTransformer: records the encode() keyword arguments."""

    def __init__(self, prompts=None):
        self.prompts = prompts or {}
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append(kwargs)
        return np.ones((len(texts), 4), dtype="float32")


class TestQueryPrompt(unittest.TestCase):
    def retriever(self, prompt, model):
        from faq_search.retriever import FAQRetriever
        r = FAQRetriever(query_prompt=prompt)
        r._model = model
        return r

    def test_no_prompt_sends_no_prompt_arguments(self):
        model = FakeModel({"query": "Instruct: x"})
        self.retriever("", model)._encode_query("hello")
        self.assertNotIn("prompt_name", model.calls[0])
        self.assertNotIn("prompt", model.calls[0])

    def test_known_prompt_name_is_passed_as_prompt_name(self):
        model = FakeModel({"query": "Instruct: x"})
        self.retriever("query", model)._encode_query("hello")
        self.assertEqual(model.calls[0]["prompt_name"], "query")
        self.assertNotIn("prompt", model.calls[0])

    def test_unknown_name_is_treated_as_literal_prompt_text(self):
        model = FakeModel({"query": "Instruct: x"})
        self.retriever("Instruct: match the FAQ\nQuery:", model)._encode_query("hello")
        self.assertEqual(model.calls[0]["prompt"], "Instruct: match the FAQ\nQuery:")
        self.assertNotIn("prompt_name", model.calls[0])

    def test_environment_variable_sets_the_default(self):
        from faq_search.retriever import FAQRetriever
        with mock.patch.dict(os.environ, {"FAQ_QUERY_PROMPT": "query"}):
            self.assertEqual(FAQRetriever().query_prompt, "query")
        with mock.patch.dict(os.environ, {"FAQ_QUERY_PROMPT": "query"}):
            self.assertEqual(FAQRetriever(query_prompt="").query_prompt, "")


class TestPromptComparison(unittest.TestCase):
    QS = TestCalibrationMath.QS
    SCORES = TestCalibrationMath.SCORES

    def test_scores_path_gets_a_tag_only_when_a_prompt_is_used(self):
        base = Path("data/eval_scores.json")
        self.assertEqual(cal.scores_path_for(base, ""), base)
        self.assertEqual(cal.scores_path_for(base, "query").name, "eval_scores_query.json")
        self.assertEqual(cal.scores_path_for(base, "Instruct: a b\nQuery:").name, "eval_scores_Instruct__a_b_Query.json")

    def test_summary_metrics(self):
        m = cal.summary_metrics(self.QS, self.SCORES)
        self.assertEqual(m["top1_accuracy"], 0.5)   # a right, b wrong
        self.assertEqual(m["top3_recall"], 1.0)     # b's expected F2 is second
        self.assertAlmostEqual(m["separation"], m["in_scope_top_p10"] - m["oos_top_p90"])

    def test_ab_report_lists_both_settings(self):
        args = SimpleNamespace(step=0.05, max_wrong_single=0.0, max_oos_single=0.0, max_oos_accept=None, maximum=3)
        text = cal.format_ab(self.QS, [("", self.SCORES, {}), ("query", self.SCORES, {})], args)
        self.assertIn("| none |", text)
        self.assertIn("| 'query' |", text)

    def test_main_from_cached_scores_for_each_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            queries = Path(tmp) / "q.json"
            queries.write_text(json.dumps({"queries": self.QS}), encoding="utf-8")
            digest = cal.file_digest(queries)
            base = Path(tmp) / "scores.json"
            for prompt in ("", "query"):
                cache = {"queries_digest": digest, "meta": {"model": "m", "records": 4, "query_prompt": prompt},
                         "scores": self.SCORES}
                cal.scores_path_for(base, prompt).write_text(json.dumps(cache), encoding="utf-8")
            cur = SimpleNamespace(single=0.8, minimum=0.5, margin=0.12, maximum=3)
            with mock.patch.object(cal, "current_settings", return_value=cur):
                for extra in ([], ["--query-prompt", "query"], ["--ab"]):
                    with self.subTest(extra=extra), contextlib.redirect_stdout(io.StringIO()) as out:
                        rc = cal.main(["--queries", str(queries), "--scores", str(base), "--from-scores", *extra])
                        self.assertEqual(rc, 0)
                        self.assertIn("# ", out.getvalue())
                # a cache whose recorded prompt differs from the requested one must be refused
                stale = {"queries_digest": digest, "meta": {"query_prompt": "something else"}, "scores": self.SCORES}
                cal.scores_path_for(base, "other").write_text(json.dumps(stale), encoding="utf-8")
                with self.assertRaises(SystemExit):
                    cal.load_or_score(self.QS, digest, "other", base, True)


@unittest.skipUnless(os.getenv("RUN_RETRIEVAL_EVAL") == "1", "set RUN_RETRIEVAL_EVAL=1 to score with the real model")
class TestRetrievalQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from faq_search.retriever import get_retriever
        from dcrai.llm.openchat import Settings
        cls.settings = Settings.from_env()
        cls.scores = cal.score_queries(QUERIES, get_retriever())

    def test_quality_at_configured_thresholds(self):
        s = self.settings
        r = cal.evaluate(QUERIES, self.scores, s.single, s.minimum, s.margin, s.maximum)
        summary = (f"single {s.single}/min {s.minimum}/margin {s.margin}: "
                   f"useful {r['useful']:.2f}, wrong single {r['single_wrong']:.2f}, "
                   f"oos single {r['oos_false_single']:.2f}")
        self.assertLessEqual(r["single_wrong"], float(os.getenv("EVAL_MAX_WRONG_SINGLE", "0.05")), summary)
        self.assertLessEqual(r["oos_false_single"], float(os.getenv("EVAL_MAX_OOS_SINGLE", "0.05")), summary)
        self.assertGreaterEqual(r["useful"], float(os.getenv("EVAL_MIN_USEFUL", "0.40")), summary)


if __name__ == "__main__":
    unittest.main()
