"""Retrieval chat for graphs with FAQ_UserQuestion (the Clean retrieval graph).

DCR stays in charge: the host only executes events that the live event list shows as enabled, and every text
the user reads comes from DCR (event descriptions) or from the retrieval result DCR stored in FAQ_RetrievalOk.
The LLM (retrieval_llm) only classifies: triage a message, check that retrieved FAQs fit, pick a follow-up item.

State split:
  DCR      every fact the conversation decides on: the triage decision (FAQ_Triage, policy in its description), what
           was searched (FAQ_UserQuestion, original wording in the comment when rewritten), the result
           (FAQ_RetrievalOk), the last answered FAQ (FAQ_Answered), follow-up and application answers.
  session  screen glue only: the id of the prompt on screen (stale-click protection) and the candidate answers
           waiting behind a confirm/options prompt. Losing it means "ask again", never a wrong process state.

Turn shapes returned to the UI (all carry faq=True, retrieval=True):
  welcome / out_of_scope / no_match / unavailable / ended / rephrase   response text, optional actions
  options   response + prompt (FAQ ids + none) for several matched questions (a single match is answered directly)
  answer    answer {faq_id, question, html, citation}; optional prompt (determination yes/no) or actions
  determination_result   outcomes [html]; optional next prompt (chained determination) or actions
"""
import functools
import html as htmllib
import json
import os
import logging
import re
import secrets
import time

import dcrai.dcr.dcr_repository as repo
from dcrai import paths, registry
import dcrai.llm.retrieval_llm as llm
import dcrai.observability.interaction_log as ilog
import dcrai.observability.turn_trace as turn_trace
import dcrai.chat.outcome as oc
import dcrai.chat.outcome_runtime as ort
from dcrai.chat.faq_runtime import StateError, choices, groups

log = logging.getLogger(__name__)

INPUT, OK, UNAVAILABLE = 'FAQ_UserQuestion', 'FAQ_RetrievalOk', 'FAQ_RetrievalUnavailable'
TRIAGE, ANSWERED = 'FAQ_Triage', 'FAQ_Answered'
# The two interfaces search through their own input, Robot continuation and failure message (spec 03, R8). The panel
# uses its own set only when the graph has it (the application host sets state['panel_search'] at start).
SEARCH_EVENTS = {'chat': ('FAQ_UserQuestion', 'FAQ_RetrievalOk', 'FAQ_RetrievalUnavailable'),
                 'panel': ('Help_UserQuestion', 'Help_RetrievalOk', 'Help_RetrievalUnavailable')}
# Contract between the graph's FAQ_Triage choice values and what the host does with them.
# The application is never started from the chat (no value for it): the Start button leaves for MitID.
TRIAGE_INTENTS = {'1': 'new_question', '2': 'reply', '4': 'end', '5': 'out_of_scope'}
PROMPT_TTL = registry.get('PROMPT_TTL')
# Example questions on the welcome screen, by FAQ id. The graph's FAQ_Welcome event names them with Example:<id>
# tags; this list is used only for graphs without that event. A click answers that FAQ directly (no clarification).
DEFAULT_EXAMPLES = ['FAQ_01', 'FAQ_21', 'FAQ_P01']
RECORDS_PATH = str(paths.FAQ_DATA / 'faq_qa_records.json')
DEFAULT_SCOPE = 'Questions about handicaptillæg, the SU disability supplement.'


# ------------------------------------------------------------------ behaviour flags
def flag(name, default):
    """True when the environment setting is '1'. Read at call time, so a test or a restart-free change applies at once.

    CONFIRM_LONE_SURVIVOR (default '1')   a list pruned to one FAQ is confirmed, not answered
    RELEVANCE_TIERS (default '1')         the relevance check returns "answers it" and "same topic only"
    PANEL_FALLBACK_REWRITE (default '0')  the panel rewrites a message the classifier did not call context dependent
    """
    if name in registry.SETTINGS:
        return registry.flag(name)     # the registry holds the default; `default` is only for names it does not know
    return os.getenv(name, default) == '1'


def log_outcome(state, interface, outcome, row, shown, via, **extra):
    """One event per question turn: which outcome was chosen and which FAQs were shown. Never any text.

    shown: candidate dicts or FAQ ids. extra: more fields for the same record (for example same_faq=True).
    """
    ids = [c['id'] if isinstance(c, dict) else c for c in shown or []]
    ilog.record(state, 'faq_outcome', interface=interface, turn=state.get('turn'), outcome=outcome,
                outcome_row=row, faq_ids=ids, via=via, **extra)


def log_reaction(state, interface, outcome, action, faq_id=None, turn=None):
    """One event when the applicant answers a Confirm, Offer or options prompt. turn is the prompt's turn."""
    ilog.record(state, 'faq_reaction', interface=interface, turn=turn if turn is not None else state.get('turn'),
                outcome=outcome, next_action=action, faq_id=faq_id)


