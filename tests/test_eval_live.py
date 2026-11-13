import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evals import eval_live as ev


def line(outcome, ids=(), row=None, inputs=None, **extra):
    d = {'kind': 'faq_outcome', 'outcome': outcome, 'faq_ids': list(ids)}
    if row is not None:
        d['outcome_row'] = row
    if inputs is not None:
        d['outcome_inputs'] = inputs
    d.update(extra)
    return d


class GradeTests(unittest.TestCase):
    def test_no_answer_cases(self):
        n = {'no_answer': True}
        self.assertEqual(ev.grade(n, line('answer', ['FAQ_1'])), 'WRONG')
        self.assertEqual(ev.grade(n, line('confirm', ['FAQ_1'])), 'confirm_unneeded')
        self.assertEqual(ev.grade(n, line('offer', ['FAQ_1'])), 'shown_options')
        self.assertEqual(ev.grade(n, line('not_covered')), 'correct')
        self.assertEqual(ev.grade(n, line('out_of_scope')), 'correct')
        self.assertEqual(ev.grade(n, line('answer', ['FAQ_1'], same_faq=True)), 'correct')
        self.assertEqual(ev.grade(n, None), 'missed')

    def test_answer_cases(self):
        a = {'answer': ['FAQ_1', 'FAQ_2']}
        self.assertEqual(ev.grade(a, line('answer', ['FAQ_2'])), 'correct')
        self.assertEqual(ev.grade(a, line('answer', ['FAQ_9'])), 'WRONG')
        self.assertEqual(ev.grade(a, line('confirm', ['FAQ_1'])), 'confirm_right')
        self.assertEqual(ev.grade(a, line('confirm', ['FAQ_9'])), 'confirm_wrong')
        self.assertEqual(ev.grade(a, line('offer', ['FAQ_9', 'FAQ_1'])), 'partial')
        self.assertEqual(ev.grade(a, line('clarify', ['FAQ_9'])), 'options_miss')
        self.assertEqual(ev.grade(a, line('not_covered')), 'missed')
        self.assertEqual(ev.grade({'same_or_answer': ['FAQ_1']}, line('answer', ['FAQ_1'], same_faq=True)), 'correct')


class InvariantTests(unittest.TestCase):
    ok = {'scope': 'in_scope', 'search': 'list', 'relevance': 'one_answers', 'clarified': 0, 'misses': 0}

    def test_clean_line(self):
        self.assertEqual(ev.check_line(line('confirm', ['F'], 6, self.ok, outcome_source='code'), 'code'), [])

    def test_row_must_equal_the_table(self):
        out = ev.check_line(line('confirm', ['F'], 4, self.ok, outcome_source='code'), 'code')
        self.assertTrue(any('table gives 6' in v for v in out))

    def test_shadow_needs_a_dmn_result_and_no_mismatch(self):
        base = line('confirm', ['F'], 6, self.ok, outcome_source='code')
        self.assertTrue(any('no DMN result' in v for v in ev.check_line(base, 'shadow')))
        good = dict(base, outcome_dcr='confirm', outcome_row_dcr=6)
        self.assertEqual(ev.check_line(good, 'shadow'), [])
        bad = dict(good, outcome_mismatch=True)
        self.assertTrue(any('disagree' in v for v in ev.check_line(bad, 'shadow')))

    def test_dcr_needs_source_dcr(self):
        l = line('confirm', ['F'], 6, self.ok, outcome_source='code', outcome_dcr='confirm')
        self.assertTrue(any('outcome_source' in v for v in ev.check_line(l, 'dcr')))
        self.assertEqual(ev.check_line(dict(l, outcome_source='dcr'), 'dcr'), [])

    def test_code_mode_has_no_dmn_result(self):
        l = line('confirm', ['F'], 6, self.ok, outcome_source='code', outcome_dcr='confirm')
        self.assertTrue(any('mode code' in v for v in ev.check_line(l, 'code')))

    def test_failclosed_is_flagged(self):
        self.assertTrue(any('failed closed' in v for v in ev.check_line(line('not_covered', [], 9, None, outcome_source='failclosed'), 'code')))


