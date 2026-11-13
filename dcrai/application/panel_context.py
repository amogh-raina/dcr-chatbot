"""The help panel's context, kept in DCR (spec 02, section 4.4).

The panel used to keep "which FAQs did I just show, what did the applicant say, what was the previous message" only in the
Flask session. Now the host also writes it to the text event Panel_Context of the graph, once per panel request, and reads
it back from the event list it already fetched. The session fields stay as the fallback (graphs without the event,
an unreadable value, PANEL_CONTEXT_IN_DCR=0).

Value, JSON, at most LIMIT characters, no answer text:

    {"v":1, "faqs":[{"id":"FAQ_21","said":"how old can they be?","asked":"How old can a child be ...?"}, {...}],
     "field":"Form0:A3", "msg":"how old can they be?"}

    faqs   the last two FAQs shown, newest first. said: the applicant's wording (for a related click, the FAQ title).
           asked: the rewrite that was searched, when one was made and differs from said.
    field  id of the application field on screen. msg: the previous typed message.

    build(state, previous, faq)   the record: previous entries, a new first entry when given, the current field and message
    fit(record)                   JSON text within LIMIT (drops faqs[1], then cuts msg, then said and asked) or None
    read(payload)                 the parsed record when the event is executed and valid (v == 1, types match), else None
    current(state, payload)       read() with the flag and the presence check; remembers what it saw in the session
    last_faq(record), last_message(record), shown_id(state, payload)    what the panel needs from a record
    expand(faq_id)                question, topic and answer start of a FAQ, from the FAQ records (prompt context only)
    @persist                      decorator for panel ask and confirm: writes the event after the wrapped call returned
"""
import functools
import json
import logging
from functools import lru_cache

import dcrai.dcr.dcr_repository as repo
import dcrai.observability.turn_trace as turn_trace
from dcrai import paths, registry

log = logging.getLogger(__name__)

EVENT = 'Panel_Context'
VERSION = 1
LIMIT = 1500           # characters of the JSON value
MAX_FAQS = 2
CAPS = {'said': 200, 'asked': 200, 'field': 80, 'msg': 500}


def _cut(value, limit):
    return value[:limit] if isinstance(value, str) else value


def build(state, previous=None, faq=None):
    """The record to store. faq: {'id', 'said', 'asked'} of a FAQ shown in this request, or None."""
    entries = [dict(f) for f in ((previous or {}).get('faqs') or []) if isinstance(f, dict) and f.get('id')]
    if faq and faq.get('id'):
        entry = {'id': str(faq['id'])}
        said = _cut(faq.get('said'), CAPS['said'])
        asked = _cut(faq.get('asked'), CAPS['asked'])
        if said:
            entry['said'] = said
        if asked and asked != said:
            entry['asked'] = asked
        entries.insert(0, entry)
    record = {'v': VERSION, 'faqs': entries[:MAX_FAQS]}
    field = _cut(((state.get('application_prompt') or {}).get('field') or {}).get('id'), CAPS['field'])
    msg = _cut(state.get('help_last_message'), CAPS['msg'])
    if field:
        record['field'] = field
    if msg:
        record['msg'] = msg
    return record


def _dump(record):
    return json.dumps(record, ensure_ascii=False, separators=(',', ':'))


def fit(record, limit=None):
    """JSON text of the record within the limit, or None when nothing helps. Cuts in order: faqs[1], msg to 200, said
    and asked to 100."""
    limit = LIMIT if limit is None else limit
    record = json.loads(json.dumps(record))
    if len(_dump(record)) <= limit:
        return _dump(record)
    record['faqs'] = record.get('faqs', [])[:1]
    if len(_dump(record)) <= limit:
        return _dump(record)
    if record.get('msg'):
        record['msg'] = record['msg'][:200]
    if len(_dump(record)) <= limit:
        return _dump(record)
    for entry in record['faqs']:
        for key in ('said', 'asked'):
            if entry.get(key):
                entry[key] = entry[key][:100]
    return _dump(record) if len(_dump(record)) <= limit else None


def _event(payload):
    return next((e for e in (payload or {}).get('events', []) if e.get('id') == EVENT), None)


def present(payload):
    """True when the graph has the event and it can be executed."""
    event = _event(payload)
    return bool(event) and event.get('enabled') is True


