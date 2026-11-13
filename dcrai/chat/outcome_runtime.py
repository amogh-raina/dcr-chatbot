"""DCR side of the outcome table: tell DCR which outcome a turn ended in, and read back what DCR makes pending.

The decision itself is made by dcrai.chat.outcome (pure code). This module writes it into the graph:

  code     the function decides; only TurnOutcome is written.
  shadow   the function decides; the DMN in DCR is also run (TurnStart, four gates) and compared.
  dcr      the DMN result decides; the function is used only if the DMN result cannot be read.

OUTCOME_MODE (environment, default `code`) selects the mode and is read at call time. A graph without TurnOutcome
(graph 2014078 and older) is left alone: settle returns the decision unchanged.

Known limit of shadow and dcr: TurnResult keeps its last value, so if the Robot did not run on a turn the previous
turn's result is read again. A stale result that differs shows as a mismatch; one that happens to be equal does not.
Whether the Robot runs again on every turn is Portal fixture F4 of spec 03.
"""
import html as htmllib
import logging
import re
from typing import NamedTuple, Optional

import dcrai.dcr.dcr_repository as repo
from dcrai import registry
from dcrai.chat import outcome as oc
from dcrai.chat.faq_runtime import StateError, choices, groups

log = logging.getLogger(__name__)

MODES = ('code', 'shadow', 'dcr')
GATES = ('GateScope', 'GateSearch', 'GateRelevance', 'GateClarified')   # table input events, in DMN order
TURN_START, TABLE, RESULT, TURN_OUTCOME = 'TurnStart', 'OutcomeTable', 'TurnResult', 'TurnOutcome'

# Text events (descriptions) the host reads when the graph has them; the host keeps today's strings otherwise.
TEXT_EVENT = {'confirm': 'Outcome_Confirm', 'clarify': 'Outcome_Clarify', 'offer': 'Outcome_Offer',
              'answer': 'Outcome_Answer', 'offer_one': 'FAQ_Msg_OfferOne', 'scope_question': 'FAQ_Msg_ScopeQuestion',
              'rephrase': 'FAQ_Msg_Rephrase', 'not_covered': 'FAQ_NoMatch', 'out_of_scope': 'FAQ_OutOfScope',
              'handover': 'Help_Handover'}

# Moved here from application_runtime.py so the chat can use them as well.
URGENT = re.compile(r"\b(deadlines?|appeal(s|ing|ed)?|klage|frist|too late|urgent(ly)?|asap|expir(e|es|ed|ing)|"
                    r"(4|four)[- ]weeks?)\b", re.I)
PERSON = re.compile(r"\b(talk|speak|chat|call)\b.{0,30}\b(person|human|someone|somebody|caseworker|agent|staff)\b|"
                    r"\b(real|actual) (person|human)\b", re.I)


class Settled(NamedTuple):
    decision: oc.Decision              # what the host renders (the function's, or the DMN's in dcr mode)
    source: str                        # 'code', 'dcr' or 'failclosed'
    event_id: Optional[str]            # the outcome event DCR made pending; None when TurnOutcome was not used
    text: Optional[str]                # that event's description as DCR holds it (HTML); None if empty or unused
    mismatch: bool                     # a readable DMN result differed from the function's (row, table outcome)
    dcr_result: Optional[tuple] = None  # (row, outcome) the DMN produced, when it ran and was readable


# OUTCOME_MODE is a registry setting (default code), read at call time.
MODE_ENV = 'OUTCOME_MODE'


def mode():
    value = str(registry.get(MODE_ENV)).strip().lower()
    if value not in MODES:
        log.warning('%s=%r is not one of %s; using code', MODE_ENV, value, MODES)
        return 'code'
    return value


def _event(payload, eid):
    return next((e for e in (payload or {}).get('events', []) if e.get('id') == eid), None)


def _plain(text):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', htmllib.unescape(text or ''))).strip()


def _exec(state, eid, value, comment=''):
    try:
        ok = repo.execute_raw_event(state, eid, value, comment)
    except Exception as exc:   # network or DCR failure must not break the turn
        log.warning('Could not execute %s: %s', eid, exc)
        return False
    if not ok:
        log.warning('Could not execute %s', eid)
    return bool(ok)


def parse_result(value):
    """`result 6:confirm` -> (6, 'confirm'); anything else -> None."""
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r'result (\d+):([a-z_]+)', value.strip())
    if not m:
        return None
    row, name = int(m[1]), m[2]
    if not 1 <= row <= len(oc.ROWS) or name not in oc.OUTCOMES or name == 'handover':
        return None
    return row, name


def turn_outcome_ready(payload):
    """True when the graph has TurnOutcome with exactly the seven outcome values and it can be executed."""
    e = _event(payload, TURN_OUTCOME)
    if e is None:
        return False
    try:
        values = {c['value'] for c in choices(e)}
    except StateError as exc:
        log.error('TurnOutcome dictionary unreadable (%s); outcome events are not used', exc)
        return False
    if values != set(oc.OUTCOMES):
        log.error('TurnOutcome values %s differ from the outcomes %s; outcome events are not used',
                  sorted(values), sorted(oc.OUTCOMES))
        return False
    if e.get('included') is not True or e.get('enabled') is not True:
        log.error('TurnOutcome is not enabled; outcome events are not used')
        return False
    return True