class FakeHttp:
    """requests.Session stand-in: init creates a log file, ask appends the lines the app would write."""
    def __init__(self, logdir, script):
        self.logdir, self.script, self.headers, self.n = Path(logdir), script, {}, 0

    def post(self, url, json=None, timeout=None):
        route = url.rsplit('/application/', 1)[1]
        resp = mock.Mock()
        resp.status_code = 200
        if route == 'init':
            self.path = self.logdir / ('%s.jsonl' % self.headers['X-Session-ID'])
            self.path.write_text('{"kind":"start"}\n')
            resp.json.return_value = {'application': True}
        else:
            data, lines = self.script(json['message'])
            with open(self.path, 'a') as fh:
                for l in lines:
                    fh.write(__import__('json').dumps(l) + '\n')
            resp.json.return_value = data
        return resp


class PanelTests(unittest.TestCase):
    def setUp(self):
        ev.ALL_VIOLATIONS.clear()

    def run_cases(self, script, **kw):
        with tempfile.TemporaryDirectory() as d:
            fake = lambda: FakeHttp(d, script)
            with mock.patch.object(ev.paths, 'INTERACTION_LOGS', Path(d)), \
                    mock.patch('requests.Session', side_effect=fake), mock.patch.object(ev.time, 'sleep'):
                return ev.replay_cases('http://x', '1', 1, 'code', progress=lambda *_: None, **kw)

    def test_a_confirmed_lone_survivor_is_not_wrong(self):
        inputs = {'scope': 'in_scope', 'search': 'list', 'relevance': 'one_answers', 'clarified': 0, 'misses': 0}
        script = lambda m: ({'status': 'faq_confirm'}, [line('confirm', ['FAQ_21'], 6, inputs, outcome_source='code')])
        out = self.run_cases(script, only={'n01'})
        self.assertEqual(out[0]['verdict'], 'confirm_unneeded')

    def test_an_answer_to_a_no_answer_case_is_wrong(self):
        script = lambda m: ({'status': 'question'}, [line('answer', ['FAQ_17'])])
        out = self.run_cases(script, only={'n01'})
        self.assertEqual(out[0]['verdict'], 'WRONG')

    def test_report_and_gate(self):
        script = lambda m: ({'status': 'faq_no_match'}, [line('not_covered', [], 9, None, outcome_source='code')])
        out = self.run_cases(script, only={'n01', 'o01'})
        args = mock.Mock(graph='1', base='http://x', expect_mode='code')
        text, passed = ev.panel_report(args, out, [])
        self.assertTrue(passed)
        self.assertIn('WRONG answers | 0', text)
        text, passed = ev.panel_report(args, out, [dict(name='x', status='FAIL', detail='')])
        self.assertFalse(passed)


if __name__ == '__main__':
    unittest.main()


class ScenarioTests(PanelTests):
    def test_mechanics_run_against_a_fake_app(self):
        seen = {}

        def script(message):
            n = seen.setdefault(message, 0)
            seen[message] = n + 1
            if 'caseworker' in message or 'somebody' in message or 'real person' in message or 'call someone' in message:
                return {'status': 'handover', 'handover': 'x'}, [line('handover', [], None)]
            if 'weather' in message or 'housing' in message or 'condition' in message:
                return {'status': 'faq_out_of_scope'}, [line('out_of_scope', [], 1, {'scope': 'out_of_scope', 'search': 'none', 'relevance': 'none', 'clarified': 0, 'misses': 0})]
            return {'status': 'faq_no_match'}, [{'kind': 'faq_ask'}, line('not_covered', [], 3, {'scope': 'in_scope', 'search': 'none', 'relevance': 'none', 'clarified': 0, 'misses': 0})]

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ev.paths, 'INTERACTION_LOGS', Path(d)), \
                    mock.patch('requests.Session', side_effect=lambda: FakeHttp(d, script)), mock.patch.object(ev.time, 'sleep'):
                out = ev.scenarios('http://x', '1', 'code', progress=lambda *_: None)
        by = {m['name']: m for m in out}
        self.assertEqual(by['person request: can I speak to a caseworker?']['status'], 'pass')
        self.assertEqual(by['confirm accepted']['status'], 'inconclusive')
        self.assertEqual(by['out of scope: how do I apply for housing benefit?']['status'], 'pass')
        self.assertEqual(by['second miss carries a handover']['status'], 'FAIL')                   # the fake never hands over


