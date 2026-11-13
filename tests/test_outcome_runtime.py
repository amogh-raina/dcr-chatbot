"""Spec 03 T5: writing the outcome into DCR (code, shadow, dcr) against a fake DCR. No model, no network."""
import copy
import os
import unittest
from unittest.mock import patch

import dcrai.chat.outcome as oc
import dcrai.chat.outcome_runtime as ort

GATES = ort.GATES


def ev(eid, roles='Chatbot', dtype='label', included=True, description='', choice='', tags='', pending=False):
    return dict(id=eid, roles=roles, dataType=dtype, tags=tags, included=included, enabled=included,
                pending=pending, executed=None, value='', label=eid, description=description,
                choiceValues=choice, sequence=0)


class FakeDCR:
    """Just enough of the outcome part of the graph: TurnOutcome with guarded responses and co-responses (so exactly
    one outcome event is pending after it), and the DMN chain TurnStart, four gates, OutcomeTable, TurnResult."""

    def __init__(self, table=True, result=None, leaky=False, dictionary=None, turn_outcome=True, enabled=True,
                 fail=()):
        dictionary = list(oc.OUTCOMES) if dictionary is None else dictionary
        self.result, self.leaky, self.fail = result, leaky, set(fail)
        self.executed, self.gates = [], {}
        events = [ev(eid, description='<p>%s text.</p>' % eid) for eid in
                  ('Outcome_Answer', 'Outcome_Confirm', 'Outcome_Offer', 'Outcome_Clarify')]
        events += [ev('FAQ_NoMatch', description='<p>No FAQ fits.</p>', tags='FAQNoMatch'),
                   ev('FAQ_OutOfScope', description='<p>Outside scope.</p>', tags='FAQOutOfScope'),
                   ev('Help_Handover', description='<p>Talk to SU.</p>', tags='FAQHandover')]
        if turn_outcome:
            e = ev('TurnOutcome', dtype='choice', choice=', '.join('%s (%s)' % (v, v) for v in dictionary))
            e['included'] = e['enabled'] = enabled
            events.append(e)
        if table:
            events += [ev('TurnStart')] + [ev(g, dtype='choice') for g in GATES]
            events += [ev('OutcomeTable', roles='Robot', dtype='none'), ev('TurnResult')]
        self.events = {x['id']: x for x in events}

    def execute(self, state, eid, value, comment='', role=None):
        self.executed.append((eid, value, comment))
        if eid in self.fail:
            return False
        if eid == 'TurnStart':
            self.gates = {}
        elif eid in GATES:
            self.gates[eid] = value
            if len(self.gates) == len(GATES):
                self.events['TurnResult']['value'] = self.run_table()
        elif eid == 'TurnOutcome':
            for outcome, event_id in oc.OUTCOME_EVENT.items():
                self.events[event_id]['pending'] = outcome == value
            if self.leaky:
                self.events['Outcome_Answer']['pending'] = True
        elif eid in self.events:
            self.events[eid]['pending'] = False
        return True

    def run_table(self):
        if self.result is not None:
            return self.result
        scope, search, relevance, clarified = (self.gates[g] for g in GATES)
        row, out = oc.table(scope, search, relevance, int(clarified))
        return 'result %d:%s' % (row, out)

    def read(self, state=None):
        return {'events': copy.deepcopy(list(self.events.values()))}

    def names(self):
        return [x[0] for x in self.executed]


def run(fake, decision, mode='code', state=None, interface='chat'):
    state = {} if state is None else state
    with patch.dict(os.environ, {'OUTCOME_MODE': mode}), \
            patch('dcrai.dcr.dcr_repository.execute_raw_event', fake.execute), \
            patch('dcrai.dcr.dcr_repository.get_raw_events', fake.read):
        return ort.settle(state, fake.read(), decision, interface)


def confirm_decision(**kw):
    return oc.decide('in_scope', 'clarify_match', ['answers'], **kw)       # row 6


