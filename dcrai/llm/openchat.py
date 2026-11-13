"""OpenAI FAQ ranking only: no DCR execution, graph parsing, or answer generation."""
import json
import logging
import math
import os
import time
from dataclasses import dataclass
from decimal import Decimal

from dcrai import prompts, registry

log = logging.getLogger(__name__)
# SDK debug logs may contain request bodies and headers; use our explicit audit log.
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


class MatchError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    model: str = 'gpt-4.1-mini-2025-04-14'
    single: float = .80
    minimum: float = .50
    margin: float = .12
    maximum: int = 3
    timeout: float = 15

    @classmethod
    def from_env(cls):
        result = cls(registry.get('FAQ_MATCH_MODEL'),
                     registry.get('FAQ_SINGLE_THRESHOLD'),
                     registry.get('FAQ_MIN_THRESHOLD'),
                     registry.get('FAQ_MARGIN_THRESHOLD'),
                     registry.get('FAQ_MAX_CANDIDATES'),
                     registry.get('FAQ_MATCH_TIMEOUT_SECONDS'))
        if not (0 <= result.minimum <= result.single <= 1 and
                0 <= result.margin <= 1 and 1 <= result.maximum <= 3 and
                math.isfinite(result.timeout) and result.timeout > 0 and result.model):
            raise MatchError('Invalid FAQ matcher configuration')
        return result


SYSTEM_PROMPT = prompts.get('forms/rank_system')


def validate_ranking(raw, keys, maximum=3):
    if not isinstance(raw, dict) or set(raw) != {'in_scope', 'scope_reason', 'ranked_matches'}:
        raise MatchError('Malformed ranking')
    if type(raw['in_scope']) is not bool or not isinstance(raw['scope_reason'], str) or not raw['scope_reason'].strip():
        raise MatchError('Malformed scope decision')
    rows = raw['ranked_matches']
    if not isinstance(rows, list) or not 0 <= len(rows) <= maximum:
        raise MatchError('Empty or oversized ranking')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'candidate_key', 'score', 'reason'}:
            raise MatchError('Malformed match')
        key, score = row['candidate_key'], row['score']
        if not isinstance(key, str) or key not in keys or key in seen:
            raise MatchError('Unknown or duplicate candidate')
        if (isinstance(score, bool) or not isinstance(score, (int, float)) or
                not math.isfinite(score) or not 0 <= score <= 1):
            raise MatchError('Invalid score')
        if not isinstance(row['reason'], str):
            raise MatchError('Invalid reason')
        seen.add(key)
    # An explicit scope rejection overrides even a contradictory high score.
    if not raw['in_scope']:
        return []
    return sorted(rows, key=lambda row: row['score'], reverse=True)


def decide(rows, settings):
    if not rows or rows[0]['score'] < settings.minimum:
        return 'no_match', []
    second = rows[1]['score'] if len(rows) > 1 else 0
    margin = Decimal(str(rows[0]['score'])) - Decimal(str(second))
    if rows[0]['score'] >= settings.single and margin >= Decimal(str(settings.margin)):
        return 'single_match', rows[:1]
    return 'ambiguous', [r for r in rows if r['score'] >= settings.minimum][:settings.maximum]


INTERPRET_PROMPT = prompts.get('forms/interpret')


def interpret(message, question, kind, options=None, context=None, client=None, settings=None):
    """Turn free text into a field value. Returns (understood, value, explanation).

    Separate from rank() on purpose: this never sees the FAQ catalogue and
    never returns answer content, only a value for the question being asked.
    """
    settings = settings or Settings.from_env()
    if kind not in ('number', 'integer', 'choice', 'choices'):
        raise MatchError('Unsupported field kind for interpretation')
    values = [o['value'] for o in (options or [])]
    if kind in ('choice', 'choices') and not values:
        raise MatchError('Choice interpretation needs options')
    payload = {'reply': message, 'question': question, 'field_kind': kind,
               'earlier_answers': context or [],
               'options': [{'value': o['value'], 'label': o['label']} for o in (options or [])]}
    if client is None:
        if not os.getenv('OPENAI_API_KEY'):
            raise MatchError('OPENAI_API_KEY is not configured')
        from openai import OpenAI
        client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=settings.timeout, max_retries=0)
    value_schema = ({'type': ['string', 'null'], 'enum': values + [None]} if kind == 'choice'
                    else {'type': ['array', 'null'], 'items': {'type': 'string', 'enum': values}}
                    if kind == 'choices' else {'type': ['number', 'null']})
    schema = {'type': 'object', 'additionalProperties': False,
              'required': ['understood', 'value', 'explanation'],
              'properties': {'understood': {'type': 'boolean'}, 'value': value_schema,
                             'explanation': {'type': 'string'}}}
    started = time.monotonic()
    log.info('Interpret question=%r kind=%s reply=%r', question, kind, message)
    try:
        response = client.responses.create(
            model=settings.model, instructions=INTERPRET_PROMPT,
            input=json.dumps(payload, ensure_ascii=False), store=False,
            timeout=settings.timeout,
            text={'format': {'type': 'json_schema', 'name': 'field_interpretation',
                             'strict': True, 'schema': schema}})
        if response.status != 'completed':
            raise MatchError('Incomplete provider output')
        raw = json.loads(response.output_text)
    except MatchError:
        raise
    except Exception as error:
        log.warning('Interpret failure type=%s latency=%.3f', type(error).__name__, time.monotonic() - started)
        raise MatchError('Interpretation is temporarily unavailable') from error
    understood = bool(raw.get('understood')) and raw.get('value') is not None
    if understood and kind == 'choice' and raw['value'] not in values:
        understood = False
    if understood and kind == 'choices':
        picked = raw['value'] if isinstance(raw['value'], list) else []
        if not picked or any(p not in values for p in picked):
            understood = False
    if understood and kind == 'integer':
        number = raw['value']
        if float(number) != int(number):
            understood = False
    log.info('Interpret understood=%s value=%r latency=%.3f',
             understood, raw.get('value'), time.monotonic() - started)
    return understood, raw.get('value'), str(raw.get('explanation') or '')


