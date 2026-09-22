"""Structured record of one person's pass through the application.

Written for downstream evaluation, not for the running app: nothing reads these
files back. One JSON Lines file per interaction, appended as it happens, so a
crash or restart keeps whatever came before it.

Each line is one event with a shared envelope:

    {"interaction": "...", "seq": 3, "at": "2026-09-15T23:49:19.428+02:00",
     "elapsed_s": 12.4, "kind": "answer", ...}

Kinds and their payloads:

    start            graph_id, simulation_id
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
    faq_ask          message, decision, candidates
    faq_answer       field (the canonical question), question, answer_event
    finished         status: complete | declined, answers, duration_s

PRIVACY: every answer the person typed is in here verbatim. The demo asks for
fictional information for exactly this reason. Do not point this at real
applications without deciding retention and access first.
"""
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone

log = logging.getLogger(__name__)

DIRECTORY = os.getenv('INTERACTION_LOG_DIR', 'interaction_logs')
ENABLED = os.getenv('INTERACTION_LOG', '1') != '0'
_lock = threading.Lock()


def start(state, graph_id, simulation_id):
    """Begin an interaction record. Safe to call when logging is off."""
    state['interaction'] = dict(id=uuid.uuid4().hex, seq=0, began=time.monotonic(),
                                question_since=None, attempts={}, rejections={})
    record(state, 'start', graph_id=graph_id, simulation_id=simulation_id)
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
        line = dict(interaction=meta['id'], seq=meta['seq'],
                    at=datetime.now(timezone.utc).astimezone().isoformat(timespec='milliseconds'),
                    elapsed_s=round(time.monotonic() - meta['began'], 3), kind=kind)
        line.update({k: v for k, v in fields.items() if v is not None})
        with _lock:
            os.makedirs(DIRECTORY, exist_ok=True)
            with open(_path(meta['id']), 'a', encoding='utf-8') as handle:
                handle.write(json.dumps(line, ensure_ascii=False) + '\n')
    except Exception:
        log.warning('Interaction logging failed kind=%s', kind, exc_info=False)


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