class SettleModes(unittest.TestCase):
    def test_code_mode_writes_only_turnoutcome(self):
        fake = FakeDCR()
        settled = run(fake, confirm_decision())
        self.assertEqual(fake.executed, [('TurnOutcome', 'confirm', 'row 6; source code; misses 0')])
        self.assertEqual((settled.source, settled.mismatch, settled.event_id, settled.dcr_result),
                         ('code', False, 'Outcome_Confirm', None))
        self.assertEqual(settled.decision.outcome, 'confirm')
        self.assertEqual(settled.text, '<p>Outcome_Confirm text.</p>')

    def test_default_mode_is_code(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('OUTCOME_MODE', None)
            self.assertEqual(ort.mode(), 'code')

    def test_unknown_mode_is_code_with_a_warning(self):
        with patch.dict(os.environ, {'OUTCOME_MODE': 'both'}):
            with self.assertLogs(ort.log, 'WARNING'):
                self.assertEqual(ort.mode(), 'code')

    def test_shadow_runs_table_and_keeps_code_result(self):
        fake = FakeDCR()
        settled = run(fake, confirm_decision(), 'shadow')
        self.assertEqual(fake.executed, [
            ('TurnStart', '', ''), ('GateScope', 'in_scope', ''), ('GateSearch', 'list', ''),
            ('GateRelevance', 'one_answers', ''), ('GateClarified', '0', ''),
            ('TurnOutcome', 'confirm', 'row 6; source code; misses 0')])
        self.assertEqual((settled.mismatch, settled.source, settled.dcr_result), (False, 'code', (6, 'confirm')))
        self.assertEqual(settled.decision.outcome, 'confirm')

    def test_shadow_mismatch_is_logged_and_code_wins(self):
        fake = FakeDCR(result='result 4:answer')
        with self.assertLogs(ort.log, 'WARNING') as logs:
            settled = run(fake, confirm_decision(), 'shadow')
        self.assertTrue(settled.mismatch)
        self.assertEqual(settled.dcr_result, (4, 'answer'))
        self.assertEqual(settled.decision.outcome, 'confirm')
        self.assertEqual(fake.executed[-1][:2], ('TurnOutcome', 'confirm'))
        self.assertTrue(any('mismatch' in line for line in logs.output))

    def test_clarified_is_sent_as_text(self):
        fake = FakeDCR()
        run(fake, oc.decide('in_scope', 'clarify_match', ['answers', 'answers'], clarified=1), 'shadow')
        self.assertIn(('GateClarified', '1', ''), fake.executed)
        self.assertEqual(fake.executed[-1][:2], ('TurnOutcome', 'offer'))

    def test_dcr_mode_agreeing_result_has_source_dcr(self):
        fake = FakeDCR()
        settled = run(fake, confirm_decision(), 'dcr')
        self.assertEqual((settled.source, settled.mismatch, settled.decision.outcome), ('dcr', False, 'confirm'))
        self.assertEqual(fake.executed[-1], ('TurnOutcome', 'confirm', 'row 6; source dcr; misses 0'))

    def test_dcr_mode_uses_table_result(self):
        fake = FakeDCR(result='result 7:clarify')
        settled = run(fake, confirm_decision(), 'dcr')
        self.assertEqual(fake.executed[-1], ('TurnOutcome', 'clarify', 'row 7; source dcr; misses 0'))
        self.assertEqual((settled.source, settled.mismatch), ('dcr', True))
        self.assertEqual((settled.decision.outcome, settled.decision.row, settled.decision.clarify_kind),
                         ('clarify', 7, 'candidates'))
        self.assertEqual(settled.event_id, 'Outcome_Clarify')

    def test_dcr_mode_applies_the_handover_rule_to_the_table_result(self):
        fake = FakeDCR(result='result 3:not_covered')
        state = {'outcome': {'clarified': 0, 'misses': 1, 'handover_shown': False}}
        settled = run(fake, confirm_decision(), 'dcr', state)
        self.assertEqual((settled.decision.outcome, settled.decision.row, settled.decision.handover_reason),
                         ('handover', 3, 2))
        self.assertEqual(fake.executed[-1], ('TurnOutcome', 'handover', 'row 3; source dcr; misses 1'))
        self.assertEqual(settled.event_id, 'Help_Handover')

    def test_dcr_mode_falls_back_when_unreadable(self):
        for bad in ('', 'garbage', 'result 12:answer', 'result 4:nonsense', 'result 4:handover'):
            with self.subTest(result=bad):
                fake = FakeDCR(result=bad)
                settled = run(fake, confirm_decision(), 'dcr')
                self.assertEqual((settled.source, settled.mismatch, settled.dcr_result), ('code', False, None))
                self.assertEqual(settled.decision.outcome, 'confirm')
                self.assertEqual(fake.executed[-1], ('TurnOutcome', 'confirm', 'row 6; source code; misses 0'))

    def test_dcr_mode_falls_back_when_a_gate_cannot_be_executed(self):
        fake = FakeDCR(fail={'GateSearch'})
        settled = run(fake, confirm_decision(), 'dcr')
        self.assertEqual((settled.source, settled.decision.outcome), ('code', 'confirm'))
        self.assertEqual(fake.names()[-1], 'TurnOutcome')

    def test_shadow_with_a_graph_without_the_table_events_still_writes_turnoutcome(self):
        fake = FakeDCR(table=False)
        settled = run(fake, confirm_decision(), 'shadow')
        self.assertEqual(fake.names(), ['TurnOutcome'])
        self.assertEqual((settled.source, settled.mismatch, settled.dcr_result), ('code', False, None))

    def test_dcr_mode_with_a_graph_without_the_table_events_uses_code(self):
        fake = FakeDCR(table=False)
        settled = run(fake, confirm_decision(), 'dcr')
        self.assertEqual((settled.source, settled.decision.outcome), ('code', 'confirm'))

    def test_explicit_request_for_a_person_does_not_run_the_table(self):
        fake = FakeDCR()
        settled = run(fake, oc.decide('in_scope', None, [], asked_person=True), 'shadow')
        self.assertEqual(fake.executed, [('TurnOutcome', 'handover', 'row none; source code; misses 0')])
        self.assertEqual((settled.decision.handover_reason, settled.event_id), (1, 'Help_Handover'))

    def test_every_outcome_leaves_exactly_its_event_pending(self):
        for outcome, event_id in oc.OUTCOME_EVENT.items():
            with self.subTest(outcome=outcome):
                fake = FakeDCR()
                decision = oc.Decision(outcome, None, outcome, None, None, None, ('in_scope', 'none', 'none', 0))
                settled = run(fake, decision)
                self.assertEqual((settled.source, settled.event_id), ('code', event_id))

    def test_comment_carries_the_miss_count(self):
        fake = FakeDCR()
        state = {'outcome': {'clarified': 0, 'misses': 3, 'handover_shown': True}}
        run(fake, oc.decide('in_scope', 'no_match', [], misses=3, handover_shown=True), 'code', state)
        self.assertEqual(fake.executed[-1], ('TurnOutcome', 'not_covered', 'row 3; source code; misses 3'))

    def test_other_events_pending_before_the_turn_are_not_a_problem_when_dcr_clears_them(self):
        fake = FakeDCR()
        fake.events['Outcome_Offer']['pending'] = True   # left over from the previous turn
        settled = run(fake, confirm_decision())
        self.assertEqual(settled.source, 'code')


class FailClosed(unittest.TestCase):
    def test_not_exactly_one_pending_fails_closed(self):
        fake = FakeDCR(leaky=True)
        with self.assertLogs(ort.log, 'ERROR'):
            settled = run(fake, confirm_decision())
        self.assertEqual(settled.source, 'failclosed')
        self.assertEqual((settled.decision.outcome, settled.decision.row), ('not_covered', 9))
        self.assertEqual(settled.event_id, 'FAQ_NoMatch')

    def test_turnoutcome_not_accepted_fails_closed(self):
        fake = FakeDCR(fail={'TurnOutcome'})
        with self.assertLogs(ort.log, 'ERROR'):
            settled = run(fake, confirm_decision())
        self.assertEqual((settled.source, settled.decision.outcome), ('failclosed', 'not_covered'))

    def test_nothing_pending_fails_closed(self):
        fake = FakeDCR()
        original = fake.execute

        def execute(state, eid, value, comment='', role=None):
            ok = original(state, eid, value, comment)
            if eid == 'TurnOutcome':
                for event_id in oc.OUTCOME_EVENT.values():
                    fake.events[event_id]['pending'] = False
            return ok
        fake.execute = execute
        with self.assertLogs(ort.log, 'ERROR'):
            settled = run(fake, confirm_decision())
        self.assertEqual(settled.source, 'failclosed')


class OldGraphs(unittest.TestCase):
    def test_graph_without_turnoutcome_is_untouched(self):
        for mode in ort.MODES:
            with self.subTest(mode=mode):
                fake = FakeDCR(turn_outcome=False)
                decision = confirm_decision()
                settled = run(fake, decision, mode)
                self.assertEqual(fake.executed, [])
                self.assertEqual(settled, ort.Settled(decision, 'code', None, None, False))

    def test_turnoutcome_with_wrong_dictionary_is_ignored(self):
        fake = FakeDCR(dictionary=list(oc.OUTCOMES[:-1]))
        decision = confirm_decision()
        with self.assertLogs(ort.log, 'ERROR'):
            settled = run(fake, decision, 'dcr')
        self.assertEqual(fake.executed, [])
        self.assertEqual(settled, ort.Settled(decision, 'code', None, None, False))

    def test_turnoutcome_with_an_extra_value_is_ignored(self):
        fake = FakeDCR(dictionary=list(oc.OUTCOMES) + ['maybe'])
        with self.assertLogs(ort.log, 'ERROR'):
            run(fake, confirm_decision())
        self.assertEqual(fake.executed, [])

    def test_turnoutcome_not_enabled_is_ignored(self):
        fake = FakeDCR(enabled=False)
        with self.assertLogs(ort.log, 'ERROR'):
            run(fake, confirm_decision())
        self.assertEqual(fake.executed, [])


class Parsing(unittest.TestCase):
    def test_parse_result(self):
        self.assertEqual(ort.parse_result('result 6:confirm'), (6, 'confirm'))
        self.assertEqual(ort.parse_result(' result 9:not_covered '), (9, 'not_covered'))
        for bad in ('6:confirm', '', 'result x', 'result 0:answer', 'result 10:answer', 'result 6:', None, 6,
                    'result 6:confirm extra', 'result 6:Confirm'):
            with self.subTest(value=bad):
                self.assertIsNone(ort.parse_result(bad))


class Texts(unittest.TestCase):
    def payload(self, *pairs):
        return {'events': [ev(eid, description=text) for eid, text in pairs]}

    def test_outcome_text_reads_the_dcr_event_or_none(self):
        with_event = self.payload(('Outcome_Confirm', '<p>Is this what you are asking?</p>'))
        self.assertEqual(ort.outcome_text(with_event, 6), 'Is this what you are asking?')
        self.assertIsNone(ort.outcome_text(self.payload(), 6))
        self.assertIsNone(ort.outcome_text(self.payload(('Outcome_Confirm', '')), 6))

    def test_outcome_text_by_row(self):
        payload = self.payload(('FAQ_OutOfScope', 'out'), ('FAQ_Msg_ScopeQuestion', 'scope?'), ('FAQ_NoMatch', 'none'),
                               ('Outcome_Answer', ''), ('Outcome_Offer', 'several'), ('FAQ_Msg_OfferOne', 'one'),
                               ('Outcome_Confirm', 'confirm'), ('Outcome_Clarify', 'clarify'))
        expected = {1: 'out', 2: 'scope?', 3: 'none', 4: None, 6: 'confirm', 7: 'clarify', 8: 'clarify', 9: 'none'}
        for row, text in expected.items():
            with self.subTest(row=row):
                self.assertEqual(ort.outcome_text(payload, row, 2), text)
        self.assertEqual(ort.outcome_text(payload, 5, 1), 'one')
        self.assertEqual(ort.outcome_text(payload, 5, 3), 'several')
        self.assertIsNone(ort.outcome_text(payload, None))

    def test_message_text_strips_markup_and_entities(self):
        payload = self.payload(('FAQ_Msg_Rephrase', '<p>Could you rephrase &amp; add more?</p>'))
        self.assertEqual(ort.message_text(payload, 'FAQ_Msg_Rephrase'), 'Could you rephrase & add more?')


class Handover(unittest.TestCase):
    def fake(self, escalate=True):
        fake = FakeDCR()
        if escalate:
            fake.events['Help_Escalate'] = ev('Help_Escalate', dtype='intchoice', tags='FAQEscalation')
        original = fake.execute

        def execute(state, eid, value, comment='', role=None):
            ok = original(state, eid, value, comment)
            if eid == 'Help_Escalate':
                fake.events['Help_Handover']['pending'] = True
            return ok
        fake.execute = execute
        return fake

    def call(self, fake, *args):
        with patch('dcrai.dcr.dcr_repository.execute_raw_event', fake.execute), \
                patch('dcrai.dcr.dcr_repository.get_raw_events', fake.read):
            return ort.handover({}, *args)

    def test_handover_executes_reads_and_acknowledges(self):
        fake = self.fake()
        result = self.call(fake, 2, 'two misses in a row')
        self.assertEqual(result, {'reason': 2, 'html': '<p>Talk to SU.</p>'})
        self.assertEqual(fake.executed, [('Help_Escalate', '2', 'two misses in a row'), ('Help_Handover', '', '')])
        self.assertFalse(fake.events['Help_Handover']['pending'])

    def test_handover_comment_is_cut_at_300_characters(self):
        fake = self.fake()
        self.call(fake, 1, 'x' * 500)
        self.assertEqual(len(fake.executed[0][2]), 300)

    def test_older_graph_without_the_handover_events_gives_none(self):
        fake = self.fake(escalate=False)
        self.assertIsNone(self.call(fake, 1, 'asked'))
        self.assertEqual(fake.executed, [])

    def test_acknowledge_executes_the_event(self):
        fake = FakeDCR()
        fake.events['Outcome_Confirm']['pending'] = True
        with patch('dcrai.dcr.dcr_repository.execute_raw_event', fake.execute):
            self.assertTrue(ort.acknowledge({}, 'Outcome_Confirm'))
        self.assertFalse(fake.events['Outcome_Confirm']['pending'])


class Patterns(unittest.TestCase):
    def test_person_and_urgent_match_what_the_panel_uses(self):
        import dcrai.application.application_runtime as ar
        self.assertEqual(ort.PERSON.pattern, ar.PERSON.pattern)
        self.assertEqual(ort.URGENT.pattern, ar.URGENT.pattern)
        self.assertEqual(ort.PERSON.flags, ar.PERSON.flags)

    def test_person_examples(self):
        self.assertTrue(ort.PERSON.search('Can I talk to a real person?'))
        self.assertTrue(ort.PERSON.search('I want to speak with a caseworker'))
        self.assertFalse(ort.PERSON.search('Who can apply for the supplement?'))
        self.assertTrue(ort.URGENT.search('I missed the 4-week deadline'))


if __name__ == '__main__':
    unittest.main()