def read(payload):
    """The stored record, only when the event is executed and the value is a valid version 1 record."""
    event = _event(payload)
    if not event or not event.get('executed') or not event.get('value'):
        return None
    try:
        data = json.loads(str(event['value']))
        while isinstance(data, str):
            data = json.loads(data)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get('v') != VERSION:
        return None
    faqs = data.get('faqs', [])
    if not isinstance(faqs, list) or not all(isinstance(f, dict) and isinstance(f.get('id'), str) for f in faqs):
        return None
    if any(not isinstance(f.get(k, ''), str) for f in faqs for k in ('said', 'asked')):
        return None
    if not isinstance(data.get('field', ''), str) or not isinstance(data.get('msg', ''), str):
        return None
    return data


def current(state, payload):
    """The record the panel should use for its model context, or None to use the session fields.

    Also learns, from the event list the caller already fetched, whether the graph has the event.
    """
    state['panel_context_present'] = present(payload)
    if not registry.flag('PANEL_CONTEXT_IN_DCR') or not state['panel_context_present']:
        return None
    record = read(payload)
    if record is not None and 'panel_context_record' not in state:
        state['panel_context_record'] = record
    return record


@lru_cache(maxsize=4)
def _records(path):
    try:
        with open(path, encoding='utf-8') as handle:
            return {r['id']: (r.get('canonical_question', ''), r.get('topic', ''), r.get('answer_text', ''))
                    for r in json.load(handle)['records']}
    except (OSError, ValueError, KeyError) as error:
        log.warning('FAQ records unavailable for the panel context: %s', type(error).__name__)
        return {}


def expand(faq_id):
    """Canonical question, topic and the start of the answer (whitespace normalised) of a FAQ, or None. Prompt context
    only: an answer shown to the applicant always comes through the DCR search."""
    found = _records(str(paths.FAQ_DATA / 'faq_qa_records.json')).get(faq_id)
    if not found:
        return None
    question, topic, answer = found
    return dict(question=question, topic=topic,
                answer_start=' '.join(str(answer or '').split())[:registry.get('ANSWER_PREVIEW_CHARS')])


def last_faq(record):
    """{id, question, answer_start} of the newest FAQ in the record, or {}."""
    faqs = (record or {}).get('faqs') or []
    if not faqs:
        return {}
    first = faqs[0]
    expanded = expand(first['id']) or {}
    return dict(id=first['id'], question=expanded.get('question') or first.get('asked') or first.get('said') or '',
                answer_start=expanded.get('answer_start', ''))


def last_message(record):
    return (record or {}).get('msg')


def shown_id(state, payload):
    """Id of the FAQ shown last: from the record, else from the session."""
    record = current(state, payload)
    if record is not None:
        return (record.get('faqs') or [{}])[0].get('id')
    return (state.get('help_last_faq') or {}).get('id')


def _write(state, data, before):
    """Execute Panel_Context once for this request. Records the outcome in the turn line as context_write."""
    if not registry.flag('PANEL_CONTEXT_IN_DCR') or state.get('panel_context_present') is not True:
        turn_trace.note(context_write='skipped')
        return
    shown = state.get('help_last_faq') or {}
    faq = None
    if shown.get('id') and shown['id'] != before:
        related = isinstance(data, dict) and data.get('related') is not None
        faq = dict(id=shown['id'],
                   said=shown.get('question') if related else (state.get('help_last_message') or shown.get('question')),
                   asked=None if related else state.get('help_last_rewrite'))
    text = fit(build(state, state.get('panel_context_record'), faq))
    if text is None:
        turn_trace.note(context_write='skipped')
        return
    state['panel_context_record'] = json.loads(text)
    if text == state.get('panel_context_last'):
        turn_trace.note(context_write='skipped')
        return
    try:
        ok = repo.execute_raw_event(state, EVENT, text, 'panel context')
    except Exception as error:
        log.warning('Panel context not written (%s)', type(error).__name__)
        ok = False
    if ok:
        state['panel_context_last'] = text
    else:
        log.warning('Panel context not written; the session fields stay the fallback')
    turn_trace.note(context_write='ok' if ok else 'failed')


def persist(fn):
    """Decorator for panel ask and confirm: after the wrapped call returned, write the context event. A fault here is
    logged and never changes the reply (R25); an exception raised by the wrapped call skips the write."""
    @functools.wraps(fn)
    def wrapper(state, data, *args, **kwargs):
        before = (state.get('help_last_faq') or {}).get('id')
        result = fn(state, data, *args, **kwargs)
        try:
            _write(state, data, before)
        except Exception:
            log.warning('Panel context write failed', exc_info=False)
            turn_trace.note(context_write='failed')
        return result
    return wrapper
