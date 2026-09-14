"""FAQ presentation and confirmation over raw DCR simulation API events only."""
import logging
import re
import secrets
import time

import dcr_repository as repo
import openchat

log = logging.getLogger(__name__)


class StateError(ValueError):
    pass


def groups(event):
    result = set()
    # /simulation/.../event serializes XML groups as tags; other endpoints
    # expose groups. Both are raw API metadata, never XML-derived.
    for field in ('groups', 'tags'):
        value = event.get(field, '')
        result.update(re.split(r'[,;\s]+', value) if isinstance(value, str) else (value or []))
    return result


def is_faq(payload):
    return any(groups(e) & {'GlobalInterpreter', 'FAQTopicMenu', 'FAQAnswer', 'FAQHome'}
               for e in (payload or {}).get('events', []))


def choices(event):
    """Decode the repository's Label (value), Label (value) wire representation."""
    raw = event.get('choiceValues', '')
    if not isinstance(raw, str) or not raw.strip():
        raise StateError('Missing API choice catalogue')
    # Non-greedy label permits parentheses inside question labels. The final
    # parentheses immediately before a separator delimit the machine value.
    pattern = re.compile(r'\s*(.*?)\s+\(([^()]*)\)(?:,\s*|$)', re.DOTALL)
    result, pos = [], 0
    for match in pattern.finditer(raw):
        if match.start() != pos or not match[1].strip() or not match[2]:
            raise StateError('Malformed API choices')
        result.append({'event_id': event['id'], 'value': match[2], 'question': match[1].strip(),
                       'candidate_key': f"{event['id']}:{match[2]}"})
        pos = match.end()
    if pos != len(raw) or not result or len({c['candidate_key'] for c in result}) != len(result):
        raise StateError('Malformed or duplicate API choices')
    return result


def catalogue(payload):
    selectors = [e for e in payload['events'] if 'GlobalInterpreter' in groups(e) and e.get('enabled') is True]
    if len(selectors) != 1 or selectors[0].get('dataType') != 'choice':
        raise StateError('Expected exactly one enabled GlobalInterpreter choice event')
    return choices(selectors[0])


def refresh(state):
    payload = repo.get_raw_events(state)
    if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
        raise StateError('DCR did not return simulation events')
    state['simulation_state'] = payload
    return payload


def active(event):
    return event.get('enabled') is True and event.get('pending') is True


def topic_tags(event):
    return {tag for tag in groups(event) if tag.startswith('FAQTopic:')}


def menu_choices(event, payload):
    options = choices(event)
    if 'FAQHideRead' not in groups(event):
        return options
    topic = topic_tags(event)
    if len(topic) != 1:
        raise StateError('History-aware menu needs one API topic marker')
    explored = [e for e in payload['events'] if 'FAQTopicExplored' in groups(e)
                and topic_tags(e) == topic]
    # Review is issued by DCR. Presentation preserves the execution history.
    if len(explored) == 1 and explored[0].get('executed'):
        review = [c for c in choices(explored[0]) if c['question'] == 'Review questions']
        if len(review) == 1 and str(explored[0].get('value')) == review[0]['value']:
            return options
    answers = [e for e in payload['events'] if 'FAQAnswer' in groups(e) and topic_tags(e) == topic]
    visible = []
    for option in options:
        matches = [e for e in answers if e.get('label') == option['question']]
        if len(matches) > 1:
            raise StateError('Duplicate answer labels within an API topic')
        if not matches or not matches[0].get('executed'):
            visible.append(option)
    return visible


def topic_name(event, payload):
    tags = topic_tags(event)
    if len(tags) != 1:
        return None
    value = next(iter(tags)).split(':', 1)[1]
    homes = [choices(e) for e in payload['events'] if 'FAQHome' in groups(e)]
    # The full topic directory takes precedence over a one-choice welcome screen.
    for options in sorted(homes, key=len, reverse=True):
        names = [c['question'] for c in options if c['value'] == value]
        if len(names) == 1:
            return names[0]
    return None


def navigation(payload, home_only=False):
    menus = [e for e in payload['events'] if e.get('enabled') is True and
             ('FAQHome' in groups(e) or (not home_only and active(e) and 'FAQTopicMenu' in groups(e)))]
    # The pending topic goes first; Home remains available for explicit browsing.
    menus.sort(key=lambda e: 'FAQHome' in groups(e))
    return [{'event_id': e['id'], 'question': e['label'],
             'is_home': 'FAQHome' in groups(e), 'options': menu_choices(e, payload)} for e in menus]


