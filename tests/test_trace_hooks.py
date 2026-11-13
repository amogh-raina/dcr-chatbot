"""Hooks that feed the turn record: model calls and DCR events (spec 02, T4). No model call, no network."""
import json
import os
import unittest
from unittest.mock import Mock, patch

import dcrai.dcr.dcr_repository as repo
import dcrai.llm.retrieval_llm as llm
import dcrai.observability.turn_trace as tt
from dcrai import registry
from dcrai.llm import openchat
from tests.test_turn_trace import TraceCase

Q1 = {'type': 'predicate', 'name': 'q1', 'instructions': 'First?'}
Q2 = {'type': 'predicate', 'name': 'q2', 'instructions': 'Second?'}


class Http:
    def __init__(self, answers=None, status=200, error=None, bad_json=False):
        self.answers, self.status, self.error, self.bad_json, self.sent = answers, status, error, bad_json, None

    def post(self, url, **kwargs):
        self.sent = kwargs['json']
        if self.error:
            raise self.error

        def body():
            if self.bad_json:
                raise ValueError('not json')
            return {'answers': self.answers}
        return Mock(status_code=self.status, json=body)


class Client:
    """Responses stub: each create() returns the next output (a dict, or a string for unparsable text)."""

    def __init__(self, *outputs):
        self.outputs, self.responses, self.calls = list(outputs), self, 0

    def create(self, **kwargs):
        self.calls += 1
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        text = out if isinstance(out, str) else json.dumps(out)
        return type('R', (), {'status': 'completed', 'output_text': text})()


class HookCase(TraceCase):
    def setUp(self):
        super().setUp()
        patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test-123'}).start()
        self.state = self.started(interface='chat')

    def traced(self, fn):
        """Run fn(state) as one traced request; return (turn line, fn's exception or None)."""
        failure = []

        @tt.turn('chat')
        def request(state, data):
            try:
                fn()
            except Exception as error:      # the hooks must record failures and still let them propagate
                failure.append(error)
            return {}
        request(self.state, {'message': 'm'})
        return self.lines(self.state, 'turn')[-1], (failure[0] if failure else None)