# ------------------------------------------------------------------ live DCR helpers
def is_retrieval(payload):
    return any(e.get('id') == INPUT for e in (payload or {}).get('events', []))


def interface_of(state):
    """'panel' for an application session, 'chat' otherwise (until the turn recorder supplies it)."""
    return 'panel' if 'application_answers' in state else 'chat'


def search_ids(state):
    """(input, ok, unavailable) event ids of the interface's own search Robot."""
    return SEARCH_EVENTS['panel' if state.get('panel_search') and interface_of(state) == 'panel' else 'chat']


def followup_surface():
    """Where follow-up determinations are asked: 'panel' (default) or 'chat' (the old behaviour)."""
    return 'chat' if str(registry.get('FOLLOWUP_SURFACE')).strip().lower() == 'chat' else 'panel'


def refresh(state):
    payload = repo.get_raw_events(state)
    if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
        raise StateError('DCR did not return simulation events')
    state['simulation_state'] = payload
    return payload


def event(payload, eid):
    return next((e for e in payload['events'] if e.get('id') == eid), None)


def active(e):
    return e.get('included') is True and e.get('enabled') is True and e.get('pending') is True


def in_group(payload, name):
    return [e for e in payload['events'] if name in groups(e)]


def plain(text):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', htmllib.unescape(text or ''))).strip()


def paragraphs(text):
    """API answer text (plain, blank-line paragraphs) -> safe HTML for the UI's answer renderer."""
    parts = [p.strip() for p in re.split(r'\n\s*\n', text or '') if p.strip()]
    return ''.join('<p>' + htmllib.escape(p).replace('\n', '<br>') + '</p>' for p in parts)


def execute(state, eid, value='', comment=''):
    if not repo.execute_raw_event(state, eid, value, comment):
        raise StateError(f'DCR could not execute {eid}')


def show_label(state, payload, group, default):
    """Execute a message label event (for the DCR log) and return its text; host text if the graph lacks it."""
    events = [e for e in in_group(payload, group) if e.get('enabled') is True]
    if not events:
        return default
    if not repo.execute_raw_event(state, events[0]['id'], ''):
        log.warning('Could not execute message event %s', events[0]['id'])
    return events[0].get('description') or default


def label_text(payload, group, default):
    """Text of a message label event without executing it."""
    events = [e for e in in_group(payload, group) if e.get('enabled') is True]
    return (events[0].get('description') if events else None) or default


def scope_text(payload):
    events = in_group(payload, 'FAQScope')
    return plain(events[0].get('description')) if events else DEFAULT_SCOPE


def selector_items(payload):
    sel = [e for e in in_group(payload, 'GlobalInterpreter') if e.get('enabled') is True]
    if len(sel) != 1 or sel[0].get('dataType') != 'choice':
        raise StateError('Expected exactly one enabled selector event')
    return sel[0]['id'], [{'value': c['value'], 'label': c['question']} for c in choices(sel[0])]


def open_determinations(payload):
    return sorted([e for e in in_group(payload, 'FAQDetermination') if active(e)],
                  key=lambda e: e.get('sequence') or 0)


@functools.lru_cache(maxsize=1)
def faq_titles():
    """Canonical question titles of the FAQ records (labels for example and related questions).

    Titles only: an answer always comes through the DCR search (Robot + effect), never from this file.
    """
    try:
        with open(RECORDS_PATH, encoding='utf-8') as f:
            return {r['id']: r['canonical_question'] for r in json.load(f)['records']}
    except (OSError, ValueError, KeyError) as error:
        log.warning('FAQ titles unavailable: %s', type(error).__name__)
        return {}


def ordered_tags(e):
    raw = e.get('tags') if e.get('tags') not in (None, '') else e.get('groups', '')
    items = re.split(r'[,;\s]+', raw) if isinstance(raw, str) else list(raw or [])
    return [t for t in items if t]


# ------------------------------------------------------------------ prompts and responses
def respond(status, response='', **extra):
    return dict(faq=True, retrieval=True, status=status, response=response, **extra)


def issue(state, kind, text, options, **extra):
    pid = secrets.token_urlsafe(18)
    state['retrieval_prompt'] = dict(id=pid, kind=kind, text=text, choices=options, created=time.monotonic(), **extra)
    return dict(id=pid, kind=kind, text=text, options=options)


def current(state):
    prompt = state.get('retrieval_prompt')
    if prompt and time.monotonic() - prompt['created'] > PROMPT_TTL:
        state['retrieval_prompt'] = None
        return None
    return prompt