def view(state, payload):
    nav = navigation(payload)
    pending = [e for e in payload['events'] if active(e) and
               groups(e) & {'FAQTopicMenu', 'FAQHome'}]
    if len(pending) != 1:
        raise StateError('Expected one pending navigation event')
    state['event_id'] = pending[0]['id']
    log.info('FAQ navigation pending=%s', pending[0]['id'])
    return {'faq': True, 'status': 'navigation', 'response': pending[0]['label'],
            'event_id': pending[0]['id'], 'navigation': nav,
            'topic_name': topic_name(pending[0], payload),
            'topic_explored': 'FAQTopicExplored' in groups(pending[0])}


def fallback(state, payload, message=None, error=None):
    result = {'faq': True, 'status': 'no_match',
              'response': message or "I couldn’t find an answer to that in this chatbot’s SU disability supplement FAQs. You can ask about eligibility, documentation, applying, or payments, or browse the topics below.",
              'actions': [{'action': 'rephrase', 'label': 'Rephrase my question'},
                          {'action': 'topics', 'label': 'Browse topics'}],
              'navigation': navigation(payload, home_only=True)}
    if error:
        result['error_code'] = error
    try:
        candidates = catalogue(payload)
        contacts = [e for e in payload['events'] if 'FallbackContact' in groups(e)]
        if len(contacts) == 1:
            matches = [c for c in candidates if c['question'] == contacts[0].get('label')]
            if len(matches) == 1:
                result['actions'].append({'action': 'contact', 'label': matches[0]['question']})
    except StateError:
        pass
    return result


def initialize(state, payload):
    state['faq_mode'] = True
    state['last_confirmed_question'] = None
    state['faq_match'] = None
    try:
        catalogue(payload)
        return view(state, payload)
    except StateError as error:
        log.error('FAQ configuration error: %s', error)
        return fallback(state, payload, 'FAQ matching is not configured correctly. Please use the topic buttons.', 'configuration_error')


def execute(state, candidate, payload):
    event = next((e for e in payload['events'] if e['id'] == candidate['event_id']), None)
    if not event or event.get('enabled') is not True or candidate not in choices(event):
        raise StateError('This choice is no longer available. Please choose again.')
    state['faq_match'] = None
    if not repo.execute_event(state, event['id'], candidate['value'], ''):
        raise StateError('DCR could not execute this choice')
    log.info('FAQ executed event=%s value=%r', event['id'], candidate['value'])
    state.setdefault('execution_history', []).append({'event_id': event['id'],
        'event_label': candidate['question'], 'value': candidate['value'], 'type': 'user', 'timestamp': time.time()})
    # A canonical direct question also provides context; topic navigation does not.
    if 'GlobalInterpreter' in groups(event) or 'FAQTopicMenu' in groups(event):
        try:
            if any(c['question'] == candidate['question'] for c in catalogue(payload)):
                state['last_confirmed_question'] = candidate['question']
        except StateError:
            pass
    latest = refresh(state)
    if 'FAQHome' in groups(event) or 'FAQTopicMenu' in groups(event):
        # Explicit back/topic buttons lead to a menu, not an answer. DCR decides.
        if any(active(e) and groups(e) & {'FAQHome', 'FAQTopicMenu'} for e in latest['events']):
            if not any(active(e) and 'FAQAnswer' in groups(e) for e in latest['events']):
                return view(state, latest)
    answers = [e for e in latest['events'] if active(e) and 'FAQAnswer' in groups(e)]
    other_pending = [e for e in latest['events'] if active(e) and e not in answers]
    if len(answers) != 1 or other_pending:
        log.error('FAQ invalid answer marking=%s', latest)
        raise StateError('DCR did not produce exactly one pending answer')
    answer = answers[0]
    text = answer.get('description')
    if not isinstance(text, str) or not text:
        raise StateError('DCR answer description is missing')
    log.info('FAQ pending answer=%s', answer['id'])
    # Capture verbatim before acknowledgement. No inferred next-event routing.
    response = {'faq': True, 'status': 'answer', 'response': text, 'answer': text,
                'answer_event_id': answer['id'], 'navigation': []}
    if not repo.execute_event(state, answer['id'], '', ''):
        response['error_code'] = 'answer_acknowledgement_failed'
        response['follow_up'] = 'The answer was retrieved, but navigation could not advance. Please restart the conversation.'
        return response
    log.info('FAQ acknowledged answer=%s', answer['id'])
    try:
        after = refresh(state)
        if any(active(e) and 'FAQAnswer' in groups(e) for e in after['events']):
            raise StateError('Answer remains pending after acknowledgement')
        nav = view(state, after)
        response['navigation'] = nav['navigation']
        response['event_id'] = nav['event_id']
        response['topic_name'] = nav['topic_name']
        response['topic_explored'] = nav['topic_explored']
        if nav['topic_explored']:
            response['follow_up'] = nav['response']
    except StateError:
        log.error('FAQ navigation failed marking=%s', state.get('simulation_state'))
        response['error_code'] = 'navigation_error'
        response['follow_up'] = 'The answer was retrieved, but navigation is unavailable. Please restart the conversation.'
    return response