class DecisionsCallTests(HookCase):
    ANSWERS = [{'name': 'q1', 'type': 'predicate', 'probability': 0.9},
               {'name': 'q2', 'type': 'predicate', 'probability': 0.1}]

    def test_decisions_call_is_recorded(self):
        http = Http(self.ANSWERS)
        row, error = self.traced(lambda: llm._decide('E', [Q1, Q2], http))
        self.assertIsNone(error)
        call = row['calls'][0]
        self.assertEqual((call['api'], call['name'], call['input'], call['status']), ('decisions', 'q1+q2', 'E', 'ok'))
        self.assertEqual(call['model'], 'gpt-6-luna')
        self.assertEqual(call['questions'], http.sent['questions'])
        self.assertEqual(call['output'], {a['name']: a for a in self.ANSWERS})
        self.assertIsInstance(call['latency_s'], float)
        self.assertNotIn('error', call)
        self.assertNotIn('sk-test-123', json.dumps(row))

    def test_decisions_http_error_is_recorded_and_still_raises(self):
        row, error = self.traced(lambda: llm._decide('E', [Q1], Http(status=500)))
        self.assertIsInstance(error, llm.LLMError)
        self.assertEqual(str(error), 'Decisions returned 500')
        call = row['calls'][0]
        self.assertEqual((call['status'], call['error'], call['name']), ('error', 'Decisions returned 500', 'q1'))
        self.assertNotIn('output', call)

    def test_decisions_transport_failure_is_recorded(self):
        row, error = self.traced(lambda: llm._decide('E', [Q1], Http(error=TimeoutError('slow'))))
        self.assertIsInstance(error, llm.LLMError)
        self.assertEqual(row['calls'][0]['error'], 'Decisions request failed: TimeoutError')

    def test_decisions_invalid_json_and_refusal_are_recorded(self):
        row, error = self.traced(lambda: llm._decide('E', [Q1], Http(bad_json=True)))
        self.assertEqual((row['calls'][0]['status'], row['calls'][0]['error']),
                         ('invalid', 'Decisions returned invalid JSON'))
        refusal = [{'name': 'q1', 'type': 'refusal'}]
        row, error = self.traced(lambda: llm._decide('E', [Q1], Http(refusal)))
        self.assertIsInstance(error, llm.LLMError)
        self.assertEqual(row['calls'][0]['status'], 'refusal')
        self.assertEqual(row['calls'][0]['output'], {'q1': refusal[0]})

    def test_a_caller_error_after_the_call_does_not_duplicate_the_record(self):
        row, _ = self.traced(lambda: llm._decide('E', [Q1, Q2], Http(self.ANSWERS)))
        self.assertEqual(len(row['calls']), 1)

    def test_missing_key_is_not_a_call(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            row, error = self.traced(lambda: llm._decide('E', [Q1], Http(self.ANSWERS)))
        self.assertIsInstance(error, llm.LLMError)
        self.assertNotIn('calls', row)

    def test_no_record_outside_a_request(self):
        http = Http(self.ANSWERS)
        self.assertEqual(set(llm._decide('E', [Q1, Q2], http)), {'q1', 'q2'})
        with self.assertRaises(llm.LLMError):
            llm._decide('E', [Q1], Http(status=500))
        self.assertEqual(self.lines(self.state, 'turn'), [])
        self.assertEqual(llm.rewrite('m', {}, client=Client({'search_query': 'x'}), settings=openchat.Settings()), 'x')

    def test_request_body_is_unchanged_by_tracing(self):
        http = Http(self.ANSWERS)
        self.traced(lambda: llm._decide('E', [Q1, Q2], http))
        self.assertEqual(http.sent, {'model': 'gpt-6-luna', 'input': 'E', 'questions': [Q1, Q2]})


class ResponsesCallTests(HookCase):
    def test_responses_call_is_recorded_with_attempts(self):
        client = Client({'search_query': 'Standalone question?'})
        row, error = self.traced(lambda: llm.rewrite('and the hours?', {'last_answered_faq': 'FAQ_1'}, client=client,
                                                     settings=openchat.Settings()))
        self.assertIsNone(error)
        call = row['calls'][0]
        self.assertEqual((call['api'], call['name'], call['status'], call['attempts']),
                         ('responses', 'query_rewrite', 'ok', 1))
        self.assertEqual(call['instructions'], llm.REWRITE_PROMPT)
        self.assertEqual(call['input'], {'message': 'and the hours?', 'context': {'last_answered_faq': 'FAQ_1'}})
        self.assertEqual(call['output'], {'search_query': 'Standalone question?'})
        self.assertEqual(call['model'], openchat.Settings().model)
        self.assertEqual(row['rewrite'], {'from': 'and the hours?', 'text': 'Standalone question?', 'call': 0})

    def test_a_retry_after_invalid_output_is_one_record_with_two_attempts(self):
        client = Client('not json', {'search_query': 'ok?'})
        row, error = self.traced(lambda: llm.rewrite('m', {}, client=client, settings=openchat.Settings()))
        self.assertIsNone(error)
        self.assertEqual(client.calls, 2)
        self.assertEqual([(c['status'], c['attempts']) for c in row['calls']], [('ok', 2)])

    def test_two_invalid_outputs_are_recorded_as_invalid(self):
        client = Client('nope', 'still nope')
        row, error = self.traced(lambda: llm.rewrite('m', {}, client=client, settings=openchat.Settings()))
        self.assertIsInstance(error, llm.LLMError)
        call = row['calls'][0]
        self.assertEqual((call['status'], call['attempts'], call['error']),
                         ('invalid', 2, 'query_rewrite returned invalid output'))

    def test_a_provider_failure_is_recorded_as_error(self):
        client = Client(RuntimeError('503 upstream detail'))
        row, error = self.traced(lambda: llm.rewrite('m', {}, client=client, settings=openchat.Settings()))
        self.assertIsInstance(error, llm.LLMError)
        call = row['calls'][0]
        self.assertEqual((call['status'], call['error']), ('error', 'query_rewrite is temporarily unavailable'))
        self.assertNotIn('upstream detail', json.dumps(row))

    def test_the_payload_is_copied_at_call_time(self):
        payload_context = {'last_answered_faq': 'FAQ_1'}
        client = Client({'search_query': 'q?'})

        def run():
            llm.rewrite('m', payload_context, client=client, settings=openchat.Settings())
            payload_context['last_answered_faq'] = 'changed afterwards'
        row, _ = self.traced(run)
        self.assertEqual(row['calls'][0]['input']['context'], {'last_answered_faq': 'FAQ_1'})


class DcrEventTests(HookCase):
    def setUp(self):
        super().setUp()
        self.dcr_state = {'root_url': 'https://dcr.test/', 'graph_id': '5', 'simulation_id': 9, 'api_key': 'k'}

    def test_dcr_event_is_recorded(self):
        post = Mock(return_value=Mock(status_code=204, text=''))
        with patch.object(repo._session, 'post', post):
            row, _ = self.traced(lambda: self.assertTrue(
                repo.execute_raw_event(self.dcr_state, 'FAQ_Triage', '1', 'why')))
        event = row['dcr_events'][0]
        self.assertEqual((event['id'], event['value'], event['comment'], event['ok']), ('FAQ_Triage', '1', 'why', True))
        self.assertRegex(event['at'], r'^\d{4}-\d\d-\d\dT')
        self.assertIsInstance(event['latency_s'], float)
        self.assertEqual(post.call_args.kwargs['json']['eventId'], 'FAQ_Triage')   # the request itself is unchanged

    def test_failed_dcr_execute_is_recorded_as_not_ok(self):
        post = Mock(return_value=Mock(status_code=500, text='boom'))
        with patch.object(repo._session, 'post', post):
            row, _ = self.traced(lambda: self.assertFalse(
                repo.execute_raw_event(self.dcr_state, 'FAQ_Triage', '1', 'why')))
        self.assertIs(row['dcr_events'][0]['ok'], False)

    def test_a_transport_error_is_recorded_and_still_raises(self):
        post = Mock(side_effect=ConnectionError('down'))
        with patch.object(repo._session, 'post', post):
            row, error = self.traced(lambda: repo.execute_raw_event(self.dcr_state, 'FAQ_UserQuestion', 'Q', ''))
        self.assertIsInstance(error, ConnectionError)
        self.assertIs(row['dcr_events'][0]['ok'], False)

    def test_events_keep_their_order(self):
        post = Mock(return_value=Mock(status_code=204, text=''))

        def run():
            for event_id in ('FAQ_Triage', 'FAQ_UserQuestion', 'FAQ_Answered'):
                repo.execute_raw_event(self.dcr_state, event_id, 'v', '')
        with patch.object(repo._session, 'post', post):
            row, _ = self.traced(run)
        self.assertEqual([e['id'] for e in row['dcr_events']], ['FAQ_Triage', 'FAQ_UserQuestion', 'FAQ_Answered'])

    def test_no_record_outside_a_request(self):
        post = Mock(return_value=Mock(status_code=204, text=''))
        with patch.object(repo._session, 'post', post):
            self.assertTrue(repo.execute_raw_event(self.dcr_state, 'FAQ_Triage', '1', 'why'))
        self.assertEqual(self.lines(self.state, 'turn'), [])

    def test_execute_event_goes_through_the_same_hook(self):
        post = Mock(return_value=Mock(status_code=204, text=''))
        with patch.object(repo._session, 'post', post):
            row, _ = self.traced(lambda: repo.execute_event(self.dcr_state, 'FAQ_Triage', '1', 'why'))
        self.assertEqual(len(row['dcr_events']), 1)


# ------------------------------------------------------------------ T5: the real entry points
import dcrai.application.application_runtime as app
import dcrai.chat.retrieval_runtime as rt
from tests.test_retrieval_runtime import FakeDCR, clarify, patch_tiers, single

ORIGINAL_TIERS_DECISIONS = llm.relevance_tiers_decisions     # the test modules patch it in setUp


class RealEntryCase(TraceCase):
    """Chat or panel against the fake DCR, with the interaction log on."""
    interface = 'chat'

    def setUp(self):
        super().setUp()
        self.dcr = FakeDCR()
        self.state = {'graph_id': 1, 'simulation_id': 2, 'graph_xml': '<dcrgraph/>'}
        patch.object(rt.repo, 'get_raw_events', side_effect=self.dcr.read).start()
        patch.object(rt.repo, 'execute_raw_event', side_effect=self.dcr.execute).start()
        patch.object(llm, 'decisions_enabled', return_value=False).start()
        patch.object(llm, 'relevant', side_effect=lambda m, c, **k: [x['id'] for x in c]).start()
        patch_tiers()
        patch.object(llm, 'pick_followup', return_value=None).start()
        patch.object(llm, 'triage', return_value=dict(value='1', reply_value=None, search_query=None, reason='r')).start()
        patch.object(llm, 'route', return_value=('new_question', None)).start()

    def begin(self, interface):
        ilog.start(self.state, '1', '2', interface=interface)
        self.state['interaction']['shown'] = {}

    def turn_lines(self):
        return self.lines(self.state, 'turn')


import dcrai.observability.interaction_log as ilog


class ChatEntryTests(RealEntryCase):
    def setUp(self):
        super().setUp()
        rt.initialize(self.state, self.dcr.read(self.state))
        self.begin('chat')

    def test_chat_request_writes_one_turn_line(self):
        self.dcr.api = single()
        result = rt.handle(self.state, {'message': 'who can get it?'})
        rows = self.turn_lines()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['turn'], row['interface'], row['entry'], row['message']), (1, 'chat', 'message', 'who can get it?'))
        self.assertEqual(row['status'], result['status'])
        self.assertEqual(len(row['searches']), 1)
        self.assertEqual(row['searches'][0]['query'], 'who can get it?')
        self.assertEqual(row['registry_version'], registry.version())
        self.assertEqual(row['graph_revision'], self.state['interaction']['graph_revision'])
        self.assertEqual(row['outcome'], 'answer')
        self.assertEqual(row['outcome_row'], 4)
        self.assertEqual(row['faq_ids'], ['FAQ_31'])
        self.assertEqual(row['context'], {'last_answered_faq': None, 'last_followup': None})
        self.assertEqual(self.state['turn'], 1)

    def test_one_increment_per_request_for_every_entry(self):
        self.dcr.api = clarify()
        options = rt.handle(self.state, {'message': 'medical docs'})
        rt.handle(self.state, {'action': 'reply', 'retrieval_prompt_id': options['prompt']['id'], 'value': 'none'})
        self.dcr.api = single()
        rt.handle(self.state, {'action': 'example', 'faq_id': 'FAQ_01'})
        rt.handle(self.state, {'action': 'rephrase'})
        self.assertEqual(self.state['turn'], 4)
        self.assertEqual([r['turn'] for r in self.turn_lines()], [1, 2, 3, 4])
        self.assertEqual([r['entry'] for r in self.turn_lines()], ['message', 'reply', 'example', 'rephrase'])

    def test_reply_to_a_prompt_sets_reacts_to(self):
        self.dcr.api = clarify()
        options = rt.handle(self.state, {'message': 'medical docs'})
        rt.handle(self.state, {'action': 'reply', 'retrieval_prompt_id': options['prompt']['id'], 'value': 'none'})
        first, second = self.turn_lines()
        self.assertNotIn('reacts_to', first)
        self.assertEqual(second['reacts_to'], 1)
        self.assertEqual(second['input_value'], 'none')

    def test_a_rejected_request_is_a_turn_with_an_error(self):
        with self.assertRaises(rt.StateError):
            rt.handle(self.state, {'action': 'reply', 'retrieval_prompt_id': 'stale', 'value': '1'})
        self.assertEqual(self.turn_lines()[0]['error'], 'StateError')

    def test_search_record_for_a_clarify_result(self):
        self.dcr.api = dict(clarify(), score=0.83, option1_score=0.83, option2_score=0.71, option3_score=0.6)
        rt.handle(self.state, {'message': 'medical docs'})
        record = self.turn_lines()[0]['searches'][0]
        self.assertEqual((record['decision'], record['top_score'], record['status']), ('clarify_match', 0.83, 'found'))
        self.assertEqual(record['option_scores'], {'FAQ_11': 0.83, 'FAQ_21': 0.71, 'FAQ_99': 0.6})
        self.assertEqual(record['retrieved'], ['FAQ_11', 'FAQ_21', 'FAQ_99'])
        self.assertEqual(record['kept'], ['FAQ_11', 'FAQ_21', 'FAQ_99'])
        self.assertEqual(record['judge'], 'medical docs')
        self.assertNotIn('how', record)

    def test_search_record_for_a_single_match_has_no_option_scores(self):
        self.dcr.api = dict(single(), score=0.95)
        rt.handle(self.state, {'message': 'who can get it?'})
        record = self.turn_lines()[0]['searches'][0]
        self.assertEqual((record['decision'], record['top_score']), ('single_match', 0.95))
        self.assertNotIn('option_scores', record)
        self.assertEqual(record['retrieved'], ['FAQ_31'])

    def test_search_record_for_no_match(self):
        self.dcr.api = dict(decision='no_match')
        rt.handle(self.state, {'message': 'weather in Rome'})
        record = self.turn_lines()[0]['searches'][0]
        self.assertEqual((record['status'], record['decision'], record['retrieved'], record['kept']),
                         ('no_match', 'no_match', [], []))

    def test_search_record_reads_tiers_when_present(self):
        self.dcr.api = clarify()
        with patch.object(llm, 'relevance_tiers', return_value={'answers': ['FAQ_21'], 'related': ['FAQ_11']}):
            rt.handle(self.state, {'message': 'medical docs'})
        record = self.turn_lines()[0]['searches'][0]
        self.assertEqual(record['tiers'], {'FAQ_21': 'answers', 'FAQ_11': 'related'})
        self.assertEqual(record['kept'], ['FAQ_21', 'FAQ_11'])

    def test_search_record_when_the_search_is_unavailable(self):
        self.dcr.api = None
        rt.handle(self.state, {'message': 'who can get it?'})
        record = self.turn_lines()[0]['searches'][0]
        self.assertEqual(record['status'], 'unavailable')
        for key in ('decision', 'retrieved', 'kept'):
            self.assertNotIn(key, record)

    def test_search_record_maps_decisions_probabilities_to_candidates(self):
        probabilities = {'answers_0': 0.9, 'topic_0': 0.95, 'answers_1': 0.1, 'topic_1': 0.7,
                         'answers_2': 0.8, 'topic_2': 0.2}

        def post(url, **kwargs):
            names = [q['name'] for q in kwargs['json']['questions']]
            answers = [{'name': n, 'type': 'predicate', 'probability': probabilities[n]} for n in names]
            return Mock(status_code=200, json=lambda: {'answers': answers})
        self.dcr.api = clarify()
        patch.object(llm, 'decisions_enabled', return_value=True).start()
        patch.object(llm, 'relevance_tiers_decisions', ORIGINAL_TIERS_DECISIONS).start()
        patch.dict(os.environ, {'OPENAI_API_KEY': 'k'}).start()
        patch('requests.post', side_effect=post).start()

        self.dcr.execute(self.state, 'FAQ_Triage', '1')

        @tt.turn('chat')
        def request(state, data):
            return {'result': rt.search(state, 'medical docs')}
        request(self.state, {'message': 'medical docs'})
        record = self.turn_lines()[0]['searches'][0]
        self.assertEqual(record['relevance'], {'FAQ_11': {'answers': 0.9, 'topic': 0.95},
                                               'FAQ_21': {'answers': 0.1, 'topic': 0.7},
                                               'FAQ_99': {'answers': 0.8, 'topic': 0.2}})
        self.assertEqual(record['tiers'], {'FAQ_11': 'answers', 'FAQ_99': 'answers', 'FAQ_21': 'related'})
        call = self.turn_lines()[0]['calls'][0]
        self.assertEqual(call['name'], 'answers_0+topic_0+answers_1+topic_1+answers_2+topic_2')

    def test_search_outside_a_request_is_untouched(self):
        self.dcr.api = single()
        self.dcr.execute(self.state, 'FAQ_Triage', '1')
        status, found, _ = rt.search(self.state, 'who can get it?')
        self.assertEqual((status, [c['id'] for c in found]), ('found', ['FAQ_31']))
        self.assertEqual(self.turn_lines(), [])


