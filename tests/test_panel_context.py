"""Help panel context record (spec 02). T7: the graph carries the Panel_Context event. No model call, no network."""
import unittest
import xml.etree.ElementTree as ET

from dcrai import paths

GRAPH = paths.GRAPHS / 'SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml'


@unittest.skipUnless(GRAPH.exists(), 'xml graphs/ is gitignored and absent here')
class PanelContextGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ET.parse(GRAPH).getroot()
        cls.events = cls.root.find('specification/resources/events')

    def event(self, event_id):
        found = [e for e in self.events.findall('event') if e.get('id') == event_id]
        self.assertEqual(len(found), 1, event_id)
        return found[0]

    def test_builder_output_has_the_panel_context_event(self):
        event = self.event('Panel_Context')
        custom = event.find('custom')
        self.assertEqual(custom.find('eventData/dataType').text, 'text')
        self.assertEqual([r.text for r in custom.findall('roles/role')], ['Chatbot'])
        self.assertEqual([g.text for g in custom.findall('groups/group')], ['FAQContext', 'PanelContext'])
        declared = [g.text for g in self.root.findall('specification/resources/custom/groups/group')]
        self.assertIn('PanelContext', declared)
        self.assertIn('FAQContext', declared)

    def test_it_is_included_and_not_pending(self):
        included = [e.get('id') for e in self.root.findall('runtime/marking/included/event')]
        pending = [e.get('id') for e in self.root.findall('runtime/marking/pendingResponses/event')]
        self.assertIn('Panel_Context', included)
        self.assertNotIn('Panel_Context', pending)

    def test_it_is_in_no_relation(self):
        for kind in self.root.find('specification/constraints'):
            for relation in kind:
                self.assertNotIn('Panel_Context', (relation.get('sourceId'), relation.get('targetId')))

    def test_label_is_unique_and_mapped(self):
        labels = [l.get('id') for l in self.root.findall('specification/resources/labels/label')]
        self.assertEqual(labels.count('Help panel context'), 1)
        mapped = [(m.get('eventId'), m.get('labelId'))
                  for m in self.root.findall('specification/resources/labelMappings/labelMapping')]
        self.assertEqual(mapped.count(('Panel_Context', 'Help panel context')), 1)
        self.assertEqual(len(labels), len(set(labels)))

    def test_it_has_the_shape_of_faq_answered(self):
        """R28: same type, role, no effect and no choice dictionary as the chat's context event."""
        def shape(event):
            custom = event.find('custom')
            data = custom.find('eventData/dataType')
            return (data.text, [r.text for r in custom.findall('roles/role')], custom.findtext('eventScope'),
                    custom.findtext('eventType') or '', len(custom.findall('eventTypeData/parameter')),
                    custom.find('eventData/dictionary') is None)
        self.assertEqual(shape(self.event('Panel_Context')), shape(self.event('FAQ_Answered')))

    def test_form0_and_existing_events_are_unchanged_in_kind(self):
        ids = {e.get('id') for e in self.events.findall('event')}
        for needed in ('Form0', 'FAQ_Answered', 'FAQ_Triage', 'FAQ_UserQuestion', 'Help_Escalate', 'Help_Handover'):
            self.assertIn(needed, ids)


# ------------------------------------------------------------------ T8: the host side
import json
import os
import shutil
import tempfile
from contextlib import ExitStack
from unittest.mock import patch

import dcrai.application.application_runtime as app
import dcrai.llm.retrieval_llm as llm
import dcrai.chat.retrieval_runtime as rt
from dcrai.application import panel_context as pc
from tests.test_retrieval_runtime import clarify, ev, single
from tests.test_trace_hooks import RealEntryCase