def marking(payload):
    # Exclude clock/diagnostic fields that change on read without a state change.
    fields = ('id', 'enabled', 'included', 'pending', 'executed', 'value', 'choiceValues', 'label', 'groups', 'tags')
    return sorted([{k: e.get(k) for k in fields} for e in payload['events']], key=lambda e: e['id'])


def handle(state, data):
    payload = refresh(state)
    action = data.get('action')
    if action == 'confirm':
        issued = state.get('faq_match')
        if (not issued or data.get('match_id') != issued['id'] or
                time.monotonic() - issued['created'] > 600):
            raise StateError('This suggestion has expired. Please ask again.')
        key = data.get('candidate_key')
        candidate = next((c for c in issued['candidates'] if c['candidate_key'] == key), None)
        # Compare full fresh marking as well as enabledness/catalogue. Changes in
        # another request must invalidate an old confirmation even if still enabled.
        if not candidate or marking(payload) != issued['marking'] or candidate not in catalogue(payload):
            state['faq_match'] = None
            raise StateError('This suggestion is no longer current. Please ask again.')
        log.info('FAQ confirmation match_id=%s candidate=%s', issued['id'], key)
        return execute(state, candidate, payload)
    if action == 'reject':
        issued = state.get('faq_match')
        if not issued or data.get('match_id') != issued['id']:
            raise StateError('This suggestion is no longer current')
        log.info('FAQ rejection match_id=%s', issued['id'])
        state['faq_match'] = None
        return fallback(state, payload, 'Please rephrase your question or choose a topic.')
    state['faq_match'] = None
    if action in ('topics', 'rephrase'):
        return fallback(state, payload, 'Choose a topic below or type another question.')
    if action == 'contact':
        contacts = [e for e in payload['events'] if 'FallbackContact' in groups(e)]
        matches = [c for c in catalogue(payload) if len(contacts) == 1 and c['question'] == contacts[0].get('label')]
        if len(matches) != 1:
            raise StateError('The contact option is not configured')
        return execute(state, matches[0], payload)
    if data.get('value') is not None:
        # Direct controls can only execute a currently presented navigation choice.
        available = [c for n in navigation(payload) for c in n['options']]
        candidates = [c for c in available if c['event_id'] == data.get('event_id') and
                      type(data['value']) in (str, int, float, bool) and str(c['value']) == str(data['value'])]
        if len(candidates) != 1:
            raise StateError('This button is no longer available. Please choose again.')
        return execute(state, candidates[0], payload)
    if action:
        raise StateError('Unknown FAQ action')
    message = data.get('message')
    if not isinstance(message, str) or not message.strip() or len(message) > 8000:
        raise StateError('Please enter a question of 1–8000 characters')
    try:
        candidates = catalogue(payload)
    except StateError as error:
        log.error('FAQ configuration error: %s', error)
        return fallback(state, payload, 'FAQ matching is not configured correctly. Please use the topic buttons.', 'configuration_error')
    try:
        decision, rows = openchat.rank(message, state.get('last_confirmed_question'), candidates)
    except (openchat.MatchError, ValueError) as error:
        log.warning('FAQ matching failure type=%s', type(error).__name__)
        return fallback(state, payload, 'Question matching is temporarily unavailable. You can still browse topics or view the authority contact information.', 'matcher_unavailable')
    if decision == 'no_match':
        return fallback(state, payload)
    by_key = {c['candidate_key']: c for c in candidates}
    selected = [by_key[r['candidate_key']] for r in rows]
    match_id = secrets.token_urlsafe(24)
    state['faq_match'] = {'id': match_id, 'candidates': selected,
                          'created': time.monotonic(), 'marking': marking(payload)}
    return {'faq': True, 'status': 'confirm_match' if decision == 'single_match' else 'clarify_match',
            'response': 'Is this the question you mean?' if decision == 'single_match' else 'I’m not entirely sure. Did you mean one of these?',
            'match_id': match_id,
            'candidates': [{'candidate_key': c['candidate_key'], 'question': c['question']} for c in selected]}