def rank(message, last_question, candidates, client=None, settings=None):
    settings = settings or Settings.from_env()
    # Deliberately project data here too, so callers cannot leak event descriptions.
    payload = {'message': message, 'context': {'last_confirmed_question': last_question},
               'candidates': [{'candidate_key': c['candidate_key'], 'question': c['question']}
                              for c in candidates]}
    keys = [c['candidate_key'] for c in candidates]
    if not keys or len(set(keys)) != len(keys):
        raise MatchError('Invalid candidate catalogue')
    if client is None:
        if registry.flag('USE_LOCAL_RETRIEVER') or not os.getenv('OPENAI_API_KEY'):
            try:
                from faq_search.retriever import get_retriever
                retriever = get_retriever()
                decision, rows = retriever.rank_candidates(
                    message, candidates, last_context=last_question,
                    single_threshold=settings.single, min_threshold=settings.minimum, margin_threshold=settings.margin
                )
                if decision == 'clarify_match':
                    decision = 'ambiguous'
                log.info('Local semantic retriever query_chars=%d decision=%s rows=%s', len(message), decision, len(rows))
                return decision, rows
            except Exception as error:
                log.warning('Local retriever unavailable: %s', error)
                if not os.getenv('OPENAI_API_KEY'):
                    raise MatchError('FAQ matching is temporarily unavailable') from error
        if not os.getenv('OPENAI_API_KEY'):
            raise MatchError('OPENAI_API_KEY is not configured')
        from openai import OpenAI
        client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=settings.timeout, max_retries=0)
    schema = {'type': 'object', 'additionalProperties': False,
              'required': ['in_scope', 'scope_reason', 'ranked_matches'],
              'properties': {'in_scope': {'type': 'boolean'},
                             'scope_reason': {'type': 'string'}, 'ranked_matches': {
                  'type': 'array', 'minItems': 0, 'maxItems': settings.maximum,
                  'items': {'type': 'object', 'additionalProperties': False,
                            'required': ['candidate_key', 'score', 'reason'],
                            'properties': {'candidate_key': {'type': 'string', 'enum': keys},
                                           'score': {'type': 'number', 'minimum': 0, 'maximum': 1},
                                           'reason': {'type': 'string'}}}}}}
    started = time.monotonic()
    log.info('FAQ provider=openai model=%s message_chars=%d has_context=%s thresholds=%s',
             settings.model, len(message), bool(last_question), settings)
    for attempt in range(2):
        try:
            response = client.responses.create(
                model=settings.model, instructions=SYSTEM_PROMPT,
                input=json.dumps(payload, ensure_ascii=False), store=False,
                timeout=settings.timeout,
                text={'format': {'type': 'json_schema', 'name': 'faq_ranking',
                                 'strict': True, 'schema': schema}})
        except Exception as error:
            log.warning('FAQ provider failure type=%s latency=%.3f',
                        type(error).__name__, time.monotonic() - started)
            raise MatchError('FAQ matching is temporarily unavailable') from error
        try:
            if response.status != 'completed':
                raise MatchError('Incomplete provider output')
            raw = json.loads(response.output_text)
            rows = validate_ranking(raw, set(keys), settings.maximum)
        except (ValueError, TypeError, AttributeError) as error:
            log.warning('FAQ invalid output attempt=%s type=%s', attempt + 1, type(error).__name__)
            if attempt == 0:
                continue
            raise MatchError('Invalid provider output after one retry') from error
        log.info('FAQ in_scope=%s scope_reason=%r', raw['in_scope'], raw['scope_reason'])
        decision, selected = decide(rows, settings)
        usage = getattr(response, 'usage', None)
        log.info('FAQ ranking=%s decision=%s latency=%.3f usage=%s',
                 [(r['candidate_key'], r['score']) for r in rows], decision,
                 time.monotonic() - started, usage.model_dump() if usage else None)
        return decision, selected