def initialize(state, payload):
    """Welcome turn. Text and example questions come from FAQ_Welcome (FAQ_Scope on older graphs)."""
    state.update(faq_mode=True, retrieval_mode=True, retrieval_prompt=None, retrieval_result=None,
                 outcome=dict(clarified=0, misses=0, handover_shown=False))
    session = event(payload, 'Session_Chat')
    if session is not None and session.get('enabled') is True:
        # Opens the chat's search input (FAQ_UserQuestion); the help panel never executes it. A graph from before the
        # split has no such event and needs nothing.
        if not repo.execute_raw_event(state, 'Session_Chat', ''):
            log.warning('Could not execute Session_Chat; the chat search input stays closed')
    welcome = in_group(payload, 'FAQWelcome')
    scope = in_group(payload, 'FAQScope')
    text = (welcome[0].get('description') if welcome else None) or \
        (scope[0].get('description') if scope else None) or f'<p>{DEFAULT_SCOPE}</p>'
    ids = [t.split(':', 1)[1] for t in ordered_tags(welcome[0]) if t.startswith('Example:')] if welcome else []
    titles = faq_titles()
    examples = [{'id': i, 'question': titles[i]} for i in (ids or DEFAULT_EXAMPLES) if i in titles]
    return respond('welcome', text, examples=examples)


UNUSABLE = 'The FAQ search did not return a usable result. Please try again.'


def check_relevance(message, found):
    """The relevance check on retrieved candidates. Returns the kept ones, each with a 'tier'.

    tier 'answers': the FAQ answers what was asked. tier 'related': same topic only. Order: answers, then related.
    RELEVANCE_TIERS=0 uses the old single check (every kept candidate is 'answers'). When the check is unavailable
    nothing is known about the candidates, so every one is 'related' and none can be shown as an answer.
    """
    by_id = {c['id']: c for c in found}
    try:
        if flag('RELEVANCE_TIERS', '1'):
            tiers = classify('relevance_tiers', message, found)
        else:
            tiers = {'answers': classify('relevant', message, found), 'related': []}
    except llm.LLMError as error:
        log.warning('Relevance check unavailable (%s); no candidate counts as an answer', error)
        return [dict(c, tier='related') for c in found]
    kept, seen = [], set()
    for tier in ('answers', 'related'):
        for i in tiers.get(tier) or []:
            if i in by_id and i not in seen:
                seen.add(i)
                kept.append(dict(by_id[i], tier=tier))
    return kept


@turn_trace.traced_search
def search(state, query, comment='', judge=None):
    """Execute FAQ_UserQuestion (the Robot runs the effect), read FAQ_RetrievalOk and post-check relevance.

    Returns (status, candidates, text): ('found', [...], ''), ('no_match', [], label text) or
    ('unavailable', [], text). Shared by the FAQ chat and the application help panel; the caller makes sure DCR
    has admitted the search (FAQ_Triage = 1 includes FAQ_UserQuestion).
    judge: the question the relevance check judges the candidates against (default: the query). The application
    panel passes what the applicant means (their words, or the rewrite), never a composed search string.
    """
    input_id, ok_id, unavailable_id = search_ids(state)
    execute(state, input_id, query, comment)
    after = refresh(state)
    unavailable = event(after, unavailable_id)
    if unavailable and active(unavailable):
        text = unavailable.get('description') or 'The FAQ search is temporarily unavailable.'
        execute(state, unavailable_id)
        return 'unavailable', [], text
    ok = event(after, ok_id)
    try:
        data = json.loads(ok.get('value') or '') if ok and ok.get('executed') else None
        while isinstance(data, str):
            data = json.loads(data)
    except ValueError:
        data = None
    if not isinstance(data, dict) or data.get('decision') not in ('single_match', 'clarify_match', 'no_match'):
        log.error('Retrieval result missing or unreadable')
        return 'unavailable', [], UNUSABLE
    if data['decision'] == 'single_match':
        found = [dict(id=data['id'], question=data['question'], answer=data.get('answer', ''),
                      citation=data.get('citation', ''))]
    elif data['decision'] == 'clarify_match':
        found = [dict(id=data[f'option{n}_id'], question=data[f'option{n}_question'],
                      answer=data.get(f'option{n}_answer', ''), citation=data.get(f'option{n}_citation', ''))
                 for n in (1, 2, 3) if data.get(f'option{n}_id')]
    else:
        found = []
    log.info('Retrieval decision=%s candidates=%s', data['decision'], [c['id'] for c in found])
    # What the search itself decided, before the relevance check prunes: callers need it to tell a true single
    # match from a lone survivor of a list.
    state['last_search'] = dict(decision=data['decision'], retrieved=[c['id'] for c in found])
    if found:
        found = check_relevance(judge or query, found)
    if not found:
        if ort.turn_outcome_ready(after):
            # TurnOutcome makes FAQ_NoMatch pending; the caller acknowledges it after the outcome is settled.
            return 'no_match', [], label_text(after, 'FAQNoMatch', 'I could not find an answer to that.')
        return 'no_match', [], show_label(state, after, 'FAQNoMatch', 'I could not find an answer to that.')
    return 'found', found, ''