class PanelEntryTests(RealEntryCase):
    def setUp(self):
        super().setUp()
        self.dcr.events['Form0:Email'].update(included=True, enabled=True)
        app.start(self.state)
        self.begin('panel')

    def test_panel_ask_and_confirm_write_one_line_each(self):
        self.dcr.api = clarify()
        result = app.ask(self.state, {'message': 'medical docs', 'scope': 'field'})
        self.assertEqual(result['status'], 'faq_clarify')
        app.confirm(self.state, {'match_id': result['match_id'], 'candidate_key': 'FAQ_21'})
        first, second = self.turn_lines()
        self.assertEqual((first['turn'], first['entry'], first['interface'], first['status']),
                         (1, 'message', 'panel', 'faq_clarify'))
        self.assertEqual((second['turn'], second['entry'], second['input_value']), (2, 'confirm', 'FAQ_21'))
        for row in (first, second):
            self.assertEqual(row['registry_version'], registry.version())
            self.assertEqual(row['graph_revision'], self.state['interaction']['graph_revision'])
        self.assertEqual(first['context'], {'faq_ids': [], 'field': 'Form0:Email', 'source': 'session'})
        self.assertEqual(self.state['turn'], 2)

    def test_panel_search_records_how_each_step_was_tried(self):
        self.dcr.api = dict(decision='no_match')
        app.ask(self.state, {'message': 'medical docs', 'scope': 'field'})
        hows = [s.get('how') for s in self.turn_lines()[0]['searches']]
        self.assertEqual(hows, ['field-typed', 'field-composed'])
        self.assertEqual(self.turn_lines()[0]['searches'][1]['query'], 'Your email? medical docs')
        self.assertEqual(self.turn_lines()[0]['searches'][1]['judge'], 'medical docs')

    def test_panel_confirm_after_prompt_sets_reacts_to(self):
        self.dcr.api = clarify()
        result = app.ask(self.state, {'message': 'medical docs'})
        app.confirm(self.state, {'match_id': result['match_id'], 'candidate_key': 'none'})
        first, second = self.turn_lines()
        self.assertNotIn('reacts_to', first)
        self.assertEqual(second['reacts_to'], 1)
        self.assertEqual(second['status'], 'faq_none')

    def test_related_click_records_the_title_as_the_message(self):
        self.dcr.api = single('FAQ_21', 'How old can a child be?')
        with patch.object(app, 'faq_titles', return_value={'FAQ_21': 'How old can a child be for the supplement?'}):
            app.ask(self.state, {'related': 'FAQ_21'})
        row = self.turn_lines()[0]
        self.assertEqual((row['entry'], row['input_value'], row['message']),
                         ('related', 'FAQ_21', 'How old can a child be for the supplement?'))

    def test_a_refused_question_is_a_turn_with_an_error(self):
        with self.assertRaises(app.ApplicationError):
            app.ask(self.state, {'message': ''})
        row = self.turn_lines()[0]
        self.assertEqual(row['error'], 'ApplicationError')
        self.assertEqual(row['message'], '')      # what the applicant sent, verbatim

    def test_handover_reason_is_copied(self):
        self.dcr.events['Help_Escalate'] = dict(id='Help_Escalate', roles='Chatbot', dataType='choice', tags='FAQEscalation',
                                                included=True, enabled=True, pending=False, executed=None, value='',
                                                label='Hand over?', description='', choiceValues='Asked (1)', sequence=0)
        self.dcr.events['Help_Handover'] = dict(id='Help_Handover', roles='Chatbot', dataType='label', tags='FAQHandover',
                                                included=True, enabled=True, pending=False, executed=None, value='',
                                                label='Talk to a person', description='<p>Call SU.</p>', sequence=0)
        original = self.dcr.execute

        def execute(state, eid, value, comment='', role=None):
            ok = original(state, eid, value, comment, role)
            if eid == 'Help_Escalate':
                self.dcr.events['Help_Handover']['pending'] = True
            return ok
        rt.repo.execute_raw_event.side_effect = execute
        self.dcr.api = single()
        result = app.ask(self.state, {'message': 'I want to talk to a real person'})
        self.assertEqual(result['status'], 'handover')
        self.assertEqual(self.turn_lines()[0]['handover'], {'reason': 1})


if __name__ == '__main__':
    unittest.main()
