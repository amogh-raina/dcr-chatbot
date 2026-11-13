"""FAQ questions during the application (help panel) on the retrieval graph, against the fake DCR."""
import contextlib
import json
import logging
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import dcrai.application.application_runtime as app
import dcrai.llm.retrieval_llm as llm
import dcrai.chat.retrieval_runtime as rt
from tests.test_retrieval_runtime import FakeDCR, SEL, TurnFake, clarify, patch_tiers, single

QUESTION = 'Will they refuse me without looking at my case?'


class ApplicationFAQTests(unittest.TestCase):
    def setUp(self):
        self.dcr = FakeDCR()
        # The application session: Form0 open, the email field is the one question on screen.
        self.dcr.events['Form0:Email'].update(included=True, enabled=True)
        self.state = {'graph_id': 1, 'simulation_id': 2}
        patch.object(rt.repo, 'get_raw_events', side_effect=self.dcr.read).start()
        patch.object(rt.repo, 'execute_raw_event', side_effect=self.dcr.execute).start()
        patch.object(llm, 'decisions_enabled', return_value=False).start()
        self.relevant = patch.object(llm, 'relevant', side_effect=lambda m, c, **k: [x['id'] for x in c]).start()
        self.tiers, _ = patch_tiers()
        self.triage = patch.object(llm, 'triage', return_value=dict(
            value='1', reply_value=None, search_query=None, reason='application help: a question')).start()
        self.route = patch.object(llm, 'route').start()
        self.addCleanup(patch.stopall)
        self.first = app.start(self.state)

    def ask(self, message=QUESTION):
        return app.ask(self.state, {'message': message})

    @contextlib.contextmanager
    def logged(self):
        """Interaction log in a temp folder; yields lines(*kinds) that reads the events back (also after the block)."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with patch.object(app.ilog, 'DIRECTORY', folder), patch.object(app.ilog, 'ENABLED', True):
            app.ilog.start(self.state, '1', '2', interface='panel')
            self.state['interaction']['shown'] = {}      # what app.start does when the log is already running
            path = Path(folder) / f"{self.state['interaction']['id']}.jsonl"

            def lines(*kinds):
                rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
                return [r for r in rows if not kinds or r['kind'] in kinds]
            yield lines

    def test_starts_on_the_email_field(self):
        self.assertEqual(self.first['field']['id'], 'Form0:Email')

    def test_single_match_is_answered_directly_after_triage_one_and_search(self):
        self.dcr.api = single()
        result = self.ask()
        self.assertTrue(result['answered'])
        self.assertEqual((result['faq_id'], result['faq_question']), ('FAQ_31', single()['question']))
        self.assertEqual(result['faq_response'], '<p>Para one.</p><p>Para two.</p>')
        self.assertNotIn('match_id', result)
        self.assertEqual(self.dcr.executed[:3], [('FAQ_Triage', '1'), ('FAQ_UserQuestion', QUESTION),
                                                 ('FAQ_Answered', f"FAQ_31: {single()['question']}")])
        self.assertEqual(self.dcr.comments['FAQ_Triage'], 'application help: a question')
        self.assertEqual([v['value'] for v in self.triage.call_args.args[2]], ['1', '5'])   # the panel offers 1 and 5
        self.route.assert_not_called()

    def test_confirm_shows_the_answer_verbatim_and_never_opens_a_determination(self):
        # FOLLOWUP_SURFACE=chat restores the old behaviour: the panel asks no follow-up either (spec 03, R10).
        patch.dict('os.environ', {'FOLLOWUP_SURFACE': 'chat'}).start()
        self.dcr.api = single()
        result = self.ask()
        self.assertEqual(result['faq_citation'], '§ 37')
        self.assertEqual(result['field']['id'], 'Form0:Email')
        self.dcr.api = clarify()
        asked = self.ask()
        result = app.confirm(self.state, {'match_id': asked['match_id'], 'candidate_key': 'FAQ_21'})
        self.assertEqual((result['faq_id'], result['faq_response']), ('FAQ_21', '<p>Answer FAQ_21.</p>'))
        self.assertIn(('FAQ_Answered', 'FAQ_21: Question FAQ_21?'), self.dcr.executed)
        executed = [eid for eid, _ in self.dcr.executed]
        self.assertNotIn(SEL, executed)
        self.assertFalse([eid for eid in executed if eid.startswith('Det')])

    def test_field_answer_still_works_after_a_question(self):
        self.dcr.api = single()
        shown = self.ask()
        done = app.answer(self.state, {'prompt_id': shown['prompt_id'], 'value': 'a@b.dk'})
        self.assertEqual(done['status'], 'complete')

    def test_lone_survivor_of_clarify_gets_faq_confirm(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        result = self.ask()
        self.assertEqual((result['status'], result['response']), ('faq_confirm', 'Is this what you are asking?'))
        self.assertEqual([c['candidate_key'] for c in result['candidates']], ['FAQ_21'])
        self.assertNotIn('answered', result)
        self.assertNotIn('FAQ_Answered', [e for e, _ in self.dcr.executed])
        self.assertEqual(self.state['application_match']['kind'], 'confirm')

    def test_confirm_yes_answers_and_logs_accepted(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        asked = self.ask()
        with self.logged() as lines:
            result = app.confirm(self.state, {'match_id': asked['match_id'], 'candidate_key': 'FAQ_21'})
        self.assertEqual((result['faq_id'], result['answered']), ('FAQ_21', True))
        self.assertIn(('FAQ_Answered', 'FAQ_21: Question FAQ_21?'), self.dcr.executed)
        reaction = lines('faq_reaction')[0]
        self.assertEqual((reaction['interface'], reaction['outcome'], reaction['next_action'], reaction['faq_id']),
                         ('panel', 'confirm', 'accepted', 'FAQ_21'))

    def test_confirm_no_counts_as_miss_and_logs_rejected(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        with self.logged() as lines:
            first = app.ask(self.state, {'message': 'q1?'})
            self.assertEqual(app.confirm(self.state, {'match_id': first['match_id'],
                                                      'candidate_key': 'none'})['status'], 'faq_none')
            second = app.ask(self.state, {'message': 'q2?'})
            result = app.confirm(self.state, {'match_id': second['match_id'], 'candidate_key': 'none'})
        self.assertNotIn('handover', result)      # this graph has no Help_Escalate event
        self.assertTrue(self.state['outcome']['handover_shown'])     # the second miss reached the limit
        self.assertEqual([r['next_action'] for r in lines('faq_reaction')], ['rejected', 'rejected'])
        self.assertNotIn('FAQ_Answered', [e for e, _ in self.dcr.executed])

    def test_panel_logs_outcome_and_reaction_without_text(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        with self.logged() as lines:
            asked = self.ask()
            app.confirm(self.state, {'match_id': asked['match_id'], 'candidate_key': 'FAQ_21'})
        outcome, reaction = lines('faq_outcome')[0], lines('faq_reaction')[0]
        self.assertEqual((outcome['interface'], outcome['outcome'], outcome['outcome_row'], outcome['via']),
                         ('panel', 'confirm', 6, 'typed'))
        self.assertEqual(outcome['faq_ids'], ['FAQ_21'])
        self.assertEqual(reaction['turn'], outcome['turn'])      # the turn of the prompt, not of the reply
        raw = '\n'.join(json.dumps(r) for r in lines('faq_outcome', 'faq_reaction'))
        for text in (QUESTION, 'Question FAQ_21?', 'Answer FAQ_21'):
            self.assertNotIn(text, raw)

    def test_related_click_that_brings_back_a_different_faq_is_confirmed(self):
        self.dcr.api = single('FAQ_31', 'Other question?')
        result = app.ask(self.state, {'related': 'FAQ_P02'})
        self.assertEqual(result['status'], 'faq_confirm')
        self.assertNotIn('answered', result)

    def test_related_only_single_match_returns_faq_related(self):
        self.dcr.api = single()
        self.tiers.side_effect = lambda m, c, **k: {'answers': [], 'related': ['FAQ_31']}
        result = self.ask()
        self.assertEqual(result['status'], 'faq_related')
        self.assertIs(result['related'], True)
        self.assertEqual(result['response'], 'No FAQ answers exactly this. This one is on the same topic and may help:')
        self.assertEqual([c['candidate_key'] for c in result['candidates']], ['FAQ_31'])
        self.assertNotIn('answered', result)
        self.assertNotIn('FAQ_Answered', [e for e, _ in self.dcr.executed])
        chosen = app.confirm(self.state, {'match_id': result['match_id'], 'candidate_key': 'FAQ_31'})
        self.assertEqual((chosen['faq_id'], chosen['answered']), ('FAQ_31', True))

    def test_relevance_unavailable_never_answers_in_the_panel(self):
        self.dcr.api = single()
        self.tiers.side_effect = llm.LLMError('down')
        result = self.ask()
        self.assertEqual(result['status'], 'faq_related')
        self.assertNotIn('answered', result)

    def test_related_offer_of_several_uses_the_plural_text(self):
        self.dcr.api = clarify()
        self.tiers.side_effect = lambda m, c, **k: {'answers': [], 'related': ['FAQ_11', 'FAQ_21']}
        result = self.ask()
        self.assertEqual((result['status'], result['response']),
                         ('faq_related', 'No FAQ answers exactly this. These are on the same topic and may help:'))
        self.assertEqual([c['candidate_key'] for c in result['candidates']], ['FAQ_11', 'FAQ_21'])

    def test_several_matches_offer_a_choice(self):
        self.dcr.api = clarify()
        result = self.ask()
        self.assertEqual(result['status'], 'faq_clarify')
        self.assertEqual([c['candidate_key'] for c in result['candidates']], ['FAQ_11', 'FAQ_21', 'FAQ_99'])

    def test_relevance_check_can_empty_the_result(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: []
        result = self.ask()
        self.assertEqual(result['status'], 'faq_no_match')
        self.assertEqual(result['response'], 'No FAQ fits.')

    def test_no_match_text_comes_from_dcr(self):
        self.dcr.api = dict(decision='no_match')
        result = self.ask()
        self.assertEqual((result['status'], result['response']), ('faq_no_match', 'No FAQ fits.'))

    def test_search_down_is_reported_and_field_stays(self):
        self.dcr.api = None
        result = self.ask()
        self.assertEqual((result['status'], result['response']), ('faq_unavailable', 'Search down.'))
        self.assertEqual(self.state['application_prompt']['field']['id'], 'Form0:Email')

    def test_application_marking_change_is_refused(self):
        self.dcr.api = single()
        original = self.dcr.execute

        def leaky(state, eid, value, comment='', role=None):
            done = original(state, eid, value, comment, role)
            if eid == 'FAQ_UserQuestion':
                self.dcr.events['Form0:Email']['value'] = 'changed'
            return done
        rt.repo.execute_raw_event.side_effect = leaky
        with self.assertRaises(app.ApplicationError):
            self.ask()

    def test_graph_without_retrieval_is_refused(self):
        del self.dcr.events['FAQ_UserQuestion']
        with self.assertRaises(app.ApplicationError):
            self.ask()

    def test_stale_or_unknown_choice_is_refused(self):
        self.dcr.api = clarify()
        asked = self.ask()
        with self.assertRaises(app.ApplicationError):
            app.confirm(self.state, {'match_id': 'old', 'candidate_key': 'FAQ_11'})
        with self.assertRaises(app.ApplicationError):
            app.confirm(self.state, {'match_id': asked['match_id'], 'candidate_key': 'FAQ_00'})

    def test_question_and_answer_text_are_never_logged(self):
        self.dcr.api = single()
        with self.assertLogs(level=logging.DEBUG) as logs:
            self.ask()
        joined = '\n'.join(logs.output)
        self.assertNotIn(QUESTION, joined)
        self.assertNotIn('Para one', joined)

    def test_message_length_is_bounded(self):
        for bad in ('', '   ', 'x' * 2001, None):
            with self.assertRaises(app.ApplicationError):
                app.ask(self.state, {'message': bad})


if __name__ == '__main__':
    unittest.main()


class HelpPanelContextTests(unittest.TestCase):
    """Field card, click-scoped search, gated rewrite and handover (graph with field help and Help_* events)."""

    def setUp(self):
        from tests.test_retrieval_runtime import ev
        self.dcr = FakeDCR()
        self.dcr.events['Form0:Email'].update(
            included=True, enabled=True, label='Your email?',
            tags='ApplicationField,Topic:applying_decisions_and_help,HelpFAQ:FAQ_P02,HelpFAQ:FAQ_P07',
            description='<p>Use a fictional address.</p>')
        self.dcr.events['Help_Escalate'] = ev('Help_Escalate', dtype='choice', tags='FAQEscalation',
                                              choice='Asked (1), Misses (2), Deadline (3), Distress (4)')
        self.dcr.events['Help_Handover'] = ev('Help_Handover', tags='FAQHandover',
                                              description='<p>Use the contact options on SU.dk.</p>')
        original = self.dcr.execute

        def execute(state, eid, value, comment='', role=None):
            done = original(state, eid, value, comment, role)
            if done and eid == 'Help_Escalate':
                self.dcr.events['Help_Handover']['pending'] = True
            return done
        self.state = {'graph_id': 1, 'simulation_id': 2}
        patch.object(rt.repo, 'get_raw_events', side_effect=self.dcr.read).start()
        patch.object(rt.repo, 'execute_raw_event', side_effect=execute).start()
        self.enabled = patch.object(llm, 'decisions_enabled', return_value=False).start()
        patch.object(llm, 'relevant', side_effect=lambda m, c, **k: [x['id'] for x in c]).start()
        patch.object(llm, 'relevant_decisions', side_effect=lambda m, c, **k: [x['id'] for x in c]).start()
        patch_tiers()
        self.triage = patch.object(llm, 'triage', return_value=dict(
            value='1', reply_value=None, search_query=None, reason='a question')).start()
        self.signals = patch.object(llm, 'panel_signals_decisions',
                                    return_value={'contextual': 0.1, 'distress': 0.1}).start()
        self.rewrite = patch.object(llm, 'rewrite', return_value='Which email address should I give?').start()
        self.addCleanup(patch.stopall)
        self.first = app.start(self.state)
        self.dcr.api = single()

    def searched(self):
        return [v for eid, v in self.dcr.executed if eid == 'FAQ_UserQuestion']

    def escalations(self):
        return [v for eid, v in self.dcr.executed if eid == 'Help_Escalate']

    def test_field_carries_its_help_card_from_dcr(self):
        card = self.first['field']['help']
        self.assertEqual(card['html'], '<p>Use a fictional address.</p>')
        self.assertEqual(card['topic'], 'applying_decisions_and_help')
        self.assertEqual([r['id'] for r in card['related']], ['FAQ_P02', 'FAQ_P07'])
        self.assertTrue(all(r['question'] for r in card['related']))

    def test_field_scope_tries_the_typed_words_first_and_composes_only_without_a_linked_faq(self):
        # FAQ_31 is not linked to the Email field (HelpFAQ FAQ_P02, FAQ_P07): second search with the label.
        # The composed query is an internal search aid: it is not shown as "Understood as".
        result = app.ask(self.state, {'message': 'what do I put here?', 'scope': 'field'})
        self.assertEqual(self.searched(), ['what do I put here?', 'Your email? what do I put here?'])
        self.assertNotIn('searched_for', result)
        self.assertEqual(result['faq_id'], 'FAQ_31')
        self.assertIn('what do I put here?', self.dcr.comments['FAQ_UserQuestion'])
        self.signals.assert_not_called()
        self.rewrite.assert_not_called()

    def test_field_scope_keeps_the_typed_search_when_a_linked_faq_comes_back(self):
        self.dcr.api = single('FAQ_P02', 'How can I follow my case?')
        result = app.ask(self.state, {'message': 'will you write to me here?', 'scope': 'field'})
        self.assertEqual(self.searched(), ['will you write to me here?'])
        self.assertNotIn('searched_for', result)
        self.assertEqual(result['faq_id'], 'FAQ_P02')

    def test_field_scope_composes_after_a_typed_miss_but_not_when_search_is_down(self):
        self.dcr.api = dict(decision='no_match')
        app.ask(self.state, {'message': 'hmm?', 'scope': 'field'})
        self.assertEqual(len(self.searched()), 2)
        self.dcr.api = None
        app.ask(self.state, {'message': 'hmm again?', 'scope': 'field'})
        self.assertEqual(len(self.searched()), 3)   # unavailable: no second search

    def test_unknown_scope_is_refused(self):
        with self.assertRaises(app.ApplicationError):
            app.ask(self.state, {'message': 'x?', 'scope': 'faq', 'faq_id': 'FAQ_21'})

    def test_related_click_searches_the_title_as_is_and_answers_it_directly(self):
        self.dcr.api = clarify()
        self.dcr.api.update(option2_id='FAQ_P02', option2_question=app.faq_titles()['FAQ_P02'])
        result = app.ask(self.state, {'related': 'FAQ_P02'})
        self.assertEqual(self.searched(), [app.faq_titles()['FAQ_P02']])
        self.assertNotIn('searched_for', result)
        self.assertEqual((result['faq_id'], result['answered']), ('FAQ_P02', True))
        with self.assertRaises(app.ApplicationError):
            app.ask(self.state, {'related': 'FAQ_00'})

    def test_unscoped_message_is_rewritten_only_when_classified_contextual(self):
        self.enabled.return_value = True
        app.ask(self.state, {'message': 'Who can get it?'})
        self.rewrite.assert_not_called()
        self.signals.return_value = {'contextual': 0.9, 'distress': 0.1}
        result = app.ask(self.state, {'message': 'what goes here'})
        self.assertEqual(self.searched()[-1], 'Which email address should I give?')
        self.assertEqual(result['searched_for'], 'Which email address should I give?')
        self.assertIs(self.rewrite.call_args.kwargs['prompt'], llm.PANEL_REWRITE_PROMPT)
        self.assertEqual(self.rewrite.call_args.args[1]['current_question'], 'Your email?')
        self.assertEqual(self.rewrite.call_args.args[1]['about_question'], 'Use a fictional address.')
        self.assertNotIn('answers', self.rewrite.call_args.args[1])

    def test_without_decisions_there_is_no_classifier_and_no_rewrite(self):
        app.ask(self.state, {'message': 'what goes here'})
        self.signals.assert_not_called()
        self.rewrite.assert_not_called()
        self.assertEqual(self.searched(), ['what goes here'])

    def test_person_request_hands_over_without_searching(self):
        result = app.ask(self.state, {'message': 'Can I talk to a real person please'})
        self.assertEqual(result['status'], 'handover')
        self.assertEqual(result['handover'], {'reason': 1, 'html': '<p>Use the contact options on SU.dk.</p>'})
        self.assertEqual(self.searched(), [])
        self.assertEqual(self.escalations(), ['1'])

    def test_deadline_hands_over_once_and_still_searches(self):
        first = app.ask(self.state, {'message': 'I missed the appeal deadline, what now?'})
        self.assertEqual(first['handover']['reason'], 3)
        self.assertEqual(len(self.searched()), 1)
        second = app.ask(self.state, {'message': 'Is the appeal deadline 4 weeks?'})
        self.assertNotIn('handover', second)
        self.assertEqual(self.escalations(), ['3'])

    def test_distress_classifier_hands_over(self):
        self.enabled.return_value = True
        self.signals.return_value = {'contextual': 0.1, 'distress': 0.85}
        result = app.ask(self.state, {'message': 'nothing works and I am so stressed about this'})
        self.assertEqual(result['handover']['reason'], 4)

    def test_two_misses_hand_over_and_an_answer_resets_the_count(self):
        self.dcr.api = dict(decision='no_match')
        self.assertNotIn('handover', app.ask(self.state, {'message': 'xyz?'}))
        self.assertEqual(app.ask(self.state, {'message': 'abc?'})['handover']['reason'], 2)
        self.dcr.api = single()
        app.ask(self.state, {'message': 'refused?'})
        self.assertEqual(self.state['outcome'], dict(clarified=0, misses=0, handover_shown=True))

    def test_none_of_these_counts_as_a_miss(self):
        self.dcr.api = clarify()
        asked = app.ask(self.state, {'message': 'q1?'})
        self.assertEqual(app.confirm(self.state, {'match_id': asked['match_id'], 'candidate_key': 'none'})['status'],
                         'faq_none')
        asked = app.ask(self.state, {'message': 'q2?'})
        second = app.confirm(self.state, {'match_id': asked['match_id'], 'candidate_key': 'none'})
        self.assertEqual(second['handover']['reason'], 2)

    def test_unreadable_answer_twice_hands_over(self):
        issued = self.state['application_prompt']
        issued['field'] = dict(issued['field'], type='int')
        with patch.object(app.openchat, 'interpret', return_value=(False, None, 'Not a number.')):
            for n in range(2):
                result = app.interpret(self.state, {'prompt_id': issued['ticket'], 'message': 'lots'})
        self.assertEqual(result['handover']['reason'], 2)

    def test_handover_leaves_the_application_alone_and_button_always_works(self):
        before = app.application_marking(self.dcr.read(self.state))
        self.assertTrue(app.escalate(self.state, 1, 'button'))
        self.assertTrue(app.escalate(self.state, 1, 'button'))
        self.assertEqual(app.application_marking(self.dcr.read(self.state)), before)
        self.assertEqual(self.escalations(), ['1', '1'])

    def test_field_scope_keeps_an_unlinked_typed_result_when_the_composed_search_finds_nothing(self):
        answers = iter([clarify(), dict(decision='no_match')])
        original = self.dcr.execute

        def execute(state, eid, value, comment='', role=None):
            if eid == 'FAQ_UserQuestion':
                self.dcr.api = next(answers)
            return original(state, eid, value, comment, role)
        rt.repo.execute_raw_event.side_effect = execute
        result = app.ask(self.state, {'message': 'can I change it later?', 'scope': 'field'})
        self.assertEqual(len(self.searched()), 2)
        self.assertEqual(result['status'], 'faq_clarify')

    def test_unrelated_message_is_not_rewritten_into_a_field_question(self):
        # Eval 2026-10-09 (o03): a weather question was rewritten into a field question and answered.
        self.enabled.return_value = True
        self.dcr.api = dict(decision='no_match')
        message = 'is it going to rain tomorrow?'
        result = app.ask(self.state, {'message': message, 'scope': 'field'})
        self.assertEqual(self.searched(), [message, f'Your email? {message}'])
        self.rewrite.assert_not_called()
        self.assertEqual((result['status'], result['response']), ('faq_no_match', 'No FAQ fits.'))
        self.assertNotIn('searched_for', result)
        self.assertEqual(self.state['outcome']['misses'], 1)

    def test_fallback_rewrite_flag_restores_the_old_order(self):
        self.enabled.return_value = True
        answers = iter([dict(decision='no_match'), dict(decision='no_match'), single('FAQ_P07', 'Q P07?')])
        original = self.dcr.execute

        def execute(state, eid, value, comment='', role=None):
            if eid == 'FAQ_UserQuestion':
                self.dcr.api = next(answers)
            return original(state, eid, value, comment, role)
        rt.repo.execute_raw_event.side_effect = execute
        with patch.dict('os.environ', {'PANEL_FALLBACK_REWRITE': '1'}):
            result = app.ask(self.state, {'message': 'what if I have two?', 'scope': 'field'})
        self.assertEqual(self.searched(), ['what if I have two?', 'Your email? what if I have two?',
                                           'Which email address should I give?'])
        self.assertEqual(result['searched_for'], 'Which email address should I give?')
        self.assertEqual(result['faq_id'], 'FAQ_P07')

    def test_no_rewrite_when_the_typed_search_already_found_something(self):
        self.enabled.return_value = True
        self.dcr.api = single('FAQ_P02', 'Q P02?')
        app.ask(self.state, {'message': 'will you write to me here?', 'scope': 'field'})
        self.rewrite.assert_not_called()
        self.assertEqual(len(self.searched()), 1)

    def test_context_dependent_message_searches_only_the_rewrite_and_judges_against_it(self):
        self.enabled.return_value = True
        self.signals.return_value = {'contextual': 0.9, 'distress': 0.1}
        relevance = llm.relevant_decisions
        result = app.ask(self.state, {'message': 'would the hours matter here?', 'scope': 'field'})
        self.assertEqual(self.searched(), ['Which email address should I give?'])
        self.assertEqual(relevance.call_args.args[0], 'Which email address should I give?')
        self.assertEqual(result['searched_for'], 'Which email address should I give?')

    def test_composed_search_is_judged_against_the_applicants_words(self):
        self.enabled.return_value = True
        app.ask(self.state, {'message': 'what do I put here?', 'scope': 'field'})
        judged = [c.args[0] for c in llm.relevant_decisions.call_args_list]
        self.assertTrue(judged)
        self.assertTrue(all(j == 'what do I put here?' for j in judged))

    def test_same_faq_wording_depends_on_tier(self):
        self.enabled.return_value = True
        first = app.ask(self.state, {'message': 'what about my previous work?'})
        self.assertEqual(first['faq_id'], 'FAQ_31')
        self.signals.return_value = {'contextual': 0.9, 'distress': 0.1}
        second = app.ask(self.state, {'message': 'and would the hours matter?'})
        self.assertEqual((second['status'], second['same_faq']), ('faq_no_match', True))
        self.assertEqual(second['response'], 'The answer above already covers this.')
        self.assertIn('searched_for', second)
        # Same FAQ again, but the check only calls it the same topic: the closest the FAQ has.
        llm.relevance_tiers_decisions.side_effect = lambda m, c, **k: {'answers': [], 'related': [x['id'] for x in c]}
        third = app.ask(self.state, {'message': 'and would the hours matter?'})
        self.assertTrue(third['same_faq'])
        self.assertIn('does not say more', third['response'])

    def test_same_faq_is_logged_with_the_outcome_it_would_have_had(self):
        self.enabled.return_value = True
        app.ask(self.state, {'message': 'what about my previous work?'})
        self.signals.return_value = {'contextual': 0.9, 'distress': 0.1}
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with patch.object(app.ilog, 'DIRECTORY', folder), patch.object(app.ilog, 'ENABLED', True):
            app.ilog.start(self.state, '1', '2', interface='panel')
            self.state['interaction']['shown'] = {}
            app.ask(self.state, {'message': 'and would the hours matter?'})
            path = Path(folder) / f"{self.state['interaction']['id']}.jsonl"
            rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
        outcome = [r for r in rows if r['kind'] == 'faq_outcome']
        self.assertEqual(len(outcome), 1)
        self.assertEqual((outcome[0]['outcome'], outcome[0]['outcome_row'], outcome[0]['same_faq'],
                          outcome[0]['faq_ids'], outcome[0]['via']), ('answer', 4, True, ['FAQ_31'], 'rewritten'))

    def test_rewrite_context_carries_the_last_answer_and_previous_question(self):
        self.enabled.return_value = True
        app.ask(self.state, {'message': 'what about my previous work?'})
        self.signals.return_value = {'contextual': 0.9, 'distress': 0.1}
        app.ask(self.state, {'message': 'and would the hours matter?'})
        context = self.rewrite.call_args.args[1]
        self.assertEqual(context['previous_question'], 'what about my previous work?')
        self.assertIn('answer begins: Para one.', context['last_answered_faq'])


class ComposedEvalDataTests(unittest.TestCase):
    """The eval file stays consistent with the FAQ records and the graph (no model needed)."""

    def test_cases_reference_existing_fields_and_faqs(self):
        import json
        from pathlib import Path
        from evals.eval_composed import compose, field_labels, field_links
        root = Path(__file__).resolve().parent.parent
        cases = json.loads((root / 'evals/cases/eval_composed_queries.json').read_text())['queries']
        titles, labels, links = app.faq_titles(), field_labels(), field_links()
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        for c in cases:
            with self.subTest(c['id']):
                self.assertEqual(c['scope'], 'field')
                self.assertIn(c['target'], labels)
                self.assertTrue(links.get(c['target']), 'field has linked FAQs in the graph')
                self.assertTrue(set(c['expected']) <= set(titles))
                self.assertEqual(compose(c, labels), f"{labels[c['target']]} {c['message']}")


class EvalPolicyTests(unittest.TestCase):
    """eval_composed scores the app column with the host's rule (no model needed)."""

    def setUp(self):
        from types import SimpleNamespace
        from evals.calibrate_thresholds import decide
        from evals import eval_composed as ev
        self.ev, self.decide = ev, decide
        self.settings = SimpleNamespace(single=0.8, minimum=0.5, margin=0.12, maximum=3)
        self.case = dict(scope='field', target='F', message='what is this?', expected=['FAQ_36'])

    def run_case(self, typed, composed):
        retrieve = lambda q: typed if q == self.case['message'] else composed
        return self.ev.run_case(self.case, retrieve, {'F': 'Label?'}, {'F': ['FAQ_36', 'FAQ_37']},
                                self.settings, self.decide)

    def test_app_keeps_the_typed_search_when_a_linked_faq_is_shown(self):
        r = self.run_case(typed=[['FAQ_37', 0.6], ['FAQ_02', 0.55]], composed=[['FAQ_36', 0.76]])
        self.assertEqual(r['note'], '')
        self.assertEqual(r['app'][0], ('clarify_match', ['FAQ_37', 'FAQ_02']))

    def test_app_uses_the_composed_search_when_no_linked_faq_is_shown(self):
        r = self.run_case(typed=[['FAQ_02', 0.58], ['FAQ_01', 0.55]], composed=[['FAQ_36', 0.76], ['FAQ_37', 0.7]])
        self.assertEqual(r['note'], 'composed')
        self.assertTrue(self.ev.score(*r['app'][0], self.case['expected'])['top1'])

    def test_scores(self):
        self.assertEqual(self.ev.score('single_match', ['X'], ['Y']),
                         dict(hit=False, top1=False, single_wrong=True, none=False))
        self.assertEqual(self.ev.score('clarify_match', ['X', 'Y'], ['Y']),
                         dict(hit=True, top1=False, single_wrong=False, none=False))