# ------------------------------------------------------------------ the outcome of a question turn (spec 03)
# Host strings: the fallback when the graph lacks the DCR text event (identical wording to the events' texts).
CONFIRM_TEXT = 'Is this what you are asking?'
RELATED_ONE = 'No FAQ answers exactly this. This one is on the same topic and may help:'
RELATED_MANY = 'No FAQ answers exactly this. These are on the same topic and may help:'
CLARIFY_TEXT = 'I found a few questions that may fit. Which one is closest?'
SCOPE_QUESTION_TEXT = 'Is your question about handicaptillæg, the SU disability supplement?'
REPHRASE_TEXT = 'Could you rephrase your question? A few more words about your situation help.'
FOLLOW_UP_TEXT = 'One more question so the answer fits your situation (you can skip it):'


def counters(state):
    """Per-session counters of the outcome function: the clarified flag, consecutive misses, handover shown."""
    return state.setdefault('outcome', dict(clarified=0, misses=0, handover_shown=False))


def advance(state, signal):
    """Apply a counter signal (outcome.next_clarified / next_misses) to the session counters."""
    c = counters(state)
    c['clarified'] = oc.next_clarified(c['clarified'], signal)
    c['misses'] = oc.next_misses(c['misses'], signal)
    if signal == 'handover':
        c['handover_shown'] = True
    return c


def decide_turn(state, decision, tiers):
    """The outcome function for an in-scope question turn, with the session's counters."""
    c = counters(state)
    return oc.decide('in_scope', decision, tiers, c['clarified'], c['misses'], handover_shown=c['handover_shown'])


def settle_turn(state, payload, decision, interface):
    """Write the outcome into DCR (outcome_runtime.settle) and acknowledge the outcome event the host renders itself.

    The handover and out-of-scope events are acknowledged by the code that shows their text.
    """
    settled = ort.settle(state, payload, decision, interface)
    if settled.event_id and settled.decision.outcome not in ('handover', 'out_of_scope'):
        ort.acknowledge(state, settled.event_id)
    return settled


def outcome_message(payload, row, shown_count=0):
    """The text of an outcome: the DCR event's description when the graph has it, the host string otherwise."""
    default = {2: SCOPE_QUESTION_TEXT, 5: RELATED_ONE if shown_count == 1 else RELATED_MANY, 6: CONFIRM_TEXT,
               7: CLARIFY_TEXT, 8: CLARIFY_TEXT}.get(row)
    return ort.outcome_text(payload, row, shown_count) or default


def rephrase_message(state):
    return ort.message_text(state.get('simulation_state'), 'FAQ_Msg_Rephrase') or REPHRASE_TEXT


def log_decision(state, interface, settled, shown, via, outcome=None, row=None, **extra):
    """log_outcome for a settled decision, with the inputs and the extra fields of spec 03 (never any text).

    outcome and row override the decision's (CONFIRM_LONE_SURVIVOR=0 logs a confirm as an answer, row 6).
    """
    d = settled.decision
    c = counters(state)
    fields = dict(outcome_inputs=dict(zip(('scope', 'search', 'relevance', 'clarified'), d.inputs),
                                      misses=c['misses']),
                  outcome_source=settled.source)
    if settled.dcr_result is not None:
        fields.update(outcome_dcr=settled.dcr_result[1], outcome_row_dcr=settled.dcr_result[0])
    if settled.mismatch:
        fields['outcome_mismatch'] = True
    for key, value in (('clarify_kind', d.clarify_kind), ('label', d.label), ('handover_reason', d.handover_reason)):
        if value is not None:
            fields[key] = value
    fields.update(extra)
    turn_trace.note(**{k: v for k, v in fields.items() if k not in ('outcome_inputs',)})
    log_outcome(state, interface, outcome or d.outcome, d.row if row is None else row, shown, via, **fields)


def option_buttons(items):
    return [{'value': c['id'], 'label': c['question']} for c in items] + [{'value': 'none', 'label': 'None of these'}]


def handover_after_misses(state):
    """The handover block when the miss counter reaches the limit (second miss in a row), else None. Once."""
    c = counters(state)
    if c['misses'] < oc.MISSES_BEFORE_HANDOVER or c['handover_shown']:
        return None
    handover = ort.handover(state, 2, '%d questions in a row without a usable answer' % c['misses'])
    advance(state, 'handover')
    return handover


