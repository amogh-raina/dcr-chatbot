"""One verbatim `turn` line per request, in the interaction's JSONL file (spec 02, section 4.2).

A request is one call of chat `handle`, panel `ask` or panel `confirm`. The decorator `turn(interface)` opens a recorder
in a context variable, the hooks (model calls, searches, DCR events) add records to it while the request runs, and one
`turn` line is written when the request ends, also when it raises. Outside a request every hook does nothing, so form
answers, evals and tests are unaffected.

    @turn_trace.turn('chat')   decorator for a request entry point; increments state['turn'], writes the turn line
    turn_trace.active()        the open recorder or None
    turn_trace.note(**fields)  add fields to the open turn line (for example context=...)
    turn_trace.add_call(record), add_search(record), add_dcr_event(record)    hooks; return the record's index or None
    @turn_trace.traced_search  decorator for rr.search: one search record per call (query, scores, relevance, kept ids)
    turn_trace.observe(...)    registered in interaction_log.OBSERVERS: copies faq_outcome, faq_reaction and handover
                               lines written during the request into the turn line

Tracing never changes a reply, raises, calls a model or calls DCR. A fault is logged at warning level and swallowed
(R18). Strings longer than MAX_STRING are cut with a marker and the line gets `truncated: true` (R20).
"""
import contextvars
import functools
import json
import logging
import re
import time

from dcrai import registry
import dcrai.observability.interaction_log as ilog

log = logging.getLogger(__name__)

MAX_STRING = 20000          # characters of any one string in a turn line (R20)
MAX_LINE = 256 * 1024       # bytes of one turn line before strings are cut harder (R20)
OUTCOME_KEYS = ('outcome', 'outcome_row', 'faq_ids', 'via', 'outcome_inputs')
CHAT_ACTIONS = ('reply', 'example', 'end', 'rephrase', 'apply')

_current = contextvars.ContextVar('turn_record', default=None)


def active():
    """The recorder of the request being handled, or None outside a request."""
    return _current.get()


def _describe(interface, name, data):
    """entry, message and input_value of a request, from the data the entry point received."""
    data = data if isinstance(data, dict) else {}
    out = {}
    if interface == 'chat':
        action = data.get('action')
        entry = action if isinstance(action, str) and action else 'message'
        if entry == 'reply':
            out['input_value'] = data.get('value')
        elif entry == 'example':
            out['input_value'] = data.get('faq_id')
    elif name == 'confirm':
        entry = 'confirm'
        out['input_value'] = data.get('candidate_key')
    elif data.get('related') is not None:
        entry = 'related'
        out['input_value'] = data.get('related')
    else:
        entry = 'message'
    if entry == 'message' and isinstance(data.get('message'), str):
        out['message'] = data['message']
    out['entry'] = entry
    if out.get('input_value') is not None:
        out['input_value'] = str(out['input_value'])
    return out


def _cut(value, limit, flag):
    if isinstance(value, str):
        if len(value) > limit:
            flag.append(True)
            return value[:limit] + f'...[cut {len(value) - limit} characters]'
        return value
    if isinstance(value, dict):
        return {k: _cut(v, limit, flag) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_cut(v, limit, flag) for v in value]
    return value


def _limit(fields):
    """JSON-safe copy of the fields with long strings cut. Returns (fields, truncated)."""
    flag = []
    safe = json.loads(json.dumps(fields, ensure_ascii=False, default=str))
    cut = _cut(safe, MAX_STRING, flag)
    for limit in (4000, 1000):
        if len(json.dumps(cut, ensure_ascii=False).encode('utf-8')) <= MAX_LINE:
            break
        cut = _cut(cut, limit, flag)
    omitted = []
    while len(json.dumps(cut, ensure_ascii=False).encode('utf-8')) > MAX_LINE - 1024:
        # Keep the envelope/outcome and omit the largest detail field explicitly.
        candidates = [k for k in ('calls', 'searches', 'dcr_events', 'context', 'context_write', 'message',
                                  'input_value', 'rewrite', 'outcome_inputs') if k in cut]
        if not candidates:
            # Defensive fallback for oversized caller-supplied extra fields.
            candidates = [k for k in cut if k not in ('schema', 'turn', 'interface', 'registry_version',
                                                      'graph_revision', 'status', 'outcome')]
        if not candidates:
            break
        key = max(candidates, key=lambda k: len(json.dumps(cut[k], ensure_ascii=False).encode('utf-8')))
        cut.pop(key)
        omitted.append(key)
        flag.append(True)
    if omitted:
        cut['omitted_fields'] = omitted
    return cut, bool(flag)


