"""Reader and rates for interaction trace files (spec 02, T6). Fixture: tests/fixtures/trace_interaction_sample.jsonl."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from dcrai.observability import trace_reader as reader

FIXTURE = Path(__file__).parent / 'fixtures' / 'trace_interaction_sample.jsonl'


def rewrite(lines, path):
    path.write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in lines) + '\n', encoding='utf-8')


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.lines = reader.load(FIXTURE)

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = reader.main(list(argv))
        return code, out.getvalue()

    def test_fixture_shape(self):
        kinds = [x['kind'] for x in self.lines]
        self.assertEqual(kinds[0], 'start')
        self.assertEqual(kinds.count('turn'), 10)
        self.assertEqual((self.lines.skipped, self.lines.legacy), (0, False))

    def test_reactions_are_joined_to_their_turn(self):
        by_turn = {t['turn']: t for t in reader.turns(self.lines)}
        self.assertEqual(by_turn[1]['reaction'], 'accepted')
        self.assertEqual(by_turn[3]['reaction'], 'rejected')
        self.assertEqual(by_turn[5]['reaction'], 'chose')
        self.assertEqual(by_turn[5]['reaction_line']['faq_id'], 'FAQ_41')
        for number in (2, 4, 6, 7, 8, 9, 10):
            self.assertNotIn('reaction', by_turn[number])
        self.assertEqual([t['turn'] for t in reader.turns(self.lines)], list(range(1, 11)))
        self.assertEqual(by_turn[2]['reacts_to'], 1)

    def test_confirm_accept_rate(self):
        # two confirm outcomes (turns 1 and 3); one accepted
        self.assertEqual(reader.confirm_accept_counts(self.lines), (1, 2))
        self.assertEqual(reader.confirm_accept_rate(self.lines), 0.5)

    def test_re_explain_rate_counts_typed_follow_ups_only(self):
        # triggers: turn 3 (confirm rejected), 5 (clarify), 7 (offer), 8 (not_covered). Turn 1 was accepted.
        # next outcome: 3 -> turn 5 typed (counts); 5 -> turn 6 chosen (does not); 7 -> turn 8 field-typed (counts);
        # 8 -> turn 9 rewritten (counts).
        self.assertEqual(reader.re_explain_counts(self.lines), (3, 4))
        self.assertEqual(reader.re_explain_rate(self.lines), 0.75)

    def test_related_and_example_follow_ups_do_not_count(self):
        def outcome(turn, name, via):
            return {'kind': 'faq_outcome', 'turn': turn, 'outcome': name, 'via': via}
        for via, expected in [('related', 0), ('example', 0), ('chosen', 0), ('field-composed', 1), ('field-typed', 1),
                              ('typed', 1), ('rewritten', 1)]:
            with self.subTest(via=via):
                lines = [outcome(1, 'offer', 'typed'), outcome(2, 'answer', via)]
                self.assertEqual(reader.re_explain_counts(lines), (expected, 1))

    def test_a_trigger_with_no_later_outcome_is_not_re_explained(self):
        lines = [{'kind': 'faq_outcome', 'turn': 1, 'outcome': 'not_covered', 'via': 'typed'}]
        self.assertEqual(reader.re_explain_counts(lines), (0, 1))

    def test_rates_are_none_without_data(self):
        self.assertIsNone(reader.confirm_accept_rate([]))
        self.assertIsNone(reader.re_explain_rate([]))

    def test_outcome_on_a_turn_line_counts_when_no_faq_outcome_line_exists(self):
        lines = [{'kind': 'turn', 'turn': 1, 'outcome': 'confirm', 'via': 'typed'},
                 {'kind': 'faq_reaction', 'turn': 1, 'outcome': 'confirm', 'next_action': 'rejected'},
                 {'kind': 'turn', 'turn': 2, 'outcome': 'answer', 'via': 'rewritten'}]
        self.assertEqual(reader.confirm_accept_counts(lines), (0, 1))
        self.assertEqual(reader.re_explain_counts(lines), (1, 1))

    def test_a_faq_outcome_and_its_turn_line_are_one_record(self):
        # the fixture holds both for every outcome: confirm outcomes are still 2, not 4
        self.assertEqual(reader.confirm_accept_counts(self.lines)[1], 2)

    def test_check_passes_on_a_complete_file(self):
        self.assertEqual(reader.check(self.lines), [])
        code, output = self.run_main('--check', str(FIXTURE))
        self.assertEqual(code, 0)
        self.assertIn('check: ok', output)

    def test_check_reports_a_turn_without_versions(self):
        broken = [dict(x) for x in self.lines]
        target = next(x for x in broken if x['kind'] == 'turn' and x['turn'] == 4)
        del target['registry_version']
        del next(x for x in broken if x['kind'] == 'turn' and x['turn'] == 6)['graph_revision']
        problems = reader.check(broken)
        self.assertEqual(len(problems), 2)
        self.assertIn('turn 4 has no registry_version', problems[0])
        self.assertIn('turn 6 has no graph_revision', problems[1])
        path = self.tmp / 'broken.jsonl'
        rewrite(broken, path)
        code, output = self.run_main('--check', str(path))
        self.assertEqual(code, 1)
        self.assertIn('PROBLEM', output)

    def test_check_reports_a_start_line_without_schema_and_a_backwards_turn(self):
        lines = [dict(x) for x in self.lines]
        del lines[0]['schema']
        turn_lines = [x for x in lines if x['kind'] == 'turn']
        turn_lines[5]['turn'] = 1
        problems = reader.check(lines)
        self.assertTrue(any('no schema' in p for p in problems))
        self.assertTrue(any('goes backwards' in p for p in problems))

    def test_load_skips_broken_lines(self):
        text = FIXTURE.read_text(encoding='utf-8').splitlines()
        path = self.tmp / 'cut.jsonl'
        path.write_text('\n'.join(text[:3] + [text[3][:30]] + ['', '[1, 2]'] + text[4:]) + '\n', encoding='utf-8')
        loaded = reader.load(path)
        self.assertEqual(loaded.skipped, 2)          # the truncated line and the non-object line; the blank one is free
        self.assertEqual(len(loaded), len(text) - 1)

    def test_old_format_file_is_readable(self):
        path = self.tmp / 'old.jsonl'
        rewrite([{'interaction': 'abc', 'seq': 1, 'at': 'x', 'elapsed_s': 0.0, 'kind': 'start',
                  'graph_id': '1', 'simulation_id': 2},
                 {'interaction': 'abc', 'seq': 2, 'at': 'x', 'elapsed_s': 1.0, 'kind': 'question', 'field': 'Form0:A1'}],
                path)
        loaded = reader.load(path)
        self.assertTrue(loaded.legacy)
        self.assertEqual(loaded[0]['interaction_id'], 'abc')
        self.assertEqual(reader.check(loaded), [])
        code, output = self.run_main('--check', str(path))
        self.assertEqual(code, 0)
        self.assertIn('old format', output)

    def test_rates_flag_prints_both_rates(self):
        code, output = self.run_main('--rates', str(FIXTURE))
        self.assertEqual(code, 0)
        self.assertIn('confirm accept rate: 50.0% (1 of 2)', output)
        self.assertIn('re-explain rate: 75.0% (3 of 4)', output)

    def test_missing_file_is_an_error_not_a_pass(self):
        with self.assertRaises(OSError):
            reader.main(['--check', str(self.tmp / 'nope.jsonl')])

    def test_lines_written_by_the_recorder_are_accepted(self):
        """A file written by interaction_log and turn_trace passes --check."""
        from unittest.mock import patch
        import dcrai.observability.interaction_log as ilog
        import dcrai.observability.turn_trace as tt
        from dcrai import paths
        with patch.object(ilog, 'DIRECTORY', str(self.tmp / 'logs')), patch.object(ilog, 'ENABLED', True), \
                patch.object(paths, 'REGISTRY_SNAPSHOTS', self.tmp / 'registry'):
            state = {'simulation_id': 3, 'graph_xml': '<a/>'}
            ilog.start(state, '1', 3, interface='chat')

            @tt.turn('chat')
            def request(state, data):
                ilog.record(state, 'faq_outcome', interface='chat', turn=state['turn'], outcome='confirm',
                            outcome_row=6, faq_ids=['FAQ_1'], via='typed')
                return {'status': 'faq_confirm'}
            request(state, {'message': 'q'})
            path = self.tmp / 'logs' / f"{state['interaction']['id']}.jsonl"
        loaded = reader.load(path)
        self.assertEqual(reader.check(loaded), [])
        self.assertEqual(reader.confirm_accept_counts(loaded), (0, 1))


if __name__ == '__main__':
    unittest.main()
