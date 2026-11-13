"""Tests for the help panel follow-up eval runner: labels, outcome mapping, grading, regrade. No model, no retriever."""
import json
import unittest
from pathlib import Path

from evals import eval_followups as ev

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests' / 'fixtures' / 'followup_results_2026-10-09.json'


def cases():
    return json.loads(ev.CASES.read_text(encoding='utf-8'))['queries']


def run(**result):
    return dict(result=result, error=None)


class TestLabels(unittest.TestCase):
    def test_f08_accepts_faq_41_and_faq_32(self):
        f08 = next(c for c in cases() if c['id'] == 'f08')
        self.assertEqual(f08['expect'], {'answer': ['FAQ_41', 'FAQ_32']})


class TestOutcome(unittest.TestCase):
    def test_outcome_maps_confirm_related_and_same_faq_flag(self):
        one = [{'candidate_key': 'FAQ_41'}]
        self.assertEqual(ev.outcome(run(status='faq_confirm', candidates=one)), ('confirm', ['FAQ_41']))
        self.assertEqual(ev.outcome(run(status='faq_related', candidates=one)), ('related', ['FAQ_41']))
        self.assertEqual(ev.outcome(run(status='faq_clarify', candidates=one)), ('options', ['FAQ_41']))
        self.assertEqual(ev.outcome(run(status='faq_no_match')), ('no_match', []))
        self.assertEqual(ev.outcome(run(status='faq_no_match', same_faq=True)), ('same_faq', []))
        self.assertEqual(ev.outcome(run(status='faq_confirm', candidates=one, same_faq=True)), ('same_faq', []))
        self.assertEqual(ev.outcome(run(answered=True, faq_id='FAQ_41')), ('answered', ['FAQ_41']))

    def test_same_faq_is_not_detected_from_wording(self):
        self.assertEqual(ev.outcome(run(status='faq_no_match', response='It does not say more about this.')),
                         ('no_match', []))


class TestGrade(unittest.TestCase):
    ANSWER = {'expect': {'answer': ['FAQ_41', 'FAQ_32']}}
    SAME = {'expect': {'same_or_answer': ['FAQ_37']}}
    NONE = {'expect': {'no_answer': True}}

    def test_grade_confirm_variants(self):
        self.assertEqual(ev.grade(self.ANSWER, 'confirm', ['FAQ_32']), 'confirm_right')
        self.assertEqual(ev.grade(self.ANSWER, 'confirm', ['FAQ_08']), 'confirm_wrong')
        self.assertEqual(ev.grade(self.SAME, 'confirm', ['FAQ_37']), 'confirm_right')
        self.assertEqual(ev.grade(self.SAME, 'confirm', ['FAQ_08']), 'confirm_wrong')
        self.assertEqual(ev.grade(self.NONE, 'confirm', ['FAQ_08']), 'confirm_unneeded')

    def test_answered_with_a_wrong_id_stays_wrong(self):
        self.assertEqual(ev.grade(self.ANSWER, 'answered', ['FAQ_08']), 'WRONG')
        self.assertEqual(ev.grade(self.ANSWER, 'answered', ['FAQ_32']), 'correct')
        self.assertEqual(ev.grade(self.NONE, 'answered', ['FAQ_08']), 'WRONG')

    def test_related_is_graded_like_options(self):
        self.assertEqual(ev.grade(self.ANSWER, 'related', ['FAQ_41']), 'partial')
        self.assertEqual(ev.grade(self.ANSWER, 'related', ['FAQ_08']), 'options_wrong')
        self.assertEqual(ev.grade(self.NONE, 'related', ['FAQ_08']), 'shown_options')
        self.assertEqual(ev.grade(self.NONE, 'no_match', []), 'correct')


class TestRegrade(unittest.TestCase):
    def test_regrade_reproduces_the_baseline(self):
        rows = ev.regrade(FIXTURE, cases())
        self.assertEqual(len(rows), 147)
        verdicts = {v: sum(1 for r in rows if r['verdict'] == v) for v in {r['verdict'] for r in rows}}
        self.assertEqual(verdicts['WRONG'], 30)
        self.assertEqual(verdicts['correct'], 51)
        self.assertEqual(sum(1 for r in rows if r['kind'] == 'answered' and r['verdict'] == 'correct'), 35)

    def test_regrade_report_has_the_metrics_and_needs_no_model(self):
        rows = ev.regrade(FIXTURE, cases())
        text = '\n'.join(ev.report_lines(rows, ['intro'], sweeps=False))
        self.assertIn('| WRONG (an FAQ answered that is not expected) | 30 |', text)
        self.assertIn('| answered and correct | 35 |', text)


class TestPromptFiles(unittest.TestCase):
    NEW = ['relevance/answers', 'relevance/same_topic', 'relevance/tiers']

    def test_new_prompt_files_follow_the_editing_rules(self):
        from dcrai import paths, prompts
        for name in self.NEW:
            with self.subTest(name):
                raw = (paths.PROMPTS / f'{name}.txt').read_text(encoding='utf-8')
                self.assertTrue(raw.endswith('\n') and not raw.endswith('\n\n'))
                self.assertFalse([line for line in raw.splitlines() if line != line.rstrip()])
                self.assertNotIn('\u2014', raw)      # no em-dash
                self.assertEqual(prompts.get(name), raw[:-1])


    def test_changed_prompts_contain_no_eval_message(self):
        import re
        from dcrai import prompts

        def norm(text):
            return ' '.join(re.sub(r'[^0-9a-z\u00e6\u00f8\u00e5]+', ' ', text.casefold()).split())
        messages = {norm(q['message']) for name in ('eval_followup_queries.json', 'eval_composed_queries.json')
                    for q in json.loads((ROOT / 'evals' / 'cases' / name).read_text(encoding='utf-8'))['queries']}
        messages = {m for m in messages if len(m) > 8}
        self.assertGreater(len(messages), 60)
        for name in ['rewrite/panel'] + self.NEW:
            text = norm(prompts.get(name))
            with self.subTest(name):
                self.assertEqual([m for m in messages if m in text], [])


if __name__ == '__main__':
    unittest.main()