class Recorder:
    def __init__(self, state, interface, fields, turn_number, version):
        self.state = state
        self.interface = interface
        self.fields = fields
        self.turn = turn_number
        self.registry_version = version
        self.calls, self.searches, self.dcr_events = [], [], []
        self.started = time.monotonic()

    def finish(self, result):
        try:
            if isinstance(result, dict) and result.get('status') is not None:
                self.fields['status'] = str(result['status'])
        except Exception:
            log.warning('Turn trace finish failed', exc_info=False)

    def fail(self, error):
        self.fields['error'] = type(error).__name__

    def rewrite(self):
        """{from, text, call} of the first query_rewrite call, or None."""
        for index, call in enumerate(self.calls):
            if call.get('name') == 'query_rewrite':
                payload = call.get('input')
                output = call.get('output')
                return {'from': payload.get('message') if isinstance(payload, dict) else None,
                        'text': output.get('search_query') if isinstance(output, dict) else None, 'call': index}
        return None

    def write(self):
        """Append the turn line. Never raises."""
        meta = self.state.get('interaction') if isinstance(self.state, dict) else None
        try:
            fields = dict(self.fields)
            fields.update(
                schema=ilog.SCHEMA, simulation_id=self.state.get('simulation_id'), interface=self.interface,
                turn=self.turn,
                registry_version=self.registry_version or (meta or {}).get('registry_version'),
                graph_revision=(meta or {}).get('graph_revision'),
                calls=self.calls or None, rewrite=self.rewrite(), searches=self.searches or None,
                dcr_events=self.dcr_events or None,
                latency_s=round(time.monotonic() - self.started, 3))
            fields, truncated = _limit(fields)
            if truncated:
                fields['truncated'] = True
            ilog.record(self.state, 'turn', **fields)
        except Exception:
            log.warning('Turn trace write failed', exc_info=False)
        finally:
            if meta is not None:
                meta.pop('turn', None)


def _open(state, interface, name, args, kwargs):
    """Count the request and open its recorder. Returns None when that fails."""
    try:
        state['turn'] = int(state.get('turn') or 0) + 1
        meta = state.get('interaction')
        if meta is not None:
            meta['turn'] = state['turn']
        data = args[0] if args else kwargs.get('data')
        try:
            version = registry.version()
        except Exception:
            log.warning('Registry version unavailable for a turn', exc_info=False)
            version = None
        return Recorder(state, interface, _describe(interface, name, data), state['turn'], version)
    except Exception:
        log.warning('Turn trace could not open', exc_info=False)
        return None


def turn(interface):
    """Decorator for a request entry point whose first argument is the session state."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(state, *args, **kwargs):
            if _current.get() is not None:      # already inside a traced request: one line per request
                return fn(state, *args, **kwargs)
            recorder = _open(state, interface, fn.__name__, args, kwargs)
            if recorder is None:
                return fn(state, *args, **kwargs)
            token = _current.set(recorder)
            try:
                result = fn(state, *args, **kwargs)
                recorder.finish(result)
                return result
            except BaseException as error:
                recorder.fail(error)
                raise
            finally:
                _current.reset(token)
                recorder.write()
        return wrapper
    return decorate


def note(**fields):
    """Add fields to the open turn line. No-op outside a request."""
    recorder = _current.get()
    if recorder is None:
        return
    try:
        recorder.fields.update({k: v for k, v in fields.items() if v is not None})
    except Exception:
        log.warning('Turn trace note failed', exc_info=False)


def _add(bucket, record):
    recorder = _current.get()
    if recorder is None:
        return None
    try:
        getattr(recorder, bucket).append(record)
        return len(getattr(recorder, bucket)) - 1
    except Exception:
        log.warning('Turn trace %s record failed', bucket, exc_info=False)
        return None


def add_call(record):
    """One model call (spec 02, 4.2.4). Returns its index in the turn's calls, or None outside a request."""
    return _add('calls', record)


def add_search(record):
    """One rr.search call (4.2.5)."""
    return _add('searches', record)


def add_dcr_event(record):
    """One execute_raw_event call (4.2.6)."""
    return _add('dcr_events', record)


RELEVANCE_QUESTION = re.compile(r'^(fits|answers|topic)_(\d+)$')
HELP_COMMENT = re.compile(r'application help \(([^)]+)\)')


