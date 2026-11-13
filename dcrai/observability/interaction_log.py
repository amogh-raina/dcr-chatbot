"""Structured record of one person's pass through the application.

Written for downstream evaluation, not for the running app: nothing reads these
files back. One JSON Lines file per interaction, appended as it happens, so a
crash or restart keeps whatever came before it.

Each line is one event with a shared envelope:

    {"interaction_id": "...", "seq": 3, "at": "2026-09-15T23:49:19.428+02:00",
     "elapsed_s": 12.4, "kind": "answer", ...}

Files written before 2026-10-10 use the key "interaction" and have no "schema"; dcrai/observability/trace_reader.py
reads both. While a request is being traced (dcrai/observability/turn_trace.py) every line also carries "turn".

Kinds and their payloads:

    start            schema (2), interface (chat | panel; "unknown" when the caller gave none), graph_id,
                     simulation_id, graph_revision (<graph id>@<12 hex of the graph XML held in the session, or
                     @unknown), registry_version (dcrai/registry.py)
    question         field, label, type, multiple, options, pending_count,
                     waiting (other pending fields), asked_count (1 = first
                     time this question was put, >1 = re-asked after an edit)
    interpretation   field, reply, kind, understood, value, display,
                     explanation, attempt (per field, 1-based)
    answer           field, label, type, value (machine), display (human),
                     source: typed | chosen | interpreted | attachment,
                     attempts (interpretations before this stuck),
                     rejections (validation failures before this stuck),
                     seconds_on_question
    rejected         field, reason, value (what was refused)
    edit             field, label, from_value, to_value, source,
                     was_pending (the question on screen when Edit was hit),
                     answered_after (how many answers are being rewound)
    faq_ask          decision (found | same_faq | no_match | unavailable), how (typed | field-typed | field-composed |
                     rewritten | related), tried (the steps taken), candidates (FAQ ids), during (field on screen)
    faq_answer       faq (id), via (as how), during
    handover         reason
    faq_outcome      interface, turn, outcome (answer | confirm | offer | clarify | not_covered), outcome_row,
                     faq_ids (FAQs shown), via (typed | field-typed | field-composed | rewritten | related |
                     chosen | example); no message or FAQ text
    faq_reaction     interface, turn (of the prompt answered), outcome (of that prompt), next_action (accepted |
                     rejected | chose | none_of_these), faq_id (when one was chosen); no text
    finished         status: complete | declined, answers, duration_s
    turn             one per chat message or panel question or confirm, written when the request ends (also when it
                     raises): entry, message (verbatim), input_value, context, calls (every model call as sent and
                     answered), rewrite, searches, outcome fields copied from faq_outcome, reacts_to, status,
                     handover, dcr_events, context_write, error, latency_s, truncated; registry_version and
                     graph_revision on every one. Spec: docs/specs/02-registry-and-trace-record.md, 4.2.3

PRIVACY: every answer the person typed is in here verbatim. The demo asks for
fictional information for exactly this reason. Do not point this at real
applications without deciding retention and access first.
"""
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone

from dcrai import paths, registry

log = logging.getLogger(__name__)

DIRECTORY = str(paths.INTERACTION_LOGS)
ENABLED = os.getenv('INTERACTION_LOG', '1') != '0'
_lock = threading.Lock()
SCHEMA = 2
# Called as observer(state, kind, line) after a line was written. turn_trace registers one at import. A fault in an
# observer is logged and swallowed.
OBSERVERS = []


def graph_revision(graph_id, graph_xml):
    """<graph id>@<12 hex of sha256 over the graph XML held in the session>, or <graph id>@unknown without XML."""
    if not graph_xml:
        return f'{graph_id}@unknown'
    data = graph_xml.encode('utf-8') if isinstance(graph_xml, str) else bytes(graph_xml)
    return f'{graph_id}@{hashlib.sha256(data).hexdigest()[:12]}'


def start(state, graph_id, simulation_id, interface=None):
    """Begin an interaction record. Safe to call when logging is off. interface: 'chat' or 'panel'.

    The start line names the registry version and the graph revision, and the registry snapshot for that version is
    written once. A caller that passes no interface is recorded as 'unknown' with a warning (every call site must pass it).
    """
    if interface is None:
        log.warning('ilog.start called without interface; recorded as unknown')
        interface = 'unknown'
    try:
        registry_version = registry.version()
    except Exception:
        log.warning('Registry version unavailable', exc_info=False)
        registry_version = 'unknown'
    revision = graph_revision(graph_id, state.get('graph_xml'))
    state['interaction'] = dict(id=uuid.uuid4().hex, seq=0, began=time.monotonic(),
                                question_since=None, attempts={}, rejections={},
                                interface=interface, registry_version=registry_version, graph_revision=revision)
    record(state, 'start', schema=SCHEMA, interface=interface, graph_id=graph_id, simulation_id=simulation_id,
           graph_revision=revision, registry_version=registry_version)
    if ENABLED:
        try:
            registry.write_snapshot()
        except Exception:
            log.warning('Registry snapshot not written', exc_info=False)
    return state['interaction']['id']


def _path(interaction_id):
    return os.path.join(DIRECTORY, f'{interaction_id}.jsonl')


def record(state, kind, **fields):
    """Append one event. Never raises: a logging fault must not break the demo."""
    meta = state.get('interaction')
    if not ENABLED or not meta:
        return
    try:
        meta['seq'] += 1
        line = dict(interaction_id=meta['id'], seq=meta['seq'],
                    at=datetime.now(timezone.utc).astimezone().isoformat(timespec='milliseconds'),
                    elapsed_s=round(time.monotonic() - meta['began'], 3), kind=kind)
        if meta.get('turn') is not None and fields.get('turn') is None:
            line['turn'] = meta['turn']      # set by turn_trace for the duration of one request
        line.update({k: v for k, v in fields.items() if v is not None})
        with _lock:
            os.makedirs(DIRECTORY, exist_ok=True)
            with open(_path(meta['id']), 'a', encoding='utf-8') as handle:
                handle.write(json.dumps(line, ensure_ascii=False) + '\n')
    except Exception:
        log.warning('Interaction logging failed kind=%s', kind, exc_info=False)
        return
    for observer in list(OBSERVERS):
        try:
            observer(state, kind, line)
        except Exception:
            log.warning('Interaction observer failed kind=%s', kind, exc_info=False)


def counter(state, bucket, field):
    """Bump and return a per-field counter, for retries and rejections."""
    meta = state.get('interaction')
    if not meta:
        return 0
    meta[bucket][field] = meta[bucket].get(field, 0) + 1
    return meta[bucket][field]


def peek(state, bucket, field):
    meta = state.get('interaction')
    return meta[bucket].get(field, 0) if meta else 0


def clear(state, field):
    """Drop a field's counters once its answer is accepted."""
    meta = state.get('interaction')
    if not meta:
        return
    meta['attempts'].pop(field, None)
    meta['rejections'].pop(field, None)


def mark_question(state):
    """Stamp when the current question went on screen, for time-on-question."""
    meta = state.get('interaction')
    if meta:
        meta['question_since'] = time.monotonic()


def seconds_on_question(state):
    meta = state.get('interaction')
    if not meta or not meta.get('question_since'):
        return None
    return round(time.monotonic() - meta['question_since'], 2)