class PanelFake(TurnFake):
    """The panel's graph after spec 03: Help_* search events, Session_Panel, TurnOutcome and the handover events on top
    of the chat fake (TurnFake) from test_retrieval_runtime."""

    def __init__(self, **kwargs):
        from tests.test_retrieval_runtime import ev
        super().__init__(**kwargs)
        self.events['Form0:Email'].update(included=True, enabled=True, label='Your email?',
                                          tags='ApplicationField,HelpFAQ:FAQ_P02')
        self.events.pop('Session_Chat', None)
        self.events['Session_Panel'] = ev('Session_Panel')
        self.events['Help_UserQuestion'] = ev('Help_UserQuestion', dtype='text', tags='FAQRetrieval', included=False)
        self.events['Help_RetrievalOk'] = ev('Help_RetrievalOk', roles='System', dtype='text', tags='FAQRetrieval')
        self.events['Help_RetrievalUnavailable'] = ev('Help_RetrievalUnavailable', tags='FAQAnswer,FAQRetrieval',
                                                      description='<p>Search down.</p>')

    def execute(self, state, eid, value, comment='', role=None):
        done = super().execute(state, eid, value, comment, role)
        if done and eid == 'FAQ_Triage':
            self.events['Help_UserQuestion'].update(included=value == '1', enabled=value == '1')
        if done and eid == 'Help_UserQuestion':
            self.events['Help_RetrievalOk'].update(executed='now', value=json.dumps(json.dumps(self.api)))
        return done