# ------------------------------------------------------------------ the question path
def ask(state, payload, message, search_query=None):
    """Run the question through DCR (Robot + effect), post-check the result, then settle the outcome and render it.

    search_query is the triage rewrite of a context-dependent message; it is what DCR searches, and the original
    wording goes into the execute comment so the DCR log keeps both. Which outcome the turn ends in is decided by
    outcome.decide (the nine-row table); outcome_runtime.settle writes it into DCR.
    """
    state['retrieval_prompt'] = None
    query = search_query or message
    shown = {'searched_for': query} if search_query and search_query != message else {}
    status, found, text = search(state, query, message if shown else '')
    decision = (state.get('last_search') or {}).get('decision')
    via = 'rewritten' if shown else 'typed'
    if status == 'unavailable':
        extra = {} if text == UNUSABLE else {'actions': [{'action': 'rephrase', 'label': 'Try again'}]}
        return respond('unavailable', text, **extra, **shown)
    settled = settle_turn(state, payload, decide_turn(state, decision, [c.get('tier') for c in found]), 'chat')
    d = settled.decision
    outcome = d.outcome
    items = oc.shown_for(d.row, found)
    if outcome in ('answer', 'confirm', 'offer', 'clarify') and not items:
        log.error('Outcome %s (row %s) has nothing to show; treating as not covered', outcome, d.row)
        outcome = 'not_covered'
    if outcome == 'confirm' and not flag('CONFIRM_LONE_SURVIVOR', '1'):
        outcome = 'answer'   # today's behaviour; the log keeps the table's row 6
    if outcome in ('not_covered', 'handover'):
        log_decision(state, 'chat', settled, [], via, outcome=outcome)
        reply = respond('no_match', text or ort.message_text(payload, 'FAQ_NoMatch') or 'I could not find an answer to that.',
                        actions=[{'action': 'rephrase', 'label': 'Rephrase my question'}], **shown)
        if outcome == 'handover':
            handover = ort.handover(state, 2, '%d questions in a row without a usable answer'
                                    % (counters(state)['misses'] + 1))
            advance(state, 'handover')
            if handover:
                reply['handover'] = handover
        else:
            advance(state, 'not_covered')
        return reply
    state['retrieval_result'] = dict(message=query, candidates=items)
    log_decision(state, 'chat', settled, items, via, outcome=outcome)
    if outcome == 'answer':
        # A true single match that the relevance check says answers it: answer it. The answer shows the matched
        # question, so the applicant sees what was answered (eval 2026-10-08: no wrong single match in 36 cases).
        advance(state, 'answered')
        reply = show_answer(state, items[0]['id'])
        reply.update(shown)
        return reply
    if outcome == 'confirm':
        # A list pruned to one FAQ: a lone survivor is not a confident match (eval 2026-10-09: every wrong answer
        # was one). Nothing from the FAQ is shown and FAQ_Answered is not executed until the applicant says yes.
        advance(state, 'confirm_shown')
        options = [{'value': items[0]['id'], 'label': 'Yes, show the answer'},
                   {'value': 'none', 'label': 'No, that is not it'}]
        prompt = issue(state, 'confirm', items[0]['question'], options, outcome='confirm', turn=state.get('turn'))
        return respond('confirm', outcome_message(payload, 6), prompt=prompt, **shown)
    prompt = issue(state, 'options', 'Which of these is closest to your question?', option_buttons(items),
                   outcome=outcome, turn=state.get('turn'))
    if outcome == 'offer':
        advance(state, 'offer')
        if d.row == 5:
            return respond('options', outcome_message(payload, 5, len(items)), prompt=prompt, related=True, **shown)
        # row 8: the best offer after a clarify. It reads the Clarify text (spec 03, Q2) and is not "related".
        return respond('options', outcome_message(payload, 8), prompt=prompt, **shown)
    advance(state, 'clarify_candidates')
    return respond('options', outcome_message(payload, 7), prompt=prompt, **shown)


def ask_example(state, payload, faq_id):
    """An example question from the welcome screen: search its exact title through DCR and answer that FAQ.

    The host executes FAQ_Triage = 1 itself (the applicant chose a listed question; no LLM triage). If the search
    does not return that FAQ (it should), the normal options are shown.
    """
    title = faq_titles().get(faq_id)
    if not title:
        raise StateError('That example is not available. Please type your question.')
    state['retrieval_prompt'] = None
    triage = event(payload, TRIAGE)
    if triage is not None:
        if triage.get('enabled') is not True:
            raise StateError('DCR is not accepting questions right now.')
        execute(state, TRIAGE, '1', 'example question chosen by the applicant')
    question = event(refresh(state), INPUT)
    if not question or question.get('enabled') is not True:
        raise StateError('DCR did not admit the question.')
    status, found, text = search(state, title, f'example question {faq_id}')
    if status == 'found' and any(c['id'] == faq_id for c in found):
        state['retrieval_result'] = dict(message=title, candidates=found)
        log_outcome(state, 'chat', 'answer', None, [faq_id], 'example')
        return show_answer(state, faq_id)
    log.warning('Example %s not returned by its own title (status=%s)', faq_id, status)
    if status == 'unavailable':
        return respond('unavailable', text, actions=[{'action': 'rephrase', 'label': 'Try again'}])
    if status == 'no_match':
        return respond('no_match', text, actions=[{'action': 'rephrase', 'label': 'Rephrase my question'}])
    state['retrieval_result'] = dict(message=title, candidates=found)
    log_outcome(state, 'chat', 'clarify', None, found, 'example')
    prompt = issue(state, 'options', 'Which of these is closest to your question?', option_buttons(found),
                   outcome='clarify', turn=state.get('turn'))
    return respond('options', 'I found a few questions that may fit. Which one is closest?', prompt=prompt)


