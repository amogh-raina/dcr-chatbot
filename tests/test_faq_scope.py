"""Scope gating checks with controlled provider outputs; not live LLM accuracy tests."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import openchat
import faq_runtime as faq

PAIR = {'candidate_key': 'global:1', 'event_id': 'global', 'value': '1',
        'question': 'How do I apply?'}
MATCH = {'candidate_key': 'global:1', 'score': .92, 'reason': 'Application instructions'}

class ScopeTests(unittest.TestCase):
    def client(self, in_scope, rows):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(status='completed', usage=None,
            output_text=json.dumps(dict(in_scope=in_scope, scope_reason='Current message relevance', ranked_matches=rows)))
        return client

    def test_scope_rejection_overrides_high_score(self):
        for rows in ([], [MATCH]):
            client = self.client(False, rows)
            self.assertEqual(openchat.rank('i want to take a shit', 'How do I apply?', [PAIR], client), ('no_match', []))
            schema = client.responses.create.call_args.kwargs['text']['format']['schema']
            self.assertEqual(schema['properties']['ranked_matches']['minItems'], 0)
            self.assertIn('in_scope', schema['required'])
            self.assertEqual(client.responses.create.call_count, 1)

    def test_relevant_follow_up_keeps_existing_ranking(self):
        result = openchat.rank('Where do I submit that?', 'How do I apply?', [PAIR], self.client(True, [MATCH]))
        self.assertEqual(result, ('single_match', [MATCH]))

    def test_invalid_scope_is_not_accepted(self):
        for flag in ('false', None, 1):
            raw = dict(in_scope=flag, scope_reason='Unrelated', ranked_matches=[MATCH])
            with self.assertRaises(openchat.MatchError):
                openchat.validate_ranking(raw, {'global:1'})
        with self.assertRaises(openchat.MatchError):
            openchat.validate_ranking({'ranked_matches': [MATCH]}, {'global:1'})

    def test_no_match_leaves_dcr_untouched(self):
        payload = {'events': [
            dict(id='home', label='Choose a topic', tags='FAQHome,FAQTopicMenu',
                 dataType='choice', included=True, enabled=True, pending=True, choiceValues='Applying (1)'),
            dict(id='global', label='Ask a question', tags='GlobalInterpreter',
                 dataType='choice', included=True, enabled=True, pending=False, choiceValues='How do I apply? (1)')]}
        real_rank = openchat.rank
        client = self.client(False, [MATCH])
        with patch.object(faq.repo, 'get_raw_events', return_value=payload), \
             patch.object(faq.repo, 'execute_event') as execute, \
             patch.object(openchat, 'rank', side_effect=lambda m, q, c: real_rank(m, q, c, client)):
            result = faq.handle({'last_confirmed_question': 'How do I apply?'}, {'message': 'i want to take a shit'})
        self.assertEqual(result['status'], 'no_match')
        self.assertIn('SU disability supplement', result['response'])
        execute.assert_not_called()

if __name__ == '__main__':
    unittest.main()