class PanelOutcomeTests(unittest.TestCase):
    """Spec 03 section 5.5, panel rows. Fake DCR with TurnOutcome and the Help_* events; no model, no network."""

    def build(self, **kwargs):
        self.dcr = PanelFake(**kwargs)
        self.state = {'graph_id': 1, 'simulation_id': 2}
        patch.object(rt.repo, 'get_raw_events', side_effect=self.dcr.read).start()
        patch.object(rt.repo, 'execute_raw_event', side_effect=self.dcr.execute).start()
        patch.object(llm, 'decisions_enabled', return_value=False).start()
        self.relevant = patch.object(llm, 'relevant', side_effect=lambda m, c, **k: [x['id'] for x in c]).start()
        patch_tiers()
        self.triage = patch.object(llm, 'triage', return_value=dict(
            value='1', reply_value=None, search_query=None, reason='a question')).start()
        self.pick = patch.object(llm, 'pick_followup', return_value=None).start()
        patch.dict('os.environ', {'OUTCOME_MODE': 'code'}).start()
        for name in ('FOLLOWUP_SURFACE', 'PANEL_TRIAGE'):
            import os
            os.environ.pop(name, None)
        self.addCleanup(patch.stopall)
        self.first = app.start(self.state)
        self.dcr.api = single()

    def setUp(self):
        self.build()

    def ask(self, message='refused without assessment?', **extra):
        return app.ask(self.state, dict(message=message, **extra))

    def names(self, eid=None):
        return self.dcr.names(eid)

    def test_start_executes_session_panel(self):
        self.assertEqual(self.names('Session_Panel'), ['Session_Panel'])
        self.assertTrue(self.state['panel_search'])
        self.assertEqual(self.state['outcome'], dict(clarified=0, misses=0, handover_shown=False))

    def test_start_without_session_event_executes_nothing(self):
        patch.stopall()
        self.dcr = None
        self.build()
        self.dcr.events.pop('Session_Panel')
        state = {'graph_id': 1, 'simulation_id': 2}
        before = len(self.dcr.executed)
        app.start(state)
        self.assertEqual(self.names('Session_Panel'), ['Session_Panel'])      # only the one from build()
        self.assertEqual(len(self.dcr.executed), before)

    def test_panel_uses_help_search_events(self):
        result = self.ask()
        self.assertTrue(result['answered'])
        self.assertIn('Help_UserQuestion', self.names())
        self.assertNotIn('FAQ_UserQuestion', self.names())

    def test_unscoped_message_goes_through_triage_with_values_1_and_5(self):
        self.ask()
        self.assertEqual([v['value'] for v in self.triage.call_args.args[2]], ['1', '5'])
        self.assertIn(('FAQ_Triage', '1'), self.dcr.executed)
        self.assertEqual(self.dcr.comments['FAQ_Triage'], 'a question')

    def test_out_of_scope_returns_faq_out_of_scope(self):
        self.triage.return_value = dict(value='5', reply_value=None, search_query=None, reason='weather')
        result = self.ask('what is the weather?')
        self.assertEqual((result['status'], result['response']), ('faq_out_of_scope', 'Outside scope.'))
        self.assertIn(('FAQ_Triage', '5'), self.dcr.executed)
        self.assertNotIn('Help_UserQuestion', self.names())
        self.assertIn(('TurnOutcome', 'out_of_scope'), self.dcr.executed)
        self.assertEqual(self.names('FAQ_OutOfScope'), ['FAQ_OutOfScope'])
        self.assertEqual(self.state['application_prompt']['field']['id'], 'Form0:Email')   # the form is untouched

    def test_related_click_and_field_scope_skip_triage(self):
        self.ask(related='FAQ_31')
        self.ask('what do I put here?', scope='field')
        self.triage.assert_not_called()
        self.assertEqual([v for e, v in self.dcr.executed if e == 'FAQ_Triage'][:1], ['1'])

    def test_related_click_answers_without_the_table(self):
        result = self.ask(related='FAQ_31')
        self.assertTrue(result['answered'])
        self.assertNotIn('TurnOutcome', self.names())

    def test_unsure_is_treated_as_in_scope(self):
        self.triage.return_value = dict(value='5', reply_value=None, search_query=None, reason='r', unsure=True)
        result = self.ask()
        self.assertTrue(result['answered'])
        self.assertIn('Help_UserQuestion', self.names())

    def test_triage_down_searches(self):
        self.triage.side_effect = llm.LLMError('down')
        self.assertTrue(self.ask()['answered'])

    def test_panel_triage_flag_off(self):
        with patch.dict('os.environ', {'PANEL_TRIAGE': '0'}):
            result = self.ask()
        self.triage.assert_not_called()
        self.assertTrue(result['answered'])
        self.assertIn(('FAQ_Triage', '1'), self.dcr.executed)

    def test_panel_fires_determination_after_answer(self):
        result = self.ask()
        self.assertEqual(result['prompt']['kind'], 'determination')
        self.assertEqual(result['prompt']['text'], 'Ask Det31?')
        self.assertIn((SEL, '3'), self.dcr.executed)
        self.assertEqual(result['field']['id'], 'Form0:Email')

    def test_followup_surface_chat_asks_nothing_in_the_panel(self):
        with patch.dict('os.environ', {'FOLLOWUP_SURFACE': 'chat'}):
            result = self.ask()
        self.assertNotIn('prompt', result)
        self.assertNotIn(SEL, self.names())
        self.pick.assert_not_called()

    def test_determination_endpoint_leaves_application_unchanged(self):
        from flask import Flask
        shown = self.ask()
        store = {'sid': self.state}
        flask_app = Flask('t')
        app.install(flask_app, store, lambda: {})
        before = app.application_marking(app.fetch(self.state))
        response = flask_app.test_client().post('/application/determination', headers={'X-Session-ID': 'sid'},
                                                json={'retrieval_prompt_id': shown['prompt']['id'], 'value': 'true'})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual((body['status'], body['outcomes'], body['answered']['value']),
                         ('determination_result', ['<p>Det31 yes.</p>'], 'Yes'))
        self.assertIn(('Det31_Yes', ''), self.dcr.executed)
        self.assertEqual(app.application_marking(app.fetch(self.state)), before)
        again = flask_app.test_client().post('/application/determination', headers={'X-Session-ID': 'sid'},
                                             json={'retrieval_prompt_id': shown['prompt']['id'], 'value': 'true'})
        self.assertEqual(again.status_code, 400)     # the prompt was consumed

    def test_determination_rejects_an_unknown_value_and_a_stale_prompt(self):
        shown = self.ask()
        with self.assertRaises(app.ApplicationError):
            app.determination(self.state, {'retrieval_prompt_id': shown['prompt']['id'], 'value': 'maybe'})
        with self.assertRaises(app.ApplicationError):
            app.determination(self.state, {'retrieval_prompt_id': 'stale', 'value': 'true'})

    def test_a_new_question_drops_an_open_followup(self):
        shown = self.ask()
        self.ask('another question?', scope='field')
        with self.assertRaises(app.ApplicationError):
            app.determination(self.state, {'retrieval_prompt_id': shown['prompt']['id'], 'value': 'true'})

    def test_misses_use_outcome_counters(self):
        self.dcr.api = dict(decision='no_match')
        first = self.ask('xyz?')
        self.assertEqual(first['status'], 'faq_no_match')
        self.assertNotIn('handover', first)
        self.assertEqual(self.state['outcome']['misses'], 1)
        second = self.ask('abc?')
        self.assertEqual(second['handover']['reason'], 2)
        self.assertEqual(second['response'], 'No FAQ fits.')
        self.assertNotIn('handover', self.ask('def?'))          # once per session
        self.assertEqual(self.names('Help_Escalate'), ['Help_Escalate'])
        self.dcr.api = single()
        self.ask('refused?')
        self.assertEqual(self.state['outcome']['misses'], 0)
        self.assertEqual(self.dcr.events['Help_Handover']['pending'], False)

    def test_deadline_handover_and_second_miss_do_not_leave_the_handover_pending(self):
        self.dcr.api = dict(decision='no_match')
        self.ask('xyz?')
        second = self.ask('is the deadline 4 weeks?')
        self.assertEqual(second['handover']['reason'], 3)
        self.assertEqual(self.dcr.events['Help_Handover']['pending'], False)
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        self.assertEqual(self.ask('medical docs?')['status'], 'faq_confirm')    # the next turn still settles

    def test_person_request_is_settled_as_handover_reason_1(self):
        result = self.ask('I want to talk to a person')
        self.assertEqual((result['status'], result['handover']['reason']), ('handover', 1))
        self.assertIn(('TurnOutcome', 'handover'), self.dcr.executed)
        self.assertNotIn('Help_UserQuestion', self.names())

    def test_second_list_after_clarify_is_row_8_with_the_clarify_text(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_11', 'FAQ_21']
        first = self.ask('medical docs?')
        second = self.ask('medical docs again?')
        self.assertEqual((first['status'], second['status']), ('faq_clarify', 'faq_clarify'))
        self.assertEqual([v for e, v in self.dcr.executed if e == 'TurnOutcome'], ['clarify', 'offer'])

    def test_confirm_text_comes_from_dcr_event(self):
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        self.assertEqual(self.ask('medical docs?')['response'], 'Confirm text from DCR.')

    def test_confirm_text_falls_back_to_the_host_string(self):
        patch.stopall()
        self.build(turn_outcome=False)
        self.dcr.api = clarify()
        self.relevant.side_effect = lambda m, c, **k: ['FAQ_21']
        self.assertEqual(self.ask('medical docs?')['response'], 'Is this what you are asking?')
        self.assertNotIn('TurnOutcome', self.names())