def show_answer(state, faq_id):
    result = state.get('retrieval_result') or {}
    found = next((c for c in result.get('candidates', []) if c['id'] == faq_id), None)
    if not found:
        raise StateError('This answer is no longer available. Please ask again.')
    state['retrieval_prompt'] = None
    reply = respond('answer', '', answer=dict(faq_id=found['id'], question=found['question'],
                                              html=paragraphs(found['answer']), citation=found['citation']))
    payload = refresh(state)
    answered = event(payload, ANSWERED)
    if answered and answered.get('enabled') is True:
        # Context for the next triage lives in DCR, not in the session.
        if not repo.execute_raw_event(state, ANSWERED, f"{found['id']}: {found['question']}"):
            log.warning('Could not record the answered FAQ in DCR')
        payload = refresh(state)
    if followup_surface() != 'chat':
        return reply   # follow-up determinations are asked in the application's help panel (spec 03, R10)
    prompt = open_followup(state, payload, found, result.get('message', ''))
    if prompt:
        reply['prompt'] = prompt
        reply['follow_up'] = FOLLOW_UP_TEXT
    return reply


def open_followup(state, payload, found, message):
    """Open the follow-up determination for an answered FAQ, if the graph models one. Returns the prompt or None.

    The selector is executed with the item whose question is the answered FAQ (exact label match), otherwise with an
    LLM choice restricted to the catalogue (or none). `payload` is the live event list after FAQ_Answered.
    """
    try:
        selector, followups = selector_items(payload)
    except StateError as error:
        log.error('Selector unavailable: %s', error)
        return None
    value = next((i['value'] for i in followups if i['label'].strip().lower() == found['question'].strip().lower()),
                 None)
    if value is None and followups:
        try:
            value = classify('pick_followup', message or '', found['question'], followups)
        except llm.LLMError as error:
            log.warning('Follow-up pick unavailable (%s)', error)
    if value is None:
        return None
    execute(state, selector, value)
    log.info('Follow-up opened selector=%s value=%s', selector, value)
    return determination_prompt(state, refresh(state))


def determination_prompt(state, payload):
    asks = open_determinations(payload)
    if not asks:
        return None
    ask_event = asks[0]
    options = [{'value': c['value'], 'label': c['question']} for c in choices(ask_event)]
    return issue(state, 'determination', ask_event.get('label', ''), options, event_id=ask_event['id'])


def answer_determination(state, prompt, value):
    payload = refresh(state)
    ask_event = event(payload, prompt['event_id'])
    if not ask_event or ask_event.get('enabled') is not True:
        state['retrieval_prompt'] = None
        raise StateError('This follow-up question is no longer open. Please ask again.')
    execute(state, ask_event['id'], value)
    state['retrieval_prompt'] = None
    after = refresh(state)
    outcomes = sorted([e for e in after['events'] if active(e) and groups(e) & {'DeterminationResult', 'FAQAnswer'}
                       and e.get('id') != UNAVAILABLE], key=lambda e: e.get('sequence') or 0)
    texts = []
    for e in outcomes:
        texts.append(e.get('description') or e.get('label', ''))
        execute(state, e['id'])  # acknowledge, so the outcome is no longer an open obligation
    label = next((c['label'] for c in prompt['choices'] if c['value'] == value), value)
    reply = respond('determination_result', '', outcomes=texts, answered=dict(question=prompt['text'], value=label))
    nxt = determination_prompt(state, refresh(state))
    if nxt:
        reply['prompt'] = nxt
    return reply


def rejected(state, signal):
    """The applicant said no to a Confirm, Offer or options prompt: ask them to rephrase and count the miss.

    A second miss in a row adds the handover block (once per session).
    """
    advance(state, signal)
    reply = respond('rephrase', rephrase_message(state))
    handover = handover_after_misses(state)
    if handover:
        reply['handover'] = handover
    return reply


def reply_to_prompt(state, prompt, value):
    if value not in [str(c['value']) for c in prompt['choices']]:
        raise StateError('That option is not available. Please choose again.')
    if prompt['kind'] == 'confirm':
        if value == 'none':
            state['retrieval_prompt'] = None
            log_reaction(state, 'chat', 'confirm', 'rejected', turn=prompt.get('turn'))
            return rejected(state, 'rejected')
        log_reaction(state, 'chat', 'confirm', 'accepted', faq_id=value, turn=prompt.get('turn'))
        advance(state, 'accepted')
        return show_answer(state, value)
    if prompt['kind'] == 'options':
        outcome = prompt.get('outcome') or 'clarify'
        if value == 'none':
            state['retrieval_prompt'] = None
            log_reaction(state, 'chat', outcome, 'none_of_these', turn=prompt.get('turn'))
            return rejected(state, 'none_of_these')
        log_reaction(state, 'chat', outcome, 'chose', faq_id=value, turn=prompt.get('turn'))
        advance(state, 'chose')
        return show_answer(state, value)
    if prompt['kind'] == 'determination':
        return answer_determination(state, prompt, value)
    if prompt['kind'] == 'scope_check':
        state['retrieval_prompt'] = None
        execute(state, TRIAGE, value, 'scope confirmed by the applicant')
        return follow_dcr(state, prompt['message'], prompt.get('query'))
    raise StateError('Unknown prompt')