class PanelContextUnitTests(unittest.TestCase):
    def record(self, **over):
        base = {'v': 1, 'faqs': [{'id': 'FAQ_21', 'said': 'a' * 200, 'asked': 'b' * 200},
                                 {'id': 'FAQ_P08', 'said': 'c' * 200}], 'field': 'Form0:A3', 'msg': 'm' * 500}
        base.update(over)
        return base

    @staticmethod
    def size(record):
        return len(json.dumps(record, ensure_ascii=False, separators=(',', ':')))

    def test_fit_returns_the_text_unchanged_when_it_fits(self):
        record = self.record()
        self.assertEqual(json.loads(pc.fit(record, limit=5000)), record)

    def test_fit_cuts_in_order_second_faq_then_msg_then_said_and_asked(self):
        full = self.size(self.record())
        step1 = json.loads(pc.fit(self.record(), limit=full - 1))
        self.assertEqual((len(step1['faqs']), len(step1['msg'])), (1, 500))
        step2 = json.loads(pc.fit(self.record(), limit=self.size(step1) - 1))
        self.assertEqual((len(step2['faqs']), len(step2['msg']), len(step2['faqs'][0]['said'])), (1, 200, 200))
        step3 = json.loads(pc.fit(self.record(), limit=self.size(step2) - 1))
        self.assertEqual((len(step3['msg']), len(step3['faqs'][0]['said']), len(step3['faqs'][0]['asked'])),
                         (200, 100, 100))

    def test_fit_gives_none_when_nothing_helps(self):
        self.assertIsNone(pc.fit(self.record(), limit=40))

    def test_fit_never_returns_more_than_the_limit(self):
        for limit in (1500, 900, 500, 380, 300):
            with self.subTest(limit=limit):
                text = pc.fit(self.record(), limit=limit)
                self.assertTrue(text is None or len(text) <= limit)

    def test_build_orders_newest_first_caps_entries_and_drops_equal_rewrites(self):
        state = {'application_prompt': {'field': {'id': 'F' * 100}}, 'help_last_message': 'x' * 900}
        previous = {'v': 1, 'faqs': [{'id': 'FAQ_1', 'said': 'one'}, {'id': 'FAQ_2', 'said': 'two'}]}
        record = pc.build(state, previous, {'id': 'FAQ_3', 'said': 's' * 300, 'asked': 's' * 300})
        self.assertEqual([f['id'] for f in record['faqs']], ['FAQ_3', 'FAQ_1'])
        self.assertEqual(len(record['faqs'][0]['said']), 200)
        self.assertNotIn('asked', record['faqs'][0])          # equal to what was said
        self.assertEqual((len(record['field']), len(record['msg'])), (80, 500))
        self.assertEqual(record['v'], 1)

    def test_read_accepts_only_a_valid_executed_version_one_record(self):
        def payload(value, executed='t1'):
            return {'events': [{'id': 'Panel_Context', 'executed': executed, 'value': value, 'enabled': True}]}
        good = '{"v":1,"faqs":[{"id":"FAQ_1","said":"s"}],"field":"Form0:A1","msg":"m"}'
        self.assertEqual(pc.read(payload(good))['faqs'][0]['id'], 'FAQ_1')
        self.assertEqual(pc.read(payload(json.dumps(good)))['msg'], 'm')       # a double-encoded value
        for bad in ['not json', '{"v":2}', '[]', '{"v":1,"faqs":"x"}', '{"v":1,"faqs":[{"id":3}]}', '{"v":1,"msg":5}', '']:
            with self.subTest(bad=bad):
                self.assertIsNone(pc.read(payload(bad)))
        self.assertIsNone(pc.read(payload(good, executed=None)))
        self.assertIsNone(pc.read({'events': []}))

    def test_expand_returns_question_topic_and_answer_start(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        records = {'records': [
            {'id': 'FAQ_A', 'canonical_question': 'Question A?', 'topic': 'topic_a',
             'answer_text': 'First   line.\n\nSecond line. ' + 'x' * 400},
            {'id': 'FAQ_B', 'canonical_question': 'Question B?', 'topic': 'topic_b', 'answer_text': 'Short.'}]}
        with open(os.path.join(folder, 'faq_qa_records.json'), 'w', encoding='utf-8') as handle:
            json.dump(records, handle)
        with patch.object(pc.paths, 'FAQ_DATA', type(pc.paths.FAQ_DATA)(folder)):
            a, b = pc.expand('FAQ_A'), pc.expand('FAQ_B')
            self.assertIsNone(pc.expand('FAQ_ZZ'))
            self.assertEqual(pc.last_faq({'faqs': [{'id': 'FAQ_B', 'said': 'z'}]})['question'], 'Question B?')
        self.assertEqual((a['question'], a['topic']), ('Question A?', 'topic_a'))
        self.assertTrue(a['answer_start'].startswith('First line. Second line. xxx'))
        self.assertEqual(len(a['answer_start']), 300)
        self.assertEqual(b['answer_start'], 'Short.')

    def test_expand_works_on_the_real_records(self):
        found = pc.expand('FAQ_31')
        self.assertTrue(found is None or (found['question'] and len(found['answer_start']) <= 300))


class PanelContextHostTests(RealEntryCase):
    def setUp(self):
        super().setUp()
        self.dcr.events['Panel_Context'] = ev('Panel_Context', dtype='text', tags='FAQContext,PanelContext')
        self.dcr.events['Form0:Email'].update(included=True, enabled=True)
        app.start(self.state)
        self.begin('panel')

    def writes(self):
        return [v for e, v in self.dcr.executed if e == 'Panel_Context']

    def contextual(self, rewrite):
        """Decisions on, the panel classifier sure the message needs context, the rewrite fixed. No model call."""
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name, value in (('decisions_enabled', True),):
            stack.enter_context(patch.object(llm, name, return_value=value))
        stack.enter_context(patch.object(llm, 'relevant_decisions', side_effect=lambda m, c, **k: [x['id'] for x in c]))
        stack.enter_context(patch.object(llm, 'panel_signals_decisions',
                                         return_value={'contextual': 0.9, 'distress': 0.0}))
        return stack.enter_context(patch.object(llm, 'rewrite', return_value=rewrite))

    def test_panel_writes_one_context_value_per_request(self):
        self.dcr.api = single()
        app.ask(self.state, {'message': 'who can get it?'})
        self.assertEqual(len(self.writes()), 1)
        value = json.loads(self.writes()[0])
        self.assertEqual(value['v'], 1)
        self.assertEqual(value['faqs'], [{'id': 'FAQ_31', 'said': 'who can get it?'}])
        self.assertEqual((value['field'], value['msg']), ('Form0:Email', 'who can get it?'))
        self.assertEqual(self.dcr.comments['Panel_Context'], 'panel context')
        self.assertEqual(self.turn_lines()[0]['context_write'], 'ok')

    def test_the_write_comes_after_the_faq_steps_in_the_same_request(self):
        self.dcr.api = single()
        app.ask(self.state, {'message': 'who can get it?'})
        order = [e for e, _ in self.dcr.executed]
        self.assertEqual(order[-1], 'Panel_Context')
        self.assertLess(order.index('FAQ_UserQuestion'), order.index('Panel_Context'))

    def test_confirm_writes_the_context_with_the_chosen_faq(self):
        self.dcr.api = clarify()
        result = app.ask(self.state, {'message': 'medical docs'})
        first = json.loads(self.writes()[0])
        self.assertEqual((first['faqs'], first['msg']), ([], 'medical docs'))
        app.confirm(self.state, {'match_id': result['match_id'], 'candidate_key': 'FAQ_21'})
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(json.loads(self.writes()[-1])['faqs'], [{'id': 'FAQ_21', 'said': 'medical docs'}])

    def test_two_faqs_are_kept_newest_first(self):
        for fid, text in (('FAQ_01', 'first'), ('FAQ_21', 'second'), ('FAQ_31', 'third')):
            self.dcr.api = single(fid, 'Q?')
            app.ask(self.state, {'message': text})
        value = json.loads(self.writes()[-1])
        self.assertEqual([f['id'] for f in value['faqs']], ['FAQ_31', 'FAQ_21'])
        self.assertEqual(value['msg'], 'third')

    def test_value_never_exceeds_the_limit_and_the_cuts_show(self):
        self.dcr.api = single()
        with patch.object(pc, 'LIMIT', 400):
            app.ask(self.state, {'message': 'w' * 300})
        value = json.loads(self.writes()[0])
        self.assertLessEqual(len(self.writes()[0]), 400)
        self.assertEqual((len(value['msg']), len(value['faqs'][0]['said'])), (200, 100))
        self.dcr.api = single('FAQ_21', 'Q?')
        app.ask(self.state, {'message': 'v' * 600})
        self.assertLessEqual(len(self.writes()[-1]), pc.LIMIT)

    def test_fit_skips_the_write_when_nothing_helps(self):
        self.dcr.api = single()
        with patch.object(pc, 'LIMIT', 20):
            result = app.ask(self.state, {'message': 'who can get it?'})
        self.assertTrue(result['answered'])
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.turn_lines()[0]['context_write'], 'skipped')

    def test_unchanged_value_is_not_written_again(self):
        self.dcr.api = single()
        app.ask(self.state, {'message': 'who can get it?'})
        app.ask(self.state, {'message': 'who can get it?'})
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual([r['context_write'] for r in self.turn_lines()], ['ok', 'skipped'])

    def test_flag_off_writes_nothing_and_reads_session_fields(self):
        self.dcr.api = single()
        with patch.dict(os.environ, {'PANEL_CONTEXT_IN_DCR': '0'}):
            app.ask(self.state, {'message': 'who can get it?'})
            context = app.help_context(self.state, self.dcr.read(self.state))
        self.assertEqual(self.writes(), [])
        self.assertEqual(context['previous_question'], 'who can get it?')
        self.assertIn('FAQ_31', context['last_answered_faq'])
        self.assertEqual(self.turn_lines()[0]['context_write'], 'skipped')

    def failing_write(self, how):
        original = rt.repo.execute_raw_event.side_effect

        def execute(state, eid, value, comment='', role=None):
            if eid == 'Panel_Context':
                if how == 'raise':
                    raise ConnectionError('down')
                return False
            return original(state, eid, value, comment, role)
        rt.repo.execute_raw_event.side_effect = execute

    def test_failed_write_does_not_fail_the_request(self):
        self.failing_write('false')
        self.dcr.api = single()
        with self.assertLogs('dcrai.application.panel_context', level='WARNING'):
            result = app.ask(self.state, {'message': 'who can get it?'})
        self.assertTrue(result['answered'])
        self.assertEqual(result['faq_id'], 'FAQ_31')
        self.assertEqual(self.turn_lines()[0]['context_write'], 'failed')

    def test_a_write_that_raises_does_not_fail_the_request(self):
        self.failing_write('raise')
        self.dcr.api = single()
        with self.assertLogs('dcrai.application.panel_context', level='WARNING'):
            result = app.ask(self.state, {'message': 'who can get it?'})
        self.assertTrue(result['answered'])
        self.assertEqual(self.turn_lines()[0]['context_write'], 'failed')

    def test_an_error_in_the_request_skips_the_write(self):
        with self.assertRaises(app.ApplicationError):
            app.ask(self.state, {'message': ''})
        self.assertEqual(self.writes(), [])
        self.assertNotIn('context_write', self.turn_lines()[0])

    def test_context_is_read_from_dcr_when_session_fields_are_gone(self):
        self.dcr.api = single()
        app.ask(self.state, {'message': 'who can get it?'})
        del self.state['help_last_faq'], self.state['help_last_message']
        rewrite = self.contextual('Who can get handicaptillaeg and until when?')
        app.ask(self.state, {'message': 'and until when?'})
        context = rewrite.call_args.args[1]
        self.assertIn('FAQ_31', context['last_answered_faq'])
        self.assertEqual(context['previous_question'], 'who can get it?')
        self.assertEqual(self.turn_lines()[-1]['context']['source'], 'dcr')

    def test_unreadable_value_falls_back_to_session_fields(self):
        self.dcr.api = single()
        app.ask(self.state, {'message': 'who can get it?'})
        for value in ('not json', '{"v":2}'):
            with self.subTest(value=value):
                self.dcr.events['Panel_Context'].update(value=value)
                payload = self.dcr.read(self.state)
                self.assertIsNone(pc.read(payload))
                context = app.help_context(self.state, payload)
                self.assertEqual(context['previous_question'], 'who can get it?')
                self.assertIn('FAQ_31', context['last_answered_faq'])

    def test_graph_without_the_event_still_works(self):
        del self.dcr.events['Panel_Context']
        self.dcr.api = single()
        first = app.ask(self.state, {'message': 'who can get it?'})
        second = app.ask(self.state, {'message': 'who can get it?'})
        self.assertTrue(first['answered'] and second['answered'])
        self.assertEqual(self.writes(), [])
        self.assertIs(self.state['panel_context_present'], False)
        self.assertEqual(self.turn_lines()[1]['context']['source'], 'session')

    def test_value_holds_no_answer_text(self):
        self.dcr.api = single()
        app.ask(self.state, {'message': 'who can get it?'})
        for value in self.writes():
            self.assertNotIn('Para one.', value)
            self.assertNotIn('Para two.', value)

    def test_same_faq_detection_uses_the_context_record(self):
        self.dcr.api = single()
        app.ask(self.state, {'message': 'who can get it?'})
        del self.state['help_last_faq']
        self.contextual('Who can get it, exactly?')
        result = app.ask(self.state, {'message': 'and exactly?'})
        self.assertEqual(result['status'], 'faq_no_match')
        self.assertTrue(result['same_faq'])

    def test_related_click_stores_the_title_as_what_was_said(self):
        self.dcr.api = single('FAQ_21', 'How old can a child be?')
        with patch.object(app, 'faq_titles', return_value={'FAQ_21': 'How old can a child be?'}):
            app.ask(self.state, {'related': 'FAQ_21'})
        self.assertEqual(json.loads(self.writes()[-1])['faqs'], [{'id': 'FAQ_21', 'said': 'How old can a child be?'}])

    def test_the_rewrite_is_stored_as_asked(self):
        self.dcr.api = single()
        app.ask(self.state, {'message': 'who can get it?'})
        self.dcr.api = single('FAQ_21', 'Q2?')
        self.contextual('How old can a child be?')
        app.ask(self.state, {'message': 'how old?'})
        newest = json.loads(self.writes()[-1])['faqs'][0]
        self.assertEqual(newest, {'id': 'FAQ_21', 'said': 'how old?', 'asked': 'How old can a child be?'})


if __name__ == '__main__':
    unittest.main()
