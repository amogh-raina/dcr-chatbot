"""Regressions found while reviewing the retrieval branch against main."""
import json
import os
import socket
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from dcrai.application import application_runtime
from dcrai.observability import turn_trace
from faq_search.api import build_payload
from tests import test_retrieval_runtime as fixture


class CitationRoundtripTests(unittest.TestCase):
    def test_citation_survives_api_payload_and_user_selection(self):
        for count in (1, 2):
            with self.subTest(candidates=count):
                case = fixture.RetrievalRuntimeTests()
                case.setUp()
                try:
                    results = [SimpleNamespace(id=f'FAQ_{n}', canonical_question=f'Question {n}?',
                                               answer_text=f'Answer {n}.', citation=f'Source section {n}', score=0.7)
                               for n in (21, 11)[:count]]
                    case.dcr.api = build_payload('clarify_match', results, SimpleNamespace(maximum=3))
                    prompt = case.send(message='a documentation question')
                    answer = case.reply(prompt, 'FAQ_21')
                    self.assertEqual(answer['answer']['citation'], 'Source section 21')
                finally:
                    case.doCleanups()


class OfflineTestIsolationTests(unittest.TestCase):
    @unittest.skipIf(os.getenv('RUN_RETRIEVAL_EVAL') == '1', 'integration tests allow model downloads')
    def test_fixture_cleanup_does_not_remove_the_suite_network_guard(self):
        with patch('socket.socket.connect', return_value=None):
            pass
        patch.stopall()
        with socket.socket() as connection:
            with self.assertRaisesRegex(RuntimeError, 'Network disabled in unit tests'):
                connection.connect(('127.0.0.1', 1))


class PanelTraceTests(unittest.TestCase):
    def test_trace_reads_the_active_surface_and_supports_older_graphs(self):
        payload = {'events': [
            dict(id='FAQ_RetrievalOk', executed=True, value=json.dumps({'score': 0.1})),
            dict(id='Help_RetrievalOk', executed=True, value=json.dumps({'score': 0.9})),
        ]}
        for application, split, expected in ((True, True, 0.9), (True, False, 0.1), (False, True, 0.1)):
            with self.subTest(application=application, split=split):
                state = dict(simulation_state=payload, panel_search=split)
                if application:
                    state['application_answers'] = []
                self.assertEqual(turn_trace._retrieval_payload(state)['score'], expected)


class SessionConcurrencyTests(unittest.TestCase):
    def exercise(self, second_sid):
        app = Flask(__name__)
        store = {sid: {'application_answers': []} for sid in ('first', 'second')}
        application_runtime.install(app, store, lambda: {})
        entered, released, second_entered = threading.Event(), threading.Event(), threading.Event()
        responses = {}

        def ask(state, data):
            if data['message'] == 'slow':
                entered.set()
                if not released.wait(5):
                    raise RuntimeError('test did not release request')
            else:
                second_entered.set()
            return {'status': 'answer'}

        def send(sid, message):
            with app.test_client() as client:
                response = client.post('/application/ask', json={'message': message}, headers={'X-Session-ID': sid})
                responses[message] = response.status_code

        first = threading.Thread(target=send, args=('first', 'slow'), daemon=True)
        second = threading.Thread(target=send, args=(second_sid, 'fast'), daemon=True)
        with patch.object(application_runtime, 'ask', side_effect=ask):
            try:
                first.start()
                self.assertTrue(entered.wait(2), 'first request never entered the application')
                second.start()
                if second_sid == 'first':
                    self.assertFalse(second_entered.wait(0.1), 'same-session operations overlapped')
                else:
                    self.assertTrue(second_entered.wait(2), 'one session blocked another session')
            finally:
                released.set()
                first.join(3)
                if second.ident is not None:
                    second.join(3)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(responses, {'slow': 200, 'fast': 200})

    def test_a_slow_session_does_not_block_another_session(self):
        self.exercise('second')

    def test_requests_in_the_same_session_are_serialized(self):
        self.exercise('first')


if __name__ == '__main__':
    unittest.main()