def _run_table(state, payload, decision):
    """Run the DMN in DCR for the decision's inputs; return (row, outcome) or None when it cannot be read."""
    if any(_event(payload, x) is None for x in (TURN_START, TABLE, RESULT) + GATES):
        log.warning('The graph lacks the outcome table events; the DMN is not run')
        return None
    scope, search, relevance, clarified = decision.inputs
    if not _exec(state, TURN_START, ''):
        return None
    for gate, value in zip(GATES, (scope, search, relevance, str(clarified))):
        if not _exec(state, gate, value):
            return None
    try:
        fresh = repo.get_raw_events(state)
    except Exception as exc:
        log.warning('Could not read the table result: %s', exc)
        return None
    result = _event(fresh, RESULT)
    parsed = parse_result(result.get('value')) if result else None
    if parsed is None:
        table = _event(fresh, TABLE)
        parsed = parse_result('result ' + str(table.get('value'))) if table and table.get('value') else None
    if parsed is None:
        log.warning('The table result is not readable')
    return parsed


def _pending_outcomes(payload):
    ids = set(oc.OUTCOME_EVENT.values())
    return {e['id'] for e in (payload or {}).get('events', [])
            if e.get('id') in ids and e.get('pending') is True and e.get('included') is True}


def settle(state, payload, decision, interface):
    """Write the turn's outcome into DCR and return what to render.

    payload: the event list the host holds before the turn's outcome (used to detect the events).
    decision: the function's oc.Decision. interface: 'chat' or 'panel' (logged only).
    """
    if not turn_outcome_ready(payload):
        return Settled(decision, 'code', None, None, False)
    counters = state.get('outcome') or {}
    misses, shown = counters.get('misses', 0), counters.get('handover_shown', False)

    chosen, source, dcr_result, mismatch = decision, 'code', None, False
    if mode() in ('shadow', 'dcr') and decision.row is not None:
        dcr_result = _run_table(state, payload, decision)
        if dcr_result is not None:
            mismatch = dcr_result != (decision.row, decision.table_outcome)
            if mismatch:
                log.warning('Outcome mismatch on %s: function %s, DMN %s, inputs %s', interface,
                            (decision.row, decision.table_outcome), dcr_result, decision.inputs)
            if mode() == 'dcr':
                source = 'dcr'
                if mismatch:
                    chosen = oc.from_table(dcr_result[0], dcr_result[1], decision.inputs, misses, shown)

    comment = 'row %s; source %s; misses %s' % (chosen.row if chosen.row is not None else 'none', source, misses)
    wrote = _exec(state, TURN_OUTCOME, chosen.outcome, comment)
    expected = {oc.OUTCOME_EVENT[chosen.outcome]}
    try:
        fresh = repo.get_raw_events(state) if wrote else None
    except Exception as exc:
        log.warning('Could not read the events after TurnOutcome: %s', exc)
        fresh = None
    pending = _pending_outcomes(fresh) if fresh is not None else None
    if pending != expected:
        log.error('Outcome %s on %s: pending outcome events %s, expected %s; failing closed to not_covered',
                  chosen.outcome, interface, sorted(pending) if pending is not None else 'unknown', sorted(expected))
        closed = oc.Decision('not_covered', 9, 'not_covered', None, None, None, decision.inputs)
        return Settled(closed, 'failclosed', oc.OUTCOME_EVENT['not_covered'], None, mismatch, dcr_result)

    event_id = oc.OUTCOME_EVENT[chosen.outcome]
    text = (_event(fresh, event_id) or {}).get('description') or None
    return Settled(chosen, source, event_id, text, mismatch, dcr_result)


def message_text(payload, event_id):
    """Plain text of a message event's description, or None when the graph lacks the event or it has no text."""
    e = _event(payload, event_id)
    return (_plain(e.get('description')) or None) if e else None


def outcome_text(payload, row, shown_count=0):
    """The text DCR holds for a row (table 4.6 of spec 03), plain; None when the graph lacks it.

    Row 8 reads the Clarify text although Outcome_Offer is the pending event (spec 03, open question Q2).
    """
    if row is None:
        return None
    if row == 1:
        key = 'out_of_scope'
    elif row in (3, 9):
        key = 'not_covered'
    elif row == 2:
        key = 'scope_question'
    elif row == 4:
        key = 'answer'
    elif row == 5:
        key = 'offer_one' if shown_count == 1 else 'offer'
    elif row == 6:
        key = 'confirm'
    elif row in (7, 8):
        key = 'clarify'
    else:
        return None
    return message_text(payload, TEXT_EVENT[key])


def acknowledge(state, event_id):
    """Execute an outcome event so it is no longer pending. True when DCR accepted it."""
    return _exec(state, event_id, '')


def handover(state, reason, signal):
    """Execute Help_Escalate (reason as value), read and acknowledge the Help_Handover text.

    Returns {'reason', 'html'}, or None when the graph has no handover events or no text. The panel's own
    escalate keeps its application-marking check and once-per-session rule around this call.
    """
    payload = repo.get_raw_events(state)
    trigger = _event(payload, 'Help_Escalate')
    if not trigger or trigger.get('enabled') is not True:
        return None   # older graph without the handover events
    if not _exec(state, 'Help_Escalate', str(reason), (signal or '')[:300]):
        return None
    payload = repo.get_raw_events(state)
    message = next((e for e in payload['events'] if 'FAQHandover' in groups(e) and e.get('pending') is True
                    and e.get('included') is True), None)
    text = (message or {}).get('description') or ''
    if message and not _exec(state, message['id'], ''):
        log.warning('Could not acknowledge %s', message['id'])
    log.info('Handover reason=%s', reason)
    return dict(reason=reason, html=text) if text else None