class FixTests(PanelTests):
    def test_handover_turn_counts_as_the_second_miss(self):
        seen = {'n': 0}

        def script(message):
            seen['n'] += 1
            inp = {'scope': 'in_scope', 'search': 'none', 'relevance': 'none', 'clarified': 0, 'misses': 0}
            if seen['n'] == 2:
                return {'status': 'faq_no_match', 'handover': 'x'}, [line('handover', [], 9, dict(inp, misses=1))]
            return {'status': 'faq_no_match'}, [line('not_covered', [], 9, inp)]

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ev.paths, 'INTERACTION_LOGS', Path(d)), \
                    mock.patch('requests.Session', side_effect=lambda: FakeHttp(d, script)), mock.patch.object(ev.time, 'sleep'):
                out = ev.scenarios('http://x', '1', 'code', progress=lambda *_: None)
        by = {m['name']: m for m in out}
        self.assertEqual(by['second miss carries a handover']['status'], 'pass')
        self.assertEqual(by['no second handover after it']['status'], 'pass')

    def test_out_of_scope_faq_ask_is_not_a_search(self):
        script = lambda m: ({'status': 'faq_out_of_scope'}, [{'kind': 'faq_ask', 'decision': 'out_of_scope'},
                                                             line('out_of_scope', [], 1)])
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ev.paths, 'INTERACTION_LOGS', Path(d)), \
                    mock.patch('requests.Session', side_effect=lambda: FakeHttp(d, script)), mock.patch.object(ev.time, 'sleep'):
                p = ev.Panel('http://x', '1')
                p.start()
                self.assertFalse(p.ask('weather', 'code')['searched'])

    def test_person_handover_has_no_table_row_and_no_dmn_violation(self):
        l = line('handover', [], None, {'scope': 'in_scope', 'search': 'none', 'relevance': 'none', 'clarified': 0, 'misses': 0})
        self.assertEqual(ev.check_line(l, 'shadow'), [])

    def test_replay_clicks_the_shown_faq_to_set_the_context(self):
        calls = []

        class Http(FakeHttp):
            def post(self, url, json=None, timeout=None):
                if url.endswith('/confirm'):
                    calls.append(json)
                    r = mock.Mock(status_code=200)
                    r.json.return_value = {'status': 'question'}
                    return r
                return super().post(url, json, timeout)

        def script(message):
            if message.startswith('what if I have prior work'):
                return ({'status': 'faq_related', 'match_id': 'm', 'candidates': [{'candidate_key': 'FAQ_01'}, {'candidate_key': 'FAQ_17'}]},
                        [line('offer', ['FAQ_01', 'FAQ_17'], 5)])
            return {'status': 'faq_no_match'}, [line('not_covered', [], 9)]

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ev.paths, 'INTERACTION_LOGS', Path(d)), \
                    mock.patch('requests.Session', side_effect=lambda: Http(d, script)), mock.patch.object(ev.time, 'sleep'):
                out = ev.replay_cases('http://x', '1', 1, 'code', only={'n01'}, progress=lambda *_: None)
        self.assertEqual(calls[0]['candidate_key'], 'FAQ_17')
        self.assertTrue(out[0]['context'])
