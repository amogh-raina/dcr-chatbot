"""Interaction log identifiers and the turn recorder (spec 02, T3). No model call, no DCR call."""
import hashlib
import json
import logging
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dcrai import paths, registry
import dcrai.observability.interaction_log as ilog
import dcrai.observability.turn_trace as tt

ROOT = Path(paths.ROOT)


class TraceCase(unittest.TestCase):
    """A temporary log folder and registry folder, logging on."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.logs, self.snapshots = self.tmp / 'logs', self.tmp / 'registry'
        patch.object(ilog, 'DIRECTORY', str(self.logs)).start()
        patch.object(ilog, 'ENABLED', True).start()
        patch.object(paths, 'REGISTRY_SNAPSHOTS', self.snapshots).start()
        self.addCleanup(patch.stopall)

    def started(self, interface='panel', xml='<a/>', graph_id='2014078', simulation_id=7):
        state = {'simulation_id': simulation_id}
        if xml is not None:
            state['graph_xml'] = xml
        ilog.start(state, graph_id, simulation_id, interface=interface)
        return state

    def lines(self, state, *kinds):
        path = self.logs / f"{state['interaction']['id']}.jsonl"
        rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
        return [r for r in rows if not kinds or r['kind'] in kinds]


class StartLineTests(TraceCase):
    def test_start_line_has_every_identifier(self):
        state = self.started()
        row = self.lines(state, 'start')[0]
        self.assertEqual((row['schema'], row['interface'], row['graph_id'], row['simulation_id']),
                         (2, 'panel', '2014078', 7))
        self.assertEqual(row['interaction_id'], state['interaction']['id'])
        self.assertEqual(row['registry_version'], registry.version())
        self.assertEqual(row['graph_revision'], '2014078@' + hashlib.sha256(b'<a/>').hexdigest()[:12])
        self.assertEqual(row['seq'], 1)

    def test_start_writes_the_registry_snapshot_once(self):
        first = self.started()
        self.started()
        files = sorted(p.name for p in self.snapshots.iterdir())
        self.assertEqual(files, [registry.version() + '.json'])
        self.assertEqual(first['interaction']['registry_version'], registry.version())

    def test_new_lines_use_interaction_id_not_interaction(self):
        state = self.started()
        ilog.record(state, 'question', field='Form0:A1')
        for row in self.lines(state):
            self.assertIn('interaction_id', row)
            self.assertNotIn('interaction', row)

    def test_graph_revision_format(self):
        digest = hashlib.sha256('<a/>'.encode('utf-8')).hexdigest()[:12]
        self.assertEqual(ilog.graph_revision('2014078', '<a/>'), f'2014078@{digest}')
        self.assertEqual(ilog.graph_revision('2014078', '<a/>'), ilog.graph_revision('2014078', '<a/>'))
        self.assertNotEqual(ilog.graph_revision('2014078', '<a/>'), ilog.graph_revision('2014078', '<b/>'))
        self.assertEqual(ilog.graph_revision('2014078', None), '2014078@unknown')
        self.assertEqual(ilog.graph_revision('2014078', ''), '2014078@unknown')
        self.assertEqual(ilog.graph_revision(5, b'<a/>'), f'5@{digest}')
        state = self.started(xml=None)
        self.assertEqual(self.lines(state, 'start')[0]['graph_revision'], '2014078@unknown')

    def test_ilog_start_callers_pass_interface(self):
        files = [ROOT / 'app.py'] + sorted((ROOT / 'dcrai').rglob('*.py')) + sorted((ROOT / 'faq_search').rglob('*.py'))
        calls = 0
        for path in files:
            text = path.read_text(encoding='utf-8')
            for match in re.finditer(r'\bilog\.start\(', text):
                depth, index = 1, match.end()
                while depth and index < len(text):
                    depth += {'(': 1, ')': -1}.get(text[index], 0)
                    index += 1
                call = text[match.end():index - 1]
                if path.name == 'interaction_log.py':
                    continue      # the warning text in start() itself
                calls += 1
                self.assertIn('interface=', call, f'{path.relative_to(ROOT)}: ilog.start without interface=')
        self.assertGreaterEqual(calls, 2)    # the chat /init and the panel application_init

    def test_start_without_interface_is_unknown_and_warns(self):
        state = {}
        with self.assertLogs('dcrai.observability.interaction_log', level=logging.WARNING) as logged:
            ilog.start(state, 'g', 1)
        self.assertEqual(len(logged.records), 1)
        self.assertEqual(self.lines(state, 'start')[0]['interface'], 'unknown')

    def test_log_off_writes_nothing(self):
        with patch.object(ilog, 'ENABLED', False):
            state = self.started()

            @tt.turn('panel')
            def request(state, data):
                return {'status': 'answer'}
            request(state, {'message': 'hello'})
        self.assertFalse(self.logs.exists())
        self.assertFalse(self.snapshots.exists())
        self.assertEqual(state['turn'], 1)


class TurnLineTests(TraceCase):
    def setUp(self):
        super().setUp()
        self.state = self.started(interface='chat')

        @tt.turn('chat')
        def echo(state, data):
            return {'status': 'answer', 'echo': data}
        self.echo = echo

    def test_one_turn_line_per_request(self):
        self.echo(self.state, {'message': 'first question'})
        self.echo(self.state, {'message': 'second question'})
        rows = self.lines(self.state, 'turn')
        self.assertEqual([r['turn'] for r in rows], [1, 2])
        row = rows[0]
        self.assertEqual((row['interface'], row['entry'], row['message'], row['status'], row['schema']),
                         ('chat', 'message', 'first question', 'answer', 2))
        self.assertEqual(row['registry_version'], registry.version())
        self.assertEqual(row['graph_revision'], self.state['interaction']['graph_revision'])
        self.assertEqual(row['simulation_id'], 7)
        self.assertIsInstance(row['latency_s'], float)
        self.assertEqual(row['interaction_id'], self.state['interaction']['id'])

    def test_turn_line_is_written_when_the_request_raises(self):
        @tt.turn('chat')
        def failing(state, data):
            raise ValueError('secret text')
        with self.assertRaises(ValueError) as caught:
            failing(self.state, {'message': 'x'})
        self.assertEqual(str(caught.exception), 'secret text')
        row = self.lines(self.state, 'turn')[0]
        self.assertEqual(row['error'], 'ValueError')
        self.assertNotIn('secret text', json.dumps(row))
        self.assertNotIn('status', row)

    def test_turn_counter_and_envelope(self):
        state = self.started(interface='panel')
        self.assertNotIn('turn', state)

        @tt.turn('panel')
        def request(state, data):
            ilog.record(state, 'question', field='inside')
            return {}
        request(state, {'message': 'a'})
        request(state, {'message': 'b'})
        ilog.record(state, 'question', field='outside')
        self.assertEqual(state['turn'], 2)
        inside = [r for r in self.lines(state, 'question') if r['field'] == 'inside']
        outside = [r for r in self.lines(state, 'question') if r['field'] == 'outside']
        self.assertEqual([r['turn'] for r in inside], [1, 2])
        self.assertNotIn('turn', outside[0])

    def test_a_caller_supplied_turn_wins_over_the_envelope(self):
        @tt.turn('chat')
        def request(state, data):
            ilog.record(state, 'faq_reaction', turn=1, next_action='accepted')
            return {}
        request(self.state, {'message': 'a'})
        request(self.state, {'message': 'b'})
        self.assertEqual([r['turn'] for r in self.lines(self.state, 'faq_reaction')], [1, 1])

    def test_outcome_fields_are_copied_from_the_faq_outcome_line(self):
        @tt.turn('chat')
        def request(state, data):
            if data.get('log'):
                ilog.record(state, 'faq_outcome', interface='chat', outcome='confirm', outcome_row=6,
                            faq_ids=['FAQ_21'], via='typed', outcome_inputs={'k': 1})
            return {'status': 'faq_confirm'}
        request(self.state, {'message': 'a', 'log': True})
        request(self.state, {'message': 'b'})
        first, second = self.lines(self.state, 'turn')
        self.assertEqual((first['outcome'], first['outcome_row'], first['faq_ids'], first['via'],
                          first['outcome_inputs']), ('confirm', 6, ['FAQ_21'], 'typed', {'k': 1}))
        for key in ('outcome', 'outcome_row', 'faq_ids', 'via', 'outcome_inputs'):
            self.assertNotIn(key, second)

    def test_reaction_line_sets_reacts_to(self):
        @tt.turn('chat')
        def request(state, data):
            if data.get('react'):
                ilog.record(state, 'faq_reaction', turn=2, outcome='confirm', next_action='accepted')
            return {}
        request(self.state, {'message': 'a'})
        request(self.state, {'message': 'b', 'react': True})
        first, second = self.lines(self.state, 'turn')
        self.assertNotIn('reacts_to', first)
        self.assertEqual(second['reacts_to'], 2)

    def test_handover_line_is_copied(self):
        @tt.turn('panel')
        def request(state, data):
            ilog.record(state, 'handover', reason=1)
            return {}
        request(self.state, {'message': 'a'})
        self.assertEqual(self.lines(self.state, 'turn')[0]['handover'], {'reason': 1})

    def test_note_adds_fields_and_is_a_no_op_outside_a_request(self):
        tt.note(context={'x': 1})     # outside a request: nothing happens, nothing raises

        @tt.turn('chat')
        def request(state, data):
            tt.note(context={'last_answered_faq': 'FAQ_1'}, extra=None)
            return {}
        request(self.state, {'message': 'a'})
        row = self.lines(self.state, 'turn')[0]
        self.assertEqual(row['context'], {'last_answered_faq': 'FAQ_1'})
        self.assertNotIn('extra', row)

    def test_recorder_fault_never_changes_the_reply(self):
        @tt.turn('chat')
        def request(state, data):
            return {'a': 1}
        with patch.object(ilog, 'record', side_effect=OSError('disk full')):
            with self.assertLogs('dcrai.observability.turn_trace', level=logging.WARNING):
                self.assertEqual(request(self.state, {'message': 'x'}), {'a': 1})

    def test_registry_fault_is_swallowed(self):
        @tt.turn('chat')
        def request(state, data):
            return {'a': 1}
        with patch.object(registry, 'version', side_effect=RuntimeError('boom')):
            with self.assertLogs('dcrai.observability.turn_trace', level=logging.WARNING):
                self.assertEqual(request(self.state, {'message': 'x'}), {'a': 1})
        row = self.lines(self.state, 'turn')[0]    # the version on the start line is the fallback
        self.assertEqual(row['registry_version'], self.state['interaction']['registry_version'])

    def test_an_observer_fault_is_swallowed(self):
        def broken(state, kind, line):
            raise RuntimeError('observer')
        with patch.object(ilog, 'OBSERVERS', [broken, tt.observe]):
            with self.assertLogs('dcrai.observability.interaction_log', level=logging.WARNING):
                ilog.record(self.state, 'question', field='x')
        self.assertEqual(len(self.lines(self.state, 'question')), 1)

    def test_nested_traced_calls_make_one_line(self):
        @tt.turn('panel')
        def inner(state, data):
            return {'status': 'inner'}

        @tt.turn('panel')
        def outer(state, data):
            return inner(state, data)
        outer(self.state, {'message': 'a'})
        rows = self.lines(self.state, 'turn')
        self.assertEqual((len(rows), rows[0]['turn'], rows[0]['status']), (1, 1, 'inner'))
        self.assertEqual(self.state['turn'], 1)

    def test_hooks_do_nothing_outside_a_request(self):
        self.assertIsNone(tt.active())
        self.assertIsNone(tt.add_call({'name': 'x'}))
        self.assertIsNone(tt.add_search({'query': 'x'}))
        self.assertIsNone(tt.add_dcr_event({'id': 'x'}))
        self.assertEqual(self.lines(self.state, 'turn'), [])

    def test_hooks_collect_records_inside_a_request(self):
        @tt.turn('chat')
        def request(state, data):
            index = tt.add_call({'api': 'responses', 'name': 'query_rewrite', 'input': {'message': 'a?'},
                                 'output': {'search_query': 'A question?'}})
            self.assertEqual(index, 0)
            tt.add_call({'api': 'decisions', 'name': 'triage'})
            tt.add_search({'query': 'A question?', 'status': 'found'})
            tt.add_dcr_event({'id': 'FAQ_Triage', 'value': '1', 'ok': True})
            return {}
        request(self.state, {'message': 'a?'})
        row = self.lines(self.state, 'turn')[0]
        self.assertEqual([c['name'] for c in row['calls']], ['query_rewrite', 'triage'])
        self.assertEqual(row['rewrite'], {'from': 'a?', 'text': 'A question?', 'call': 0})
        self.assertEqual(row['searches'][0]['query'], 'A question?')
        self.assertEqual(row['dcr_events'][0]['id'], 'FAQ_Triage')

    def test_empty_collections_are_not_written(self):
        self.echo(self.state, {'message': 'a'})
        row = self.lines(self.state, 'turn')[0]
        for key in ('calls', 'searches', 'dcr_events', 'rewrite', 'handover', 'reacts_to', 'error', 'truncated'):
            self.assertNotIn(key, row)

    def test_long_string_is_cut_and_flagged(self):
        @tt.turn('chat')
        def request(state, data):
            tt.add_call({'api': 'decisions', 'name': 'x', 'input': 'a' * 30000})
            return {}
        request(self.state, {'message': 'm'})
        row = self.lines(self.state, 'turn')[0]
        stored = row['calls'][0]['input']
        self.assertTrue(row['truncated'])
        self.assertTrue(stored.startswith('a' * 20000))
        self.assertLess(len(stored), 20100)
        self.assertIn('cut 10000 characters', stored)

    def test_a_huge_line_is_cut_harder(self):
        @tt.turn('chat')
        def request(state, data):
            for n in range(20):
                tt.add_call({'api': 'decisions', 'name': f'q{n}', 'input': 'b' * 20000})
            return {}
        request(self.state, {'message': 'm'})
        path = self.logs / f"{self.state['interaction']['id']}.jsonl"
        longest = max(len(x.encode('utf-8')) for x in path.read_text(encoding='utf-8').splitlines())
        self.assertLess(longest, 256 * 1024)
        self.assertTrue(self.lines(self.state, 'turn')[0]['truncated'])

    def test_unserialisable_values_do_not_lose_the_line(self):
        @tt.turn('chat')
        def request(state, data):
            tt.add_call({'api': 'responses', 'name': 'x', 'input': {'bad': {1, 2}}})
            return {}
        request(self.state, {'message': 'm'})
        self.assertEqual(len(self.lines(self.state, 'turn')), 1)


class EntryTests(TraceCase):
    def run_entry(self, interface, name, data):
        state = self.started(interface=interface)

        def fn(state, data):
            return {}
        fn.__name__ = name
        tt.turn(interface)(fn)(state, data)
        return self.lines(state, 'turn')[0]

    def test_chat_entries(self):
        row = self.run_entry('chat', 'handle', {'message': 'Who can get it?'})
        self.assertEqual((row['entry'], row['message']), ('message', 'Who can get it?'))
        row = self.run_entry('chat', 'handle', {'action': 'reply', 'retrieval_prompt_id': 'p', 'value': '2'})
        self.assertEqual((row['entry'], row['input_value']), ('reply', '2'))
        self.assertNotIn('message', row)
        row = self.run_entry('chat', 'handle', {'action': 'example', 'faq_id': 'FAQ_01'})
        self.assertEqual((row['entry'], row['input_value']), ('example', 'FAQ_01'))
        for action in ('end', 'rephrase', 'apply'):
            self.assertEqual(self.run_entry('chat', 'handle', {'action': action})['entry'], action)

    def test_panel_entries(self):
        row = self.run_entry('panel', 'ask', {'message': 'how old?', 'scope': 'field'})
        self.assertEqual((row['entry'], row['message']), ('message', 'how old?'))
        row = self.run_entry('panel', 'ask', {'related': 'FAQ_21'})
        self.assertEqual((row['entry'], row['input_value']), ('related', 'FAQ_21'))
        row = self.run_entry('panel', 'confirm', {'match_id': 'm1', 'candidate_key': 'FAQ_P08'})
        self.assertEqual((row['entry'], row['input_value']), ('confirm', 'FAQ_P08'))

    def test_a_non_dict_request_body_is_tolerated(self):
        row = self.run_entry('chat', 'handle', None)
        self.assertEqual(row['entry'], 'message')


if __name__ == '__main__':
    unittest.main()