# ------------------------------------------------------------------ application hand-over
def start_application(state, payload):
    """The application is a separate session (MitID login, then its own simulation of this graph).

    Nothing is executed in the FAQ simulation; the UI navigates to the login page.
    """
    state['retrieval_prompt'] = None
    return respond('navigate', 'Taking you to the MitID login to start the application.',
                   navigate=f"/mitid?graphid={state.get('graph_id', '')}")


# ------------------------------------------------------------------ classifier selection
def classify(name, *args):
    """Decisions API first when DECISIONS_ENABLED=1, the Responses-based function as fallback."""
    if llm.decisions_enabled():
        try:
            return getattr(llm, f'{name}_decisions')(*args)
        except llm.LLMError as error:
            log.warning('Decisions %s unavailable (%s); using the Responses fallback', name, error)
    return getattr(llm, name)(*args)


SCOPE_CHECK = [{'value': '1', 'label': 'Yes, search for it'}, {'value': '5', 'label': 'No, something else'}]


# ------------------------------------------------------------------ triage (policy event) and context from DCR
def dcr_context(payload):
    """Conversation context as DCR holds it: the last answered FAQ and the last answered follow-up question."""
    context = {'last_answered_faq': None, 'last_followup': None}
    answered = event(payload, ANSWERED)
    if answered and answered.get('executed') and answered.get('value'):
        context['last_answered_faq'] = str(answered['value'])
    asked = [e for e in in_group(payload, 'FAQDetermination') if e.get('executed') and e.get('value') not in (None, '')]
    if asked:
        last = max(asked, key=lambda e: str(e.get('executed')))
        try:
            label = next((c['question'] for c in choices(last) if c['value'] == str(last['value'])), str(last['value']))
        except StateError:
            label = str(last['value'])
        context['last_followup'] = {'question': last.get('label', ''), 'answer': label}
    turn_trace.note(context=context)
    return context


def route(state, payload, message, prompt):
    """Decide what a typed message is. Returns (intent, reply_value, search_query).

    With FAQ_Triage in the graph: the policy is that event's description, the LLM picks one of its values, and the
    host executes FAQ_Triage with it (the reason goes in the comment). DCR then admits FAQ_UserQuestion only for
    value 1. Without it (older graphs): the built-in route prompt, no rewrite.
    """
    triage = event(payload, TRIAGE)
    if not triage:
        try:
            intent, value = llm.route(message, prompt, scope_text(payload))
        except llm.LLMError as error:
            log.warning('Router unavailable (%s); treating message as a question', error)
            intent, value = 'new_question', None
        return intent, value, None
    values = [{'value': c['value'], 'label': c['question']} for c in choices(triage)]
    if {v['value'] for v in values} - set(TRIAGE_INTENTS):
        raise StateError('FAQ_Triage values do not match the host contract (1, 2, 4, 5); re-import the graph')
    try:
        decision = classify('triage', message, plain(triage.get('description')), values, prompt, dcr_context(payload))
    except llm.LLMError as error:
        log.warning('Triage unavailable (%s); defaulting to a search', error)
        decision = dict(value='1', reply_value=None, search_query=None, reason='triage unavailable; default search')
    if decision.get('unsure'):
        # Not sure whether this is in scope: ask the applicant; FAQ_Triage is executed once they answer.
        return 'scope_check', None, decision['search_query']
    execute(state, TRIAGE, decision['value'], decision['reason'][:300])
    return TRIAGE_INTENTS[decision['value']], decision['reply_value'], decision['search_query']


MESSAGE_GROUPS = ('FAQOutOfScope', 'FAQGoodbye')


def follow_dcr(state, message, query):
    """After FAQ_Triage ran: do what DCR made possible, without interpreting the triage value.

    Pending message events (out of scope, goodbye) are shown and acknowledged; an enabled FAQ_UserQuestion means
    DCR admitted a search.
    """
    payload = refresh(state)
    messages = sorted([e for e in payload['events'] if active(e) and groups(e) & set(MESSAGE_GROUPS)],
                      key=lambda e: e.get('sequence') or 0)
    if messages:
        if any('FAQOutOfScope' in groups(e) for e in messages):
            # Row 1 of the outcome table. Settled before the message is acknowledged, so FAQ_OutOfScope is executed
            # once (TurnOutcome makes it pending too).
            settled = ort.settle(state, payload, oc.decide('out_of_scope', None, [], counters(state)['clarified']), 'chat')
            log_decision(state, 'chat', settled, [], 'rewritten' if query and query != message else 'typed')
            advance(state, 'out_of_scope')
        else:
            advance(state, 'end')
        texts = []
        for e in messages:
            texts.append(e.get('description') or e.get('label', ''))
            execute(state, e['id'])
        state['retrieval_prompt'] = None
        status = 'out_of_scope' if any('FAQOutOfScope' in groups(e) for e in messages) else 'ended'
        return respond(status, ''.join(texts))
    question = event(payload, INPUT)
    if question and question.get('enabled') is True:
        return ask(state, payload, message, query)
    return respond('rephrase', 'Could you ask that as a question? For example: "Who can get handicaptillæg?"')