def _retrieval_payload(state):
    """The FAQ_RetrievalOk value of the last event list, parsed, or None. Same reading rule as rr.search."""
    after = (state.get('simulation_state') or {}).get('events') or []
    ok = next((e for e in after if e.get('id') == 'FAQ_RetrievalOk'), None)
    if not ok or not ok.get('executed'):
        return None
    data = json.loads(ok.get('value') or '')
    while isinstance(data, str):
        data = json.loads(data)
    return data if isinstance(data, dict) else None


def _relevance(calls, ids):
    """{id: {fits | answers, topic: probability}} from the Decisions calls made during one search, by candidate order."""
    out = {}
    for call in calls:
        output = call.get('output')
        if call.get('api') != 'decisions' or not isinstance(output, dict):
            continue
        for name, answer in output.items():
            match = RELEVANCE_QUESTION.match(str(name))
            if not match or int(match.group(2)) >= len(ids) or not isinstance(answer, dict):
                continue
            if answer.get('probability') is not None:
                out.setdefault(ids[int(match.group(2))], {})[match.group(1)] = answer['probability']
    return out


def _search_record(recorder, state, args, kwargs, result, mark, started, error):
    query = args[0] if args else kwargs.get('query')
    comment = args[1] if len(args) > 1 else kwargs.get('comment', '')
    judge = args[2] if len(args) > 2 else kwargs.get('judge')
    record = {'query': query, 'judge': judge or query}
    how = HELP_COMMENT.search(comment or '')
    if how:
        record['how'] = how.group(1)
    if error:
        record['error'] = error
    status = result[0] if isinstance(result, tuple) and result else None
    if status:
        record['status'] = status
    if status in ('found', 'no_match'):
        data = _retrieval_payload(state)
        if data:
            record['decision'] = data.get('decision')
            record['top_score'] = data.get('score')
            scores = {data[f'option{n}_id']: data.get(f'option{n}_score') for n in (1, 2, 3)
                      if data.get(f'option{n}_id') and data.get(f'option{n}_score') is not None}
            if scores:
                record['option_scores'] = scores
        retrieved = (state.get('last_search') or {}).get('retrieved')
        if retrieved is not None:
            record['retrieved'] = list(retrieved)
            relevance = _relevance(recorder.calls[mark:], list(retrieved))
            if relevance:
                record['relevance'] = relevance
        kept = result[1] if len(result) > 1 and isinstance(result[1], list) else []
        record['kept'] = [c.get('id') for c in kept if isinstance(c, dict)]
        tiers = {c['id']: c['tier'] for c in kept if isinstance(c, dict) and c.get('tier') and c.get('id')}
        if tiers:
            record['tiers'] = tiers
    record['latency_s'] = round(time.monotonic() - started, 3)
    return record


def traced_search(fn):
    """Decorator for rr.search(state, query, comment='', judge=None): add one search record to the open turn.

    Reads the API payload back from state['simulation_state'] (FAQ_RetrievalOk), the retrieved ids from
    state['last_search'], the kept candidates and their tiers from the return value, and the relevance probabilities from
    the Decisions calls made during the search. Never changes the result or raises.
    """
    @functools.wraps(fn)
    def wrapper(state, *args, **kwargs):
        recorder = _current.get()
        if recorder is None:
            return fn(state, *args, **kwargs)
        mark, started, result, error = len(recorder.calls), time.monotonic(), None, None
        try:
            result = fn(state, *args, **kwargs)
            return result
        except BaseException as caught:
            error = type(caught).__name__
            raise
        finally:
            try:
                recorder.searches.append(_search_record(recorder, state, args, kwargs, result, mark, started, error))
            except Exception:
                log.warning('Search not traced', exc_info=False)
    return wrapper


def observe(state, kind, line):
    """Copy the lines other code writes during a request into the turn line (interaction_log observer)."""
    recorder = _current.get()
    if recorder is None:
        return
    if kind == 'faq_outcome':
        for key in OUTCOME_KEYS:
            if line.get(key) is not None:
                recorder.fields[key] = line[key]
    elif kind == 'faq_reaction':
        if line.get('turn') is not None:
            recorder.fields['reacts_to'] = line['turn']
    elif kind == 'handover':
        recorder.fields['handover'] = {'reason': line.get('reason')}


if observe not in ilog.OBSERVERS:
    ilog.OBSERVERS.append(observe)
