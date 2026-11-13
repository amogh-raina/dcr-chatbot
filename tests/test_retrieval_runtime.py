"""Retrieval chat flow against a fake DCR (Clean retrieval graph shape) and a fake LLM."""
import copy
import json
import unittest
from unittest.mock import patch

import dcrai.llm.retrieval_llm as llm
import dcrai.chat.retrieval_runtime as rt
from dcrai.chat.faq_runtime import StateError

SEL = 'FAQ_DeterminationSelector'
ITEMS = [("Can I get handicaptillæg if I'm not a Danish citizen?", '1'),
         ('How long does a condition need to have lasted before it counts as permanent?', '2'),
         ('When will my application be refused outright, without the Agency assessing the substance of my case?', '3'),
         ('What if I miss the 4-week deadline for appealing?', '4')]
DETS = {'1': 'Det05b', '2': 'Det09', '3': 'Det31', '4': 'Det42'}


def ev(eid, roles='Chatbot', dtype='label', tags='', included=True, description='', label=None, choice=''):
    return dict(id=eid, roles=roles, dataType=dtype, tags=tags, included=included, enabled=included,
                pending=False, executed=None, value='', label=label or eid, description=description,
                choiceValues=choice, sequence=0)


class FakeDCR:
    def __init__(self):
        e = [ev('FAQ_UserQuestion', dtype='text', tags='FAQRetrieval', included=False),
             ev('FAQ_Triage', dtype='choice', tags='FAQTriage', description='<p>Triage policy text.</p>',
                choice='New question (1), Reply (2), End (4), Out of scope (5)'),
             ev('FAQ_Answered', dtype='text', tags='FAQContext'),
             ev('FAQ_Retrieve', roles='Robot', dtype='text', tags='FAQRetrieval'),
             ev('FAQ_RetrievalOk', roles='System', dtype='text', tags='FAQRetrieval'),
             ev('FAQ_RetrievalUnavailable', tags='FAQAnswer,FAQRetrieval', description='<p>Search down.</p>'),
             ev(SEL, dtype='choice', tags='GlobalInterpreter',
                choice=', '.join(f'{label} ({value})' for label, value in ITEMS)),
             ev('FAQ_Scope', tags='FAQScope', description='<p>I answer handicaptillæg questions.</p>'),
             ev('FAQ_OutOfScope', tags='FAQOutOfScope', description='<p>Outside scope.</p>'),
             ev('FAQ_NoMatch', tags='FAQNoMatch', description='<p>No FAQ fits.</p>'),
             ev('FAQ_Goodbye', tags='FAQGoodbye', description='<p>Goodbye.</p>'),
             ev('Form0:Email', roles='', dtype='email', included=False, label='Your email?'),
             ev('Form0:Complete', roles='', tags='ApplicationComplete', included=False, label='Sent.')]
        for n, (prefix) in enumerate(DETS.values(), start=1):
            e.append(dict(ev(f'{prefix}_Ask', dtype='choice', tags='FAQDetermination', included=False,
                             label=f'Ask {prefix}?', choice='Yes (true), No (false)'), sequence=100 + n))
            e.append(ev(f'{prefix}_Yes', tags='FAQAnswer,DeterminationResult', description=f'<p>{prefix} yes.</p>'))
            e.append(ev(f'{prefix}_No', tags='FAQAnswer,DeterminationResult', description=f'<p>{prefix} no.</p>'))
        self.events = {x['id']: x for x in e}
        self.api = None
        self.executed = []
        self.comments = {}
        self.with_triage = True

    def read(self, state):
        payload = {'events': copy.deepcopy(list(self.events.values()))}
        rt.repo._remember_roles(state, payload)
        return payload

    def drop_triage(self):
        del self.events['FAQ_Triage']
        self.events['FAQ_UserQuestion'].update(included=True, enabled=True)

    def execute(self, state, eid, value, comment='', role=None):
        e = self.events[eid]
        if not e['enabled']:
            return False
        self.executed.append((eid, value))
        self.comments[eid] = comment
        self.clock = getattr(self, 'clock', 0) + 1
        e.update(executed=f't{self.clock:04d}', pending=False, value=value)
        if eid == 'FAQ_Triage':
            self.events['FAQ_UserQuestion'].update(included=value == '1', enabled=value == '1')
            if value == '5':
                self.events['FAQ_OutOfScope']['pending'] = True
            if value == '4':
                self.events['FAQ_Goodbye']['pending'] = True
        elif eid == 'FAQ_UserQuestion':
            if self.api is None:
                self.events['FAQ_RetrievalUnavailable']['pending'] = True
            else:
                self.events['FAQ_RetrievalOk'].update(executed='now', value=json.dumps(json.dumps(self.api)))
        elif eid == SEL:
            for v, prefix in DETS.items():
                ask = self.events[f'{prefix}_Ask']
                on = value == v
                ask.update(included=on, enabled=on, pending=on)
        elif eid == 'Form0:Email':
            self.events['Form0:Complete'].update(included=True, enabled=True, pending=True)
        elif eid.endswith('_Ask'):
            prefix = eid[:-4]
            self.events[f'{prefix}_Yes' if value == 'true' else f'{prefix}_No']['pending'] = True
        return True


def patch_tiers():
    """Fakes for the two-judgement relevance check that delegate to the (patched) single checks: whatever those keep
    'answers it', nothing is 'same topic only'. A test that needs a tier overrides the returned mock's side_effect."""
    plain = patch.object(llm, 'relevance_tiers', side_effect=lambda m, c, **k: {'answers': llm.relevant(m, c),
                                                                               'related': []}).start()
    decisions = patch.object(llm, 'relevance_tiers_decisions',
                             side_effect=lambda m, c, **k: {'answers': llm.relevant_decisions(m, c),
                                                            'related': []}).start()
    return plain, decisions


def single(fid='FAQ_31', question=ITEMS[2][0]):
    return dict(decision='single_match', id=fid, question=question, answer='Para one.\n\nPara two.', citation='§ 37')


def clarify():
    d = dict(decision='clarify_match', id='', question='', answer='', citation='')
    for n, fid in enumerate(['FAQ_11', 'FAQ_21', 'FAQ_99'], start=1):
        d.update({f'option{n}_id': fid, f'option{n}_question': f'Question {fid}?', f'option{n}_answer': f'Answer {fid}.'})
    return d


class RetrievalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.dcr = FakeDCR()
        self.state = {'graph_id': 1, 'simulation_id': 2}
        patch.object(rt.repo, 'get_raw_events', side_effect=self.dcr.read).start()
        patch.object(rt.repo, 'execute_raw_event', side_effect=self.dcr.execute).start()
        self.route = patch.object(llm, 'route', return_value=('new_question', None)).start()
        self.triage = patch.object(llm, 'triage', return_value=self.decision('1')).start()
        self.relevant = patch.object(llm, 'relevant', side_effect=lambda m, c, **k: [x['id'] for x in c]).start()
        self.tiers, _ = patch_tiers()
        self.pick = patch.object(llm, 'pick_followup', return_value=None).start()
        self.addCleanup(patch.stopall)
        self.surface = patch.dict('os.environ', {'FOLLOWUP_SURFACE': 'chat'})   # the old chat behaviour; the panel default is tested apart
        self.surface.start()
        self.addCleanup(self.surface.stop)
        self.welcome = rt.initialize(self.state, self.dcr.read(self.state))

    @staticmethod
    def decision(value, reply=None, query=None):
        return dict(value=value, reply_value=reply, search_query=query, reason='because')

    def send(self, **data):
        return rt.handle(self.state, data)

    def reply(self, result, value):
        return self.send(action='reply', retrieval_prompt_id=result['prompt']['id'], value=value)

    def test_flag_reads_the_environment_at_call_time(self):
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('PANEL_FALLBACK_REWRITE', None)
            self.assertFalse(rt.flag('PANEL_FALLBACK_REWRITE', '0'))
            self.assertFalse(rt.flag('PANEL_FALLBACK_REWRITE', '1'))      # a registered name: the registry default (0) wins
            os.environ['PANEL_FALLBACK_REWRITE'] = '1'
            self.assertTrue(rt.flag('PANEL_FALLBACK_REWRITE', '0'))
            os.environ['PANEL_FALLBACK_REWRITE'] = '0'
            self.assertFalse(rt.flag('PANEL_FALLBACK_REWRITE', '1'))

    def test_welcome_reads_scope_from_dcr(self):
        self.assertTrue(rt.is_retrieval(self.dcr.read(self.state)))
        self.assertEqual(self.welcome['status'], 'welcome')
        self.assertIn('handicaptillæg', self.welcome['response'])
        self.assertTrue(self.state['retrieval_mode'] and self.state['faq_mode'])

    def test_out_of_scope_never_reaches_the_robot(self):
        self.triage.return_value = self.decision('5')
        result = self.send(message='What is the weather?')
        self.assertEqual(result['status'], 'out_of_scope')
        self.assertIn('Outside scope', result['response'])
        self.assertIn(('FAQ_Triage', '5'), self.dcr.executed)
        self.assertEqual(self.dcr.comments['FAQ_Triage'], 'because')
        self.assertNotIn('FAQ_UserQuestion', [e for e, _ in self.dcr.executed])
        self.assertFalse(self.dcr.events['FAQ_UserQuestion']['included'])  # DCR gate
        self.assertIn('FAQ_OutOfScope', [e for e, _ in self.dcr.executed])
        message, policy, values = self.triage.call_args.args[:3]
        self.assertEqual(policy, 'Triage policy text.')
        self.assertEqual([v['value'] for v in values], ['1', '2', '4', '5'])
        self.route.assert_not_called()

    def test_single_match_is_answered_directly_with_exact_followup(self):
        self.dcr.api = single()
        answer = self.send(message='refused without assessment?')
        self.assertEqual(answer['status'], 'answer')
        self.assertEqual(answer['answer']['question'], ITEMS[2][0])
        self.assertEqual(answer['answer']['faq_id'], 'FAQ_31')
        self.assertEqual(answer['answer']['html'], '<p>Para one.</p><p>Para two.</p>')
        self.assertIn((SEL, '3'), self.dcr.executed)
        self.pick.assert_not_called()  # exact label match, no LLM
        self.assertEqual(answer['prompt']['kind'], 'determination')
        self.assertEqual(answer['prompt']['text'], 'Ask Det31?')
        outcome = self.reply(answer, 'true')
        self.assertEqual(outcome['outcomes'], ['<p>Det31 yes.</p>'])
        self.assertIn(('Det31_Yes', ''), self.dcr.executed)  # acknowledged
        self.assertEqual(outcome['answered']['value'], 'Yes')

    def test_clarify_post_check_and_llm_followup_none(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21', 'FAQ_11']
        options = self.send(message='medical docs')
        self.assertEqual(options['status'], 'options')
        self.assertEqual([o['value'] for o in options['prompt']['options']], ['FAQ_21', 'FAQ_11', 'none'])
        answer = self.reply(options, 'FAQ_21')
        self.assertEqual(answer['answer']['html'], '<p>Answer FAQ_21.</p>')
        self.pick.assert_called_once()
        # every determination is offered, including FAQ_31 whose label mentions 'application'
        self.assertEqual([str(i['value']) for i in self.pick.call_args.args[2]], ['1', '2', '3', '4'])
        self.assertNotIn(SEL, [e for e, _ in self.dcr.executed])
        self.assertNotIn('actions', answer)       # no "another question?" buttons after an answer
        self.assertNotIn('follow_up', answer)

    def test_search_records_the_api_decision_and_gives_kept_candidates_a_tier(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        self.send(message='medical docs')
        self.assertEqual(self.state['last_search'], {'decision': 'clarify_match',
                                                     'retrieved': ['FAQ_11', 'FAQ_21', 'FAQ_99']})
        self.assertEqual([(c['id'], c['tier']) for c in self.state['retrieval_result']['candidates']],
                         [('FAQ_21', 'answers')])

    def test_lone_survivor_of_clarify_is_confirmed_not_answered(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        result = self.send(message='medical docs')
        self.assertEqual((result['status'], result['response']), ('confirm', 'Is this what you are asking?'))
        self.assertEqual(result['prompt']['kind'], 'confirm')
        self.assertEqual(result['prompt']['text'], 'Question FAQ_21?')
        self.assertEqual([o['value'] for o in result['prompt']['options']], ['FAQ_21', 'none'])
        self.assertNotIn('answer', result)
        self.assertNotIn('FAQ_Answered', [e for e, _ in self.dcr.executed])

    def test_confirm_yes_shows_the_answer_and_records_it(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        asked = self.send(message='medical docs')
        answer = self.reply(asked, 'FAQ_21')
        self.assertEqual(answer['status'], 'answer')
        self.assertEqual(answer['answer']['html'], '<p>Answer FAQ_21.</p>')
        self.assertIn(('FAQ_Answered', 'FAQ_21: Question FAQ_21?'), self.dcr.executed)

    def test_confirm_no_asks_to_rephrase_and_shows_nothing(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        asked = self.send(message='medical docs')
        result = self.reply(asked, 'none')
        self.assertEqual(result['status'], 'rephrase')
        self.assertNotIn('answer', result)
        self.assertNotIn('FAQ_Answered', [e for e, _ in self.dcr.executed])
        self.assertIsNone(self.state['retrieval_prompt'])

    def test_single_match_same_topic_only_is_offered_as_related(self):
        self.dcr.api = single()
        self.tiers.side_effect = lambda m, c, **k: {'answers': [], 'related': ['FAQ_31']}
        result = self.send(message='refused?')
        self.assertEqual(result['status'], 'options')
        self.assertIs(result['related'], True)
        self.assertEqual(result['response'], rt.RELATED_ONE)
        self.assertEqual([o['value'] for o in result['prompt']['options']], ['FAQ_31', 'none'])
        self.assertNotIn('answer', result)
        self.assertNotIn('FAQ_Answered', [e for e, _ in self.dcr.executed])

    def test_related_offer_of_several_uses_the_plural_text_and_a_choice_answers_it(self):
        self.dcr.api = clarify()
        self.tiers.side_effect = lambda m, c, **k: {'answers': [], 'related': ['FAQ_11', 'FAQ_21']}
        result = self.send(message='medical docs')
        self.assertEqual((result['status'], result['response']), ('options', rt.RELATED_MANY))
        answer = self.reply(result, 'FAQ_21')
        self.assertEqual(answer['answer']['faq_id'], 'FAQ_21')

    def test_relevance_unavailable_never_answers(self):
        self.dcr.api = single()
        self.tiers.side_effect = llm.LLMError('down')
        result = self.send(message='refused?')
        self.assertEqual(result['status'], 'options')
        self.assertIs(result['related'], True)
        self.assertNotIn('FAQ_Answered', [e for e, _ in self.dcr.executed])
        self.assertEqual(self.state['retrieval_result']['candidates'][0]['tier'], 'related')

    def test_relevance_tiers_flag_off_uses_the_old_check(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21', 'FAQ_11']
        with patch.dict('os.environ', {'RELEVANCE_TIERS': '0'}):
            result = self.send(message='medical docs')
        self.relevant.assert_called_once()
        self.tiers.assert_not_called()
        self.assertEqual(result['status'], 'options')
        self.assertEqual([c['tier'] for c in self.state['retrieval_result']['candidates']], ['answers', 'answers'])

    def test_candidates_come_back_answers_first_and_unknown_ids_are_ignored(self):
        self.dcr.api = clarify()
        self.tiers.side_effect = lambda m, c, **k: {'answers': ['FAQ_99', 'nope'], 'related': ['FAQ_11', 'FAQ_99']}
        kept = rt.check_relevance('m', [dict(id=i, question='q') for i in ('FAQ_11', 'FAQ_21', 'FAQ_99')])
        self.assertEqual([(c['id'], c['tier']) for c in kept], [('FAQ_99', 'answers'), ('FAQ_11', 'related')])

    def test_true_single_match_judged_by_the_check_is_still_answered_directly(self):
        self.dcr.api = single()
        self.assertEqual(self.send(message='refused?')['status'], 'answer')

    def test_post_check_rejects_everything_gives_no_match(self):
        self.dcr.api = single()
        self.relevant.side_effect = lambda m, c, **k: []
        result = self.send(message='how do I bake bread for my handicap?')
        self.assertEqual(result['status'], 'no_match')
        self.assertIn(('FAQ_NoMatch', ''), self.dcr.executed)

    def test_api_no_match(self):
        self.dcr.api = dict(decision='no_match')
        self.assertEqual(self.send(message='x')['status'], 'no_match')
        self.relevant.assert_not_called()

    def test_unavailable_is_shown_and_acknowledged(self):
        self.dcr.api = None
        result = self.send(message='x')
        self.assertEqual(result['status'], 'unavailable')
        self.assertIn('Search down', result['response'])
        self.assertIn(('FAQ_RetrievalUnavailable', ''), self.dcr.executed)

    def test_typed_reply_to_determination(self):
        self.dcr.api = single()
        self.send(message='x')
        self.triage.return_value = self.decision('2', 'false')
        outcome = self.send(message='no, I had everything they asked for')
        self.assertEqual(outcome['outcomes'], ['<p>Det31 no.</p>'])
        self.assertEqual(self.triage.call_args.args[3]['kind'], 'determination')

    def test_unclear_reply_repeats_prompt(self):
        self.dcr.api = single()
        answer = self.send(message='x')            # answer + determination prompt
        self.triage.return_value = self.decision('2')
        again = self.send(message='hmm')
        self.assertEqual(again['status'], 'unclear')
        self.assertEqual(again['prompt']['id'], answer['prompt']['id'])

    def test_new_question_drops_open_followup(self):
        self.dcr.api = single()
        answer = self.send(message='x')
        self.dcr.api = single('FAQ_42', ITEMS[3][0])
        answer2 = self.send(message='missed the deadline')
        with self.assertRaises(StateError):
            self.reply(answer, 'true')  # the old follow-up is gone
        self.assertEqual(answer2['prompt']['text'], 'Ask Det42?')
        self.assertFalse(self.dcr.events['Det31_Ask']['included'])

    def test_stale_prompt_rejected(self):
        self.dcr.api = single()
        self.send(message='x')
        with self.assertRaises(StateError):
            self.send(action='reply', retrieval_prompt_id='old', value='yes')

    def test_apply_leaves_the_chat_for_mitid(self):
        result = self.send(action='apply')
        self.assertEqual(result['status'], 'navigate')
        self.assertTrue(result['navigate'].startswith('/mitid?graphid='))
        self.assertEqual(self.dcr.executed, [])  # nothing runs in the FAQ simulation

    def test_apply_text_is_answered_as_a_question(self):
        self.dcr.api = single()
        self.triage.return_value = self.decision('1')
        self.assertEqual(self.send(message='I want to apply now')['status'], 'answer')
        self.assertIn(('FAQ_Triage', '1'), self.dcr.executed)
        self.assertNotIn('Form0:Email', [e for e, _ in self.dcr.executed])

    def test_triage_failure_falls_back_to_search(self):
        self.triage.side_effect = llm.LLMError('down')
        self.dcr.api = single()
        self.assertEqual(self.send(message='x')['status'], 'answer')
        self.assertIn(('FAQ_Triage', '1'), self.dcr.executed)
        self.assertIn('triage unavailable', self.dcr.comments['FAQ_Triage'])

    def test_rewrite_searches_standalone_question_and_keeps_original(self):
        self.dcr.api = single()
        self.triage.return_value = self.decision('1', query='How old can the medical documentation be?')
        result = self.send(message='and how old can it be?')
        self.assertIn(('FAQ_UserQuestion', 'How old can the medical documentation be?'), self.dcr.executed)
        self.assertEqual(self.dcr.comments['FAQ_UserQuestion'], 'and how old can it be?')
        self.assertEqual(result['searched_for'], 'How old can the medical documentation be?')
        self.assertEqual(self.relevant.call_args.args[0], 'How old can the medical documentation be?')

    def test_self_contained_question_is_not_marked_as_rewritten(self):
        self.dcr.api = single()
        result = self.send(message='Who can get it?')
        self.assertNotIn('searched_for', result)
        self.assertEqual(self.dcr.comments['FAQ_UserQuestion'], '')

    def test_context_comes_from_dcr(self):
        self.dcr.api = single()
        answer = self.send(message='x')
        self.assertIn(('FAQ_Answered', f'FAQ_31: {ITEMS[2][0]}'), self.dcr.executed)
        self.reply(answer, 'true')
        self.dcr.api = single()
        self.send(message='and then what?')
        context = self.triage.call_args.args[4]
        self.assertEqual(context['last_answered_faq'], f'FAQ_31: {ITEMS[2][0]}')
        self.assertEqual(context['last_followup'], {'question': 'Ask Det31?', 'answer': 'Yes'})

    def test_reply_without_prompt_does_not_search(self):
        self.triage.return_value = self.decision('2')
        self.assertEqual(self.send(message='yes')['status'], 'rephrase')
        self.assertNotIn('FAQ_UserQuestion', [e for e, _ in self.dcr.executed])

    def test_end_shows_goodbye_from_dcr(self):
        self.triage.return_value = self.decision('4')
        result = self.send(message="thanks, that's all")
        self.assertEqual(result['status'], 'ended')
        self.assertIn('Goodbye', result['response'])
        self.assertIn(('FAQ_Goodbye', ''), self.dcr.executed)

    def test_welcome_without_welcome_event_uses_scope_and_default_examples(self):
        self.assertEqual([e['id'] for e in self.welcome['examples']], rt.DEFAULT_EXAMPLES)
        self.assertTrue(all(e['question'] for e in self.welcome['examples']))

    def test_welcome_event_supplies_text_and_examples(self):
        from tests.test_retrieval_runtime import ev
        self.dcr.events['FAQ_Welcome'] = ev('FAQ_Welcome', tags='FAQWelcome,Example:FAQ_21,Example:FAQ_09',
                                            description='<p>Hi, I am here to help.</p>')
        welcome = rt.initialize(self.state, self.dcr.read(self.state))
        self.assertEqual(welcome['response'], '<p>Hi, I am here to help.</p>')
        self.assertEqual([e['id'] for e in welcome['examples']], ['FAQ_21', 'FAQ_09'])

    def test_example_is_answered_directly_without_llm_triage(self):
        self.dcr.api = single()
        answer = self.send(action='example', faq_id='FAQ_31')
        self.assertEqual(answer['status'], 'answer')
        self.assertEqual(answer['answer']['faq_id'], 'FAQ_31')
        self.assertIn(('FAQ_Triage', '1'), self.dcr.executed)
        self.assertEqual(self.dcr.comments['FAQ_Triage'], 'example question chosen by the applicant')
        self.assertIn(('FAQ_UserQuestion', rt.faq_titles()['FAQ_31']), self.dcr.executed)
        self.triage.assert_not_called()

    def test_example_not_returned_by_its_title_falls_back_to_options(self):
        self.dcr.api = clarify()
        result = self.send(action='example', faq_id='FAQ_31')
        self.assertEqual(result['status'], 'options')
        with self.assertRaises(StateError):
            self.send(action='example', faq_id='FAQ_00')

    def test_idle_end_is_recorded_in_dcr(self):
        result = self.send(action='end', reason='idle')
        self.assertEqual(result['status'], 'ended')
        self.assertIn('Goodbye', result['response'])
        self.assertIn(('FAQ_Triage', '4'), self.dcr.executed)
        self.assertEqual(self.dcr.comments['FAQ_Triage'], 'idle timeout (no activity)')
        self.assertIn(('FAQ_Goodbye', ''), self.dcr.executed)

    def test_graph_without_triage_uses_builtin_router(self):
        self.dcr.drop_triage()
        self.dcr.api = single()
        self.assertEqual(self.send(message='x')['status'], 'answer')
        self.route.assert_called_once()
        self.triage.assert_not_called()


class RetrievalLLMSchemaTests(unittest.TestCase):
    class Client:
        def __init__(self, out):
            self.out = out
            self.responses = self

        def create(self, **kwargs):
            self.kwargs = kwargs
            return type('R', (), {'status': 'completed', 'output_text': json.dumps(self.out)})()

    def settings(self):
        from dcrai.llm import openchat
        return openchat.Settings()

    def test_route_rejects_value_outside_prompt(self):
        client = self.Client({'intent': 'reply', 'reply_value': 'maybe', 'reason': ''})
        prompt = {'kind': 'determination', 'text': 'Q?', 'choices': [{'value': 'true', 'label': 'Yes'}]}
        self.assertEqual(llm.route('m', prompt, 'scope', client=client, settings=self.settings()), ('reply', None))
        schema = client.kwargs['text']['format']['schema']
        self.assertEqual(schema['properties']['reply_value']['enum'], ['true', None])

    def test_relevant_filters_unknown_ids(self):
        client = self.Client({'relevant_ids': ['FAQ_2', 'nope', 'FAQ_2'], 'reason': ''})
        got = llm.relevant('m', [{'id': 'FAQ_1', 'question': 'a'}, {'id': 'FAQ_2', 'question': 'b'}],
                           client=client, settings=self.settings())
        self.assertEqual(got, ['FAQ_2'])

    def test_relevance_tiers_schema_is_disjoint(self):
        client = self.Client({'answers': ['FAQ_1'], 'related': ['FAQ_1', 'FAQ_2', 'FAQ_X', 'FAQ_2'], 'reason': ''})
        got = llm.relevance_tiers('m', [{'id': 'FAQ_1', 'question': 'a'}, {'id': 'FAQ_2', 'question': 'b'}],
                                  client=client, settings=self.settings())
        self.assertEqual(got, {'answers': ['FAQ_1'], 'related': ['FAQ_2']})
        schema = client.kwargs['text']['format']['schema']
        self.assertEqual(schema['required'], ['answers', 'related', 'reason'])
        self.assertEqual(schema['properties']['answers']['items']['enum'], ['FAQ_1', 'FAQ_2'])
        self.assertEqual(client.kwargs['instructions'], llm.RELEVANCE_TIERS_PROMPT)
        self.assertEqual(llm.relevance_tiers('m', [], client=client, settings=self.settings()),
                         {'answers': [], 'related': []})

    def test_triage_schema_from_event_values(self):
        client = self.Client({'value': '1', 'reply_value': None, 'search_query': '  standalone?  ', 'reason': 'r'})
        got = llm.triage('m', 'POLICY', [{'value': '1', 'label': 'q'}, {'value': '5', 'label': 'oos'}], None,
                         {'last_answered_faq': None, 'last_followup': None}, client=client, settings=self.settings())
        self.assertEqual(got['search_query'], 'standalone?')
        sent = json.loads(client.kwargs['input'])
        self.assertEqual(sent['policy'], 'POLICY')
        self.assertEqual(client.kwargs['text']['format']['schema']['properties']['value']['enum'], ['1', '5'])

    def test_triage_rejects_unknown_value(self):
        client = self.Client({'value': '9', 'reply_value': None, 'search_query': None, 'reason': ''})
        with self.assertRaises(llm.LLMError):
            llm.triage('m', 'P', [{'value': '1', 'label': 'q'}], None, {}, client=client, settings=self.settings())

    def test_pick_followup_none(self):
        client = self.Client({'value': 'none', 'reason': ''})
        self.assertIsNone(llm.pick_followup('m', 'q', [{'value': '1', 'label': 'x'}], client=client,
                                            settings=self.settings()))


if __name__ == '__main__':
    unittest.main()


class DecisionsTests(unittest.TestCase):
    """Decisions API path: thresholds, conditional rewrite, fallback, scope check."""

    class Http:
        def __init__(self, answers, status=200):
            self.answers, self.status, self.sent = answers, status, None

        def post(self, url, **kwargs):
            from unittest.mock import Mock
            self.sent = kwargs['json']
            return Mock(status_code=self.status, json=lambda: {'answers': self.answers})

    VALUES = [{'value': str(i), 'label': f'v{i}'} for i in range(1, 6)]
    YESNO = {'kind': 'determination', 'text': 'Q?', 'choices': [{'value': 'true', 'label': 'Yes'},
                                                               {'value': 'false', 'label': 'No'}]}

    def setUp(self):
        patch.dict('os.environ', {'OPENAI_API_KEY': 'k', 'DECISIONS_ENABLED': '1'}).start()
        self.addCleanup(patch.stopall)

    def tri(self, choice, conf, probs, ctx=0.0, reply=None):
        out = [{'type': 'choice', 'name': 'triage', 'choice': choice, 'confidence': conf,
                'probabilities': [{'value': k, 'probability': v} for k, v in probs.items()]},
               {'type': 'predicate', 'name': 'contextual', 'probability': ctx}]
        if reply:
            out.append({'type': 'choice', 'name': 'reply', 'choice': reply[0], 'confidence': reply[1]})
        return out

    def test_confident_triage(self):
        http = self.Http(self.tri('1', 0.93, {'1': .94, '5': .01}))
        got = llm.triage_decisions('who can get it?', 'POLICY', self.VALUES, None, {}, http=http)
        self.assertEqual((got['value'], got['unsure'], got['search_query']), ('1', False, None))
        self.assertEqual(http.sent['questions'][0]['instructions'], 'POLICY')
        self.assertIn('conf=0.93', got['reason'])

    def test_unsure_between_question_and_out_of_scope(self):
        http = self.Http(self.tri('5', 0.4, {'1': .4, '5': .55, '2': .05}))
        self.assertTrue(llm.triage_decisions('housing benefit?', 'P', self.VALUES, None, {}, http=http)['unsure'])

    def test_low_reply_confidence_drops_value(self):
        http = self.Http(self.tri('2', 0.85, {'2': .9}, reply=('true', 0.37)))
        got = llm.triage_decisions('no, I had more', 'P', self.VALUES, self.YESNO, {}, http=http)
        self.assertIsNone(got['reply_value'])
        http = self.Http(self.tri('2', 0.85, {'2': .9}, reply=('false', 0.9)))
        self.assertEqual(llm.triage_decisions('no', 'P', self.VALUES, self.YESNO, {}, http=http)['reply_value'], 'false')

    def test_rewrite_only_with_context_and_high_probability(self):
        with patch.object(llm, 'rewrite', return_value='How old can documentation be?') as rewrite:
            http = self.Http(self.tri('1', 0.9, {'1': .9}, ctx=1.0))
            got = llm.triage_decisions('and how old?', 'P', self.VALUES, None,
                                       {'last_answered_faq': 'FAQ_21: docs?'}, http=http)
            self.assertEqual(got['search_query'], 'How old can documentation be?')
            http = self.Http(self.tri('1', 0.9, {'1': .9}, ctx=0.41))
            llm.triage_decisions("I'm not Danish", 'P', self.VALUES, None, {'last_answered_faq': 'x'}, http=http)
            http = self.Http(self.tri('1', 0.9, {'1': .9}, ctx=1.0))
            llm.triage_decisions('and how old?', 'P', self.VALUES, None, {}, http=http)  # no context in DCR
            self.assertEqual(rewrite.call_count, 1)

    def test_refusal_or_error_raises(self):
        with self.assertRaises(llm.LLMError):
            llm.triage_decisions('m', 'P', self.VALUES, None, {}, http=self.Http([], status=500))
        refusal = [{'type': 'refusal', 'name': 'triage'}, {'type': 'predicate', 'name': 'contextual', 'probability': 0}]
        with self.assertRaises(llm.LLMError):
            llm.triage_decisions('m', 'P', self.VALUES, None, {}, http=self.Http(refusal))

    def test_relevance_and_followup_predicates(self):
        http = self.Http([{'type': 'predicate', 'name': 'fits_0', 'probability': 0.9},
                          {'type': 'predicate', 'name': 'fits_1', 'probability': 0.1}])
        self.assertEqual(llm.relevant_decisions('docs?', [{'id': 'FAQ_21', 'question': 'a'},
                                                          {'id': 'FAQ_05b', 'question': 'b'}], http=http), ['FAQ_21'])
        items = [{'value': '1', 'label': 'x'}, {'value': '3', 'label': 'y'}]
        http = self.Http([{'type': 'predicate', 'name': 'same_0', 'probability': 0.1},
                          {'type': 'predicate', 'name': 'same_1', 'probability': 0.95}])
        self.assertEqual(llm.pick_followup_decisions('m', 'y', items, http=http), '3')
        http = self.Http([{'type': 'predicate', 'name': 'same_0', 'probability': 0.5},
                          {'type': 'predicate', 'name': 'same_1', 'probability': 0.45}])
        self.assertIsNone(llm.pick_followup_decisions('m', 'q', items, http=http))

    def test_relevance_tiers_decisions_two_predicates_per_candidate(self):
        http = self.Http([{'type': 'predicate', 'name': 'answers_0', 'probability': 0.9},
                          {'type': 'predicate', 'name': 'topic_0', 'probability': 0.9},
                          {'type': 'predicate', 'name': 'answers_1', 'probability': 0.1},
                          {'type': 'predicate', 'name': 'topic_1', 'probability': 0.8},
                          {'type': 'predicate', 'name': 'answers_2', 'probability': 0.1},
                          {'type': 'predicate', 'name': 'topic_2', 'probability': 0.1}])
        got = llm.relevance_tiers_decisions('docs?', [{'id': 'FAQ_21', 'question': 'a', 'answer': 'start of a'},
                                                      {'id': 'FAQ_05b', 'question': 'b'},
                                                      {'id': 'FAQ_99', 'question': 'c'}], http=http)
        self.assertEqual(got, {'answers': ['FAQ_21'], 'related': ['FAQ_05b']})
        questions = http.sent['questions']
        self.assertEqual([q['name'] for q in questions],
                         ['answers_0', 'topic_0', 'answers_1', 'topic_1', 'answers_2', 'topic_2'])
        for q in questions:
            expected = llm.RELEVANCE_ANSWERS if q['name'].startswith('answers') else llm.RELEVANCE_SAME_TOPIC
            self.assertTrue(q['instructions'].startswith(expected + ' FAQ question: '))
        self.assertIn('FAQ answer begins: start of a', questions[0]['instructions'])

    def test_relevance_tiers_decisions_thresholds_and_order(self):
        http = self.Http([{'type': 'predicate', 'name': f'{kind}_{i}', 'probability': p}
                          for i, (a, t) in enumerate([(0.6, 0.0), (0.9, 0.0), (0.3, 0.7), (0.3, 0.9)])
                          for kind, p in (('answers', a), ('topic', t))])
        cands = [{'id': f'F{i}', 'question': 'q'} for i in range(4)]
        self.assertEqual(llm.relevance_tiers_decisions('m', cands, http=http),
                         {'answers': ['F1', 'F0'], 'related': ['F3', 'F2']})
        with patch.dict('os.environ', {'DECISIONS_ANSWERS_MIN': '0.95', 'DECISIONS_TOPIC_MIN': '0.8'}):
            self.assertEqual(llm.relevance_tiers_decisions('m', cands, http=http),
                             {'answers': [], 'related': ['F3']})

    def test_runtime_falls_back_to_responses(self):
        with patch.object(llm, 'triage_decisions', side_effect=llm.LLMError('beta down')), \
             patch.object(llm, 'triage', return_value=dict(value='4', reply_value=None, search_query=None,
                                                          reason='r')) as fallback:
            self.assertEqual(rt.classify('triage', 'm', 'P', self.VALUES, None, {})['value'], '4')
            fallback.assert_called_once()


class ScopeCheckTests(unittest.TestCase):
    def setUp(self):
        self.dcr = FakeDCR()
        self.state = {'graph_id': 1, 'simulation_id': 2}
        patch.object(rt.repo, 'get_raw_events', side_effect=self.dcr.read).start()
        patch.object(rt.repo, 'execute_raw_event', side_effect=self.dcr.execute).start()
        patch.object(llm, 'relevant', side_effect=lambda m, c, **k: [x['id'] for x in c]).start()
        patch_tiers()
        patch.object(llm, 'pick_followup', return_value=None).start()
        self.triage = patch.object(llm, 'triage', return_value=dict(value='5', reply_value=None, search_query=None,
                                                                    reason='r', unsure=True)).start()
        self.addCleanup(patch.stopall)
        rt.initialize(self.state, self.dcr.read(self.state))

    def test_unsure_asks_before_triage_then_searches(self):
        result = rt.handle(self.state, {'message': 'How do I apply for housing support as a student?'})
        self.assertEqual(result['status'], 'scope_check')
        self.assertNotIn('FAQ_Triage', [e for e, _ in self.dcr.executed])  # nothing decided yet
        self.dcr.api = single()
        confirm = rt.handle(self.state, {'action': 'reply', 'retrieval_prompt_id': result['prompt']['id'], 'value': '1'})
        self.assertIn(('FAQ_Triage', '1'), self.dcr.executed)
        self.assertEqual(self.dcr.comments['FAQ_Triage'], 'scope confirmed by the applicant')
        self.assertIn(('FAQ_UserQuestion', 'How do I apply for housing support as a student?'), self.dcr.executed)
        self.assertEqual(confirm['status'], 'answer')

    def test_unsure_then_no_is_out_of_scope(self):
        result = rt.handle(self.state, {'message': 'housing benefit?'})
        out = rt.handle(self.state, {'action': 'reply', 'retrieval_prompt_id': result['prompt']['id'], 'value': '5'})
        self.assertEqual(out['status'], 'out_of_scope')
        self.assertNotIn('FAQ_UserQuestion', [e for e, _ in self.dcr.executed])


class InteractionLogTests(unittest.TestCase):
    """Spec 01 R11, R12: outcome and reaction events, the chat log start, and the turn counter. No message text."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        import dcrai.observability.interaction_log as ilog
        self.ilog = ilog
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch.object(ilog, 'DIRECTORY', self.tmp.name).start()
        patch.object(ilog, 'ENABLED', True).start()
        self.addCleanup(patch.stopall)
        self.dir = Path(self.tmp.name)

    def lines(self, state, *kinds):
        path = self.dir / f"{state['interaction']['id']}.jsonl"
        rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
        return [r for r in rows if not kinds or r['kind'] in kinds]

    def test_start_records_the_interface_and_marks_a_missing_one_unknown(self):
        # Spec 02 R9 and R22: the start line always carries the interface; a caller that passes none is 'unknown'.
        chat, other = {}, {}
        self.ilog.start(chat, '1', '2', interface='chat')
        with self.assertLogs('dcrai.observability.interaction_log', level='WARNING'):
            self.ilog.start(other, '1', '2')
        self.assertEqual(self.lines(chat, 'start')[0]['interface'], 'chat')
        self.assertEqual(self.lines(other, 'start')[0]['interface'], 'unknown')

    def test_log_outcome_and_reaction_carry_ids_and_no_text(self):
        state = {'turn': 3}
        self.ilog.start(state, '1', '2', interface='chat')
        shown = [dict(id='FAQ_21', question='Secret question text?', answer='Secret answer text.')]
        rt.log_outcome(state, 'chat', 'confirm', 6, shown, 'typed')
        rt.log_outcome(state, 'chat', 'answer', 4, ['FAQ_31'], 'typed', same_faq=True)
        state['turn'] = 4
        rt.log_reaction(state, 'chat', 'confirm', 'rejected', turn=3)
        rt.log_reaction(state, 'chat', 'confirm', 'accepted', faq_id='FAQ_21', turn=3)
        rows = self.lines(state, 'faq_outcome', 'faq_reaction')
        first, second, rejected, accepted = rows
        self.assertEqual((first['kind'], first['interface'], first['turn'], first['outcome'], first['outcome_row']),
                         ('faq_outcome', 'chat', 3, 'confirm', 6))
        self.assertEqual((first['faq_ids'], first['via']), (['FAQ_21'], 'typed'))
        self.assertIs(second['same_faq'], True)
        self.assertEqual((rejected['kind'], rejected['turn'], rejected['outcome'], rejected['next_action']),
                         ('faq_reaction', 3, 'confirm', 'rejected'))
        self.assertNotIn('faq_id', rejected)
        self.assertEqual(accepted['faq_id'], 'FAQ_21')
        text = (self.dir / f"{state['interaction']['id']}.jsonl").read_text(encoding='utf-8')
        self.assertNotIn('Secret', text)

    def test_chat_logs_outcome_and_reaction_without_text(self):
        dcr = FakeDCR()
        state = {'graph_id': 1, 'simulation_id': 2}
        message = 'my private question about medical docs'
        with patch.object(rt.repo, 'get_raw_events', side_effect=dcr.read), \
             patch.object(rt.repo, 'execute_raw_event', side_effect=dcr.execute), \
             patch.object(llm, 'triage', return_value=dict(value='1', reply_value=None, search_query=None,
                                                           reason='r')), \
             patch.object(llm, 'relevant', side_effect=lambda m, c, **k: ['FAQ_21']), \
             patch.object(llm, 'relevance_tiers', side_effect=lambda m, c, **k: {'answers': ['FAQ_21'],
                                                                                'related': []}), \
             patch.object(llm, 'pick_followup', return_value=None):
            self.ilog.start(state, '1', '2', interface='chat')
            rt.initialize(state, dcr.read(state))
            dcr.api = clarify()
            asked = rt.handle(state, {'message': message})
            rt.handle(state, {'action': 'reply', 'retrieval_prompt_id': asked['prompt']['id'], 'value': 'none'})
        rows = self.lines(state, 'faq_outcome', 'faq_reaction')
        outcome, reaction = rows
        self.assertEqual((outcome['interface'], outcome['turn'], outcome['outcome'], outcome['outcome_row']),
                         ('chat', 1, 'confirm', 6))
        self.assertEqual((outcome['faq_ids'], outcome['via']), (['FAQ_21'], 'typed'))
        self.assertEqual((reaction['interface'], reaction['turn'], reaction['outcome'], reaction['next_action']),
                         ('chat', 1, 'confirm', 'rejected'))
        raw = '\n'.join(json.dumps(r) for r in rows)
        for text in (message, 'Question FAQ_21?', 'Answer FAQ_21'):
            self.assertNotIn(text, raw)

    def test_handle_counts_a_turn_for_a_message_an_example_and_a_reply(self):
        dcr = FakeDCR()
        state = {'graph_id': 1, 'simulation_id': 2}
        with patch.object(rt.repo, 'get_raw_events', side_effect=dcr.read), \
             patch.object(rt.repo, 'execute_raw_event', side_effect=dcr.execute), \
             patch.object(llm, 'triage', return_value=dict(value='1', reply_value=None, search_query=None,
                                                           reason='r')), \
             patch.object(llm, 'relevant', side_effect=lambda m, c, **k: [x['id'] for x in c]), \
             patch.object(llm, 'relevance_tiers', side_effect=lambda m, c, **k: {'answers': [x['id'] for x in c],
                                                                                'related': []}), \
             patch.object(llm, 'pick_followup', return_value=None):
            rt.initialize(state, dcr.read(state))
            dcr.api = clarify()
            options = rt.handle(state, {'message': 'medical docs'})
            self.assertEqual(state['turn'], 1)
            rt.handle(state, {'action': 'reply', 'retrieval_prompt_id': options['prompt']['id'], 'value': 'none'})
            self.assertEqual(state['turn'], 2)
            dcr.api = single()
            rt.handle(state, {'action': 'example', 'faq_id': 'FAQ_01'})
            self.assertEqual(state['turn'], 3)

    def test_init_starts_an_interaction_log_on_retrieval_graphs(self):
        from xml.etree.ElementTree import Element
        import app as webapp
        dcr = FakeDCR()
        webapp.tab_sessions.clear()
        with patch.object(webapp.dcrrepo, 'get_graph', return_value=Element('dcrgraph', title='FAQ')), \
             patch.object(webapp.dcrrepo, 'create_simulation', return_value=77), \
             patch.object(webapp.dcrrepo, 'get_events', side_effect=lambda s: dcr.read(s)):
            response = webapp.app.test_client().post('/init', json={'graph_id': '5'},
                                                     headers={'X-Session-ID': 'chat-log'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'welcome')
        session = webapp.tab_sessions['chat-log']
        self.assertTrue(session['interaction']['id'])
        started = self.lines(session, 'start')
        self.assertEqual(len(started), 1)
        self.assertEqual((started[0]['interface'], started[0]['graph_id'], started[0]['simulation_id']),
                         ('chat', '5', 77))


class TurnFake(FakeDCR):
    """The chat graph after spec 03: Session_Chat, TurnOutcome (the execute makes exactly its outcome event pending),
    the outcome texts and the handover events."""

    def __init__(self, session=True, turn_outcome=True, handover=True, texts=None):
        super().__init__()
        import dcrai.chat.outcome as oc
        self.oc = oc
        if session:
            self.events['Session_Chat'] = ev('Session_Chat')
        if turn_outcome:
            self.events['TurnOutcome'] = ev('TurnOutcome', dtype='choice',
                                            choice=', '.join(f'{v} ({v})' for v in oc.OUTCOMES))
            for name in ('Answer', 'Confirm', 'Offer', 'Clarify'):
                self.events[f'Outcome_{name}'] = ev(f'Outcome_{name}', tags='OutcomeMessage',
                                                    description=f'<p>{name} text from DCR.</p>')
        if handover:
            self.events['Help_Escalate'] = ev('Help_Escalate', dtype='choice', tags='FAQEscalation',
                                              choice='Asked (1), Misses (2), Deadline (3), Distress (4)')
            self.events['Help_Handover'] = ev('Help_Handover', tags='FAQHandover',
                                              description='<p>Use the contact options on SU.dk.</p>')
        for eid, text in (texts or {}).items():
            self.events[eid] = ev(eid, description=f'<p>{text}</p>')

    def execute(self, state, eid, value, comment='', role=None):
        done = super().execute(state, eid, value, comment, role)
        if done and eid == 'TurnOutcome':
            for outcome, event_id in self.oc.OUTCOME_EVENT.items():
                if event_id in self.events:
                    self.events[event_id]['pending'] = outcome == value
        if done and eid == 'Help_Escalate' and 'Help_Handover' in self.events:
            self.events['Help_Handover']['pending'] = True
        return done

    def names(self, eid=None):
        return [e for e, _ in self.executed if eid is None or e == eid]


class OutcomeTableChatTests(unittest.TestCase):
    """Spec 03 section 5.5, chat rows. A fake DCR with TurnOutcome and a fake LLM; no model, no network."""

    def build(self, **kwargs):
        import tempfile
        from pathlib import Path
        import dcrai.observability.interaction_log as ilog
        self.ilog = ilog
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch.object(ilog, 'DIRECTORY', self.tmp.name).start()
        patch.object(ilog, 'ENABLED', True).start()
        self.dir = Path(self.tmp.name)
        self.dcr = TurnFake(**kwargs)
        self.state = {'graph_id': 1, 'simulation_id': 2}
        patch.object(rt.repo, 'get_raw_events', side_effect=self.dcr.read).start()
        patch.object(rt.repo, 'execute_raw_event', side_effect=self.dcr.execute).start()
        patch.object(llm, 'route', return_value=('new_question', None)).start()
        self.triage = patch.object(llm, 'triage', return_value=dict(value='1', reply_value=None, search_query=None,
                                                                    reason='r')).start()
        self.relevant = patch.object(llm, 'relevant', side_effect=lambda m, c, **k: [x['id'] for x in c]).start()
        patch_tiers()
        self.pick = patch.object(llm, 'pick_followup', return_value=None).start()
        patch.dict('os.environ', {'OUTCOME_MODE': 'code'}).start()
        os_environ_pop('FOLLOWUP_SURFACE')
        self.addCleanup(patch.stopall)
        self.ilog.start(self.state, '1', '2', interface='chat')
        self.welcome = rt.initialize(self.state, self.dcr.read(self.state))

    def setUp(self):
        self.build()

    def outcomes(self):
        path = self.dir / f"{self.state['interaction']['id']}.jsonl"
        rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
        return [r for r in rows if r['kind'] == 'faq_outcome']

    def send(self, message='a question'):
        return rt.handle(self.state, {'message': message})

    def reply(self, result, value):
        return rt.handle(self.state, {'action': 'reply', 'retrieval_prompt_id': result['prompt']['id'], 'value': value})

    def test_lone_survivor_logs_row_6_and_true_single_row_4(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        confirm = self.send('medical docs')
        self.assertEqual(confirm['status'], 'confirm')
        self.dcr.api = single()
        self.relevant.side_effect = lambda m, c, **k: [x['id'] for x in c]
        answer = self.send('refused without assessment?')
        self.assertEqual(answer['status'], 'answer')
        rows = self.outcomes()
        self.assertEqual([(r['outcome'], r['outcome_row']) for r in rows], [('confirm', 6), ('answer', 4)])
        self.assertEqual(rows[0]['outcome_inputs'], dict(scope='in_scope', search='list', relevance='one_answers',
                                                         clarified=0, misses=0))
        self.assertIn(('TurnOutcome', 'confirm'), self.dcr.executed)
        self.assertIn(('Outcome_Confirm', ''), self.dcr.executed)    # acknowledged by the host after it was shown

    def test_unsure_gives_scope_question_row_2(self):
        self.triage.return_value = dict(value='5', reply_value=None, search_query=None, reason='r', unsure=True)
        result = self.send('housing benefit?')
        self.assertEqual(result['status'], 'scope_check')
        self.assertEqual(result['prompt']['kind'], 'scope_check')
        self.assertEqual(result['prompt']['text'], 'Is your question about handicaptillæg, the SU disability supplement?')
        self.assertEqual(self.state['outcome']['clarified'], 0)
        self.assertEqual([r['outcome_row'] for r in self.outcomes()], [2])
        self.assertNotIn('FAQ_UserQuestion', self.dcr.names())

    def test_scope_question_text_comes_from_the_dcr_event_when_present(self):
        patch.stopall()
        self.build(texts={'FAQ_Msg_ScopeQuestion': 'Is this about the handicap supplement?'})
        self.triage.return_value = dict(value='5', reply_value=None, search_query=None, reason='r', unsure=True)
        result = self.send('housing benefit?')
        self.assertEqual(result['prompt']['text'], 'Is this about the handicap supplement?')

    def test_second_list_after_clarify_is_offer_row_8(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_11', 'FAQ_21']
        first = self.send('medical docs')
        self.assertEqual((first['status'], first['response']), ('options', 'Clarify text from DCR.'))
        self.assertEqual(self.state['outcome']['clarified'], 1)
        second = self.send('medical docs again')
        self.assertEqual(second['status'], 'options')
        self.assertNotIn('related', second)
        self.assertEqual([(r['outcome'], r['outcome_row']) for r in self.outcomes()], [('clarify', 7), ('offer', 8)])

    def test_second_miss_adds_handover(self):
        self.dcr.api = dict(decision='no_match')
        first = self.send('nothing like this')
        self.assertEqual(first['status'], 'no_match')
        self.assertNotIn('handover', first)
        second = self.send('still nothing')
        self.assertEqual(second['status'], 'no_match')
        self.assertIn('No FAQ fits', second['response'])
        self.assertEqual(second['handover']['reason'], 2)
        self.assertEqual(second['handover']['html'], '<p>Use the contact options on SU.dk.</p>')
        third = self.send('and again')
        self.assertEqual(third['status'], 'no_match')
        self.assertNotIn('handover', third)
        self.assertEqual(self.dcr.names('Help_Escalate'), ['Help_Escalate'])    # once per session
        self.assertEqual([r['outcome'] for r in self.outcomes()], ['not_covered', 'handover', 'not_covered'])

    def test_reject_twice_in_a_row_adds_handover_once(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        first = self.reply(self.send('medical docs'), 'none')
        self.assertEqual(first['status'], 'rephrase')
        self.assertNotIn('handover', first)
        second = self.reply(self.send('medical docs 2'), 'none')
        self.assertEqual(second['handover']['reason'], 2)

    def test_a_shown_answer_resets_the_miss_run(self):
        self.dcr.api = dict(decision='no_match')
        self.send('nothing')
        self.dcr.api = single()
        self.assertEqual(self.send('refused without assessment?')['status'], 'answer')
        self.dcr.api = dict(decision='no_match')
        self.assertNotIn('handover', self.send('nothing again'))

    def test_person_request_is_handover_reason_1(self):
        result = self.send('I want to talk to a person')
        self.assertEqual(result['status'], 'handover')
        self.assertEqual(result['handover']['reason'], 1)
        self.assertNotIn('FAQ_UserQuestion', self.dcr.names())
        self.assertEqual([r['outcome'] for r in self.outcomes()], ['handover'])

    def test_chat_does_not_fire_determination(self):
        self.assertTrue(self.dcr.events[SEL]['enabled'])
        self.dcr.api = single()
        answer = self.send('refused without assessment?')
        self.assertEqual(answer['status'], 'answer')
        self.assertNotIn(SEL, self.dcr.names())
        self.pick.assert_not_called()
        self.assertNotIn('prompt', answer)

    def test_followup_surface_chat_restores_today(self):
        with patch.dict('os.environ', {'FOLLOWUP_SURFACE': 'chat'}):
            self.dcr.api = single()
            answer = self.send('refused without assessment?')
        self.assertIn((SEL, '3'), self.dcr.executed)
        self.assertEqual(answer['prompt']['kind'], 'determination')

    def test_initialize_executes_session_chat_only_if_present(self):
        self.assertEqual(self.dcr.names('Session_Chat'), ['Session_Chat'])
        patch.stopall()
        self.build(session=False)
        self.assertEqual(self.dcr.names('Session_Chat'), [])
        self.assertEqual(self.welcome['status'], 'welcome')

    def test_out_of_scope_acknowledged_once(self):
        self.triage.return_value = dict(value='5', reply_value=None, search_query=None, reason='r')
        result = self.send('What is the weather?')
        self.assertEqual(result['status'], 'out_of_scope')
        self.assertIn('Outside scope', result['response'])
        self.assertEqual(self.dcr.names('FAQ_OutOfScope'), ['FAQ_OutOfScope'])
        self.assertIn(('TurnOutcome', 'out_of_scope'), self.dcr.executed)
        self.assertEqual([r['outcome_row'] for r in self.outcomes()], [1])

    def test_confirm_text_comes_from_dcr_event(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        self.assertEqual(self.send('medical docs')['response'], 'Confirm text from DCR.')

    def test_confirm_text_falls_back_to_the_host_string(self):
        patch.stopall()
        self.build(turn_outcome=False)
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        self.assertEqual(self.send('medical docs')['response'], 'Is this what you are asking?')
        self.assertNotIn('TurnOutcome', self.dcr.names())     # R12: a graph without the table is untouched

    def test_settled_outcome_is_written_into_dcr_before_the_text_is_shown(self):
        self.dcr.api = dict(decision='no_match')
        result = self.send('nothing like this')
        order = self.dcr.names()
        self.assertLess(order.index('TurnOutcome'), order.index('FAQ_NoMatch'))
        self.assertEqual(self.dcr.names('FAQ_NoMatch'), ['FAQ_NoMatch'])
        self.assertIn('No FAQ fits', result['response'])


def os_environ_pop(name):
    import os
    os.environ.pop(name, None)