def scope_check(state, message, query):
    """Row 2 of the outcome table: the triage is unsure, so ask whether the question is about handicaptillæg."""
    payload = state.get('simulation_state')
    if payload is None:
        payload = refresh(state)
    settled = settle_turn(state, payload, oc.decide('unsure', None, [], counters(state)['clarified']), 'chat')
    log_decision(state, 'chat', settled, [], 'rewritten' if query and query != message else 'typed')
    advance(state, 'scope_question')
    prompt = issue(state, 'scope_check', outcome_message(payload, 2), SCOPE_CHECK, message=message, query=query)
    return respond('scope_check', 'I want to make sure I understand.', prompt=prompt)


def person_request(state, payload):
    """The applicant asks for a person (handover reason 1). None when the graph has no handover events."""
    trigger = event(payload, 'Help_Escalate')
    if trigger is None or trigger.get('enabled') is not True:
        return None
    settled = ort.settle(state, payload, oc.decide('in_scope', None, [], asked_person=True), 'chat')
    handover = ort.handover(state, 1, 'asked to talk to a person')
    if not handover:
        return None
    log_decision(state, 'chat', settled, [], 'typed')
    return respond('handover', '', handover=handover)


# ------------------------------------------------------------------ entry point


@turn_trace.turn('chat')
def handle(state, data):
    """One chat request. The turn decorator counts it (state['turn']) and writes its turn line."""
    payload = refresh(state)
    action = data.get('action')
    if action == 'reply':
        prompt = current(state)
        if not prompt or data.get('retrieval_prompt_id') != prompt['id']:
            raise StateError('This question has changed. Please ask again.')
        return reply_to_prompt(state, prompt, str(data.get('value')))
    if action == 'apply':
        return start_application(state, payload)
    if action == 'example':
        return ask_example(state, payload, str(data.get('faq_id') or ''))
    if action == 'end':
        # Idle timeout in the UI (reason 'idle') or an explicit end. Recorded in DCR: FAQ_Triage = 4 makes
        # FAQ_Goodbye pending and follow_dcr shows it; older graphs get the host text.
        state['retrieval_prompt'] = None
        reason = 'idle timeout (no activity)' if data.get('reason') == 'idle' else 'ended by the applicant'
        triage = event(payload, TRIAGE)
        if triage is not None and triage.get('enabled') is True:
            execute(state, TRIAGE, '4', reason)
            return follow_dcr(state, '', None)
        return respond('ended', 'Thank you. You can ask another question at any time.')
    if action == 'rephrase':
        state['retrieval_prompt'] = None
        return respond('rephrase', 'Type your question in your own words.')
    if action:
        raise StateError('Unknown action')
    message = data.get('message')
    if not isinstance(message, str) or not message.strip() or len(message) > 2000:
        raise StateError('Please enter a message of 1–2000 characters')
    message = message.strip()
    prompt = current(state)
    if not prompt and ort.PERSON.search(message):
        reply = person_request(state, payload)
        if reply:
            return reply
    intent, value, query = route(state, payload, message, prompt)
    if intent == 'scope_check':
        return scope_check(state, message, query)
    if intent == 'reply' and prompt:
        if value is None:
            reply = respond('unclear', 'I did not catch which option you mean. Please choose one, or ask a new question.')
            reply['prompt'] = dict(id=prompt['id'], kind=prompt['kind'], text=prompt['text'], options=prompt['choices'])
            return reply
        return reply_to_prompt(state, prompt, value)
    if event(payload, TRIAGE):
        # FAQ_Triage has run; DCR now decides what is possible (search or message).
        return follow_dcr(state, message, query)
    if intent == 'apply':
        return start_application(state, payload)
    if intent == 'end':
        state['retrieval_prompt'] = None
        advance(state, 'end')
        return respond('ended', 'Thank you. You can ask another question at any time.')
    if intent == 'out_of_scope':
        state['retrieval_prompt'] = None
        advance(state, 'out_of_scope')
        return respond('out_of_scope', show_label(state, payload, 'FAQOutOfScope', 'That is outside what I can help with.'))
    if intent == 'reply' and not prompt:
        return respond('rephrase', 'Could you ask that as a question? For example: "Who can get handicaptillæg?"')
    return ask(state, payload, message, query)
