"""Registry of every behavioural setting, with one version id for the whole configuration.

What it holds: the settings table (name, type, default, class, description) and the readers for it.
What it does not hold: model instruction text (prompts/ does, read through dcrai.prompts) or secrets (never read here).

    registry.get(name)        typed effective value; environment first, then the default; read on every call
    registry.flag(name)       get() for a flag, as a bool
    registry.snapshot()       {'version', 'prompts_version', 'schema', 'prompts', 'settings', 'data'}
    registry.version()        12 hex characters over prompt digests, versioned settings and the two FAQ data digests
    registry.write_snapshot() traces/registry/<version>.json with the full prompt texts, once per version
    registry.describe()       the table as a list of dicts, for docs and checks

Classes. threshold, flag, model, retrieval and constant change behaviour and enter the version. ops and secret do not.
A secret is never read, listed with a value, snapshotted or logged here: get() refuses it.
A value that does not parse as its type gives the default and one warning. A flag is true only for the string 1.
Settings with env=False (the three constants) have no environment variable and always return the default.
"""
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dcrai import paths, prompts

log = logging.getLogger(__name__)

VERSIONED = frozenset({'threshold', 'flag', 'model', 'retrieval', 'constant'})
SCHEMA = 1
DATA_FILES = {'faq_records': 'faq_qa_records.json', 'faq_embeddings_meta': 'faq_embeddings_meta.json'}


@dataclass(frozen=True)
class Setting:
    name: str
    type: str          # flag | float | int | str | path
    default: object
    cls: str           # threshold | flag | model | retrieval | constant | ops | secret
    description: str
    env: bool = True   # False: no environment variable, the default is the value


def _s(name, type_, default, cls, description, env=True):
    return Setting(name, type_, default, cls, description, env)


SETTINGS = {s.name: s for s in [
    _s('DECISIONS_ENABLED', 'flag', False, 'flag', 'Use the Decisions API for triage, panel signals, contextual rewrite and the relevance check.'),
    _s('DECISIONS_MODEL', 'str', 'gpt-6-luna', 'model', 'Model named in every Decisions request.'),
    _s('DECISIONS_TIMEOUT_SECONDS', 'float', 10.0, 'model', 'Timeout of one Decisions request, in seconds.'),
    _s('DECISIONS_TRIAGE_MIN', 'float', 0.6, 'threshold', 'Triage confidence below which a new-question/out-of-scope split is unsure.'),
    _s('DECISIONS_REPLY_MIN', 'float', 0.6, 'threshold', 'Confidence needed to accept a reply to the prompt on screen.'),
    _s('DECISIONS_CONTEXT_MIN', 'float', 0.7, 'threshold', 'Probability that a message depends on context before it is rewritten.'),
    _s('DECISIONS_RELEVANT_MIN', 'float', 0.5, 'threshold', 'Probability that a retrieved FAQ fits the question (legacy relevance check).'),
    _s('DECISIONS_FOLLOWUP_MIN', 'float', 0.7, 'threshold', 'Probability that a modelled follow-up belongs to the answered FAQ.'),
    _s('DECISIONS_DISTRESS_MIN', 'float', 0.7, 'threshold', 'Probability of distress at which the help panel hands over.'),
    _s('FAQ_MATCH_MODEL', 'str', 'gpt-4.1-mini-2025-04-14', 'model', 'Model of the Responses-based fallbacks (not the embedding model).'),
    _s('FAQ_SINGLE_THRESHOLD', 'float', 0.80, 'threshold', 'Score at or above which one FAQ is a single match.'),
    _s('FAQ_MIN_THRESHOLD', 'float', 0.50, 'threshold', 'Score below which a FAQ is not a candidate.'),
    _s('FAQ_MARGIN_THRESHOLD', 'float', 0.12, 'threshold', 'Score gap to the runner-up needed for a single match.'),
    _s('FAQ_MAX_CANDIDATES', 'int', 3, 'threshold', 'Largest number of candidates returned (1 to 3).'),
    _s('FAQ_MATCH_TIMEOUT_SECONDS', 'float', 15.0, 'model', 'Timeout of one Responses call, in seconds.'),
    _s('USE_LOCAL_RETRIEVER', 'flag', True, 'retrieval', 'Rank candidates with the local embedding retriever instead of a model.'),
    _s('FAQ_QUERY_PROMPT', 'str', '', 'retrieval', 'Prompt applied to the user query only when embedding it; empty means none.'),
    _s('CONFIRM_LONE_SURVIVOR', 'flag', True, 'flag', 'Spec 01: confirm a lone surviving candidate instead of answering it directly.'),
    _s('RELEVANCE_TIERS', 'flag', True, 'flag', 'Spec 01: classify candidates as answers or related instead of fits.'),
    _s('PANEL_FALLBACK_REWRITE', 'flag', False, 'flag', 'Spec 01: let the help panel search a rewrite after a failed typed search.'),
    _s('DECISIONS_ANSWERS_MIN', 'float', 0.5, 'threshold', 'Spec 01: probability that a FAQ answers the question (tier answers).'),
    _s('DECISIONS_TOPIC_MIN', 'float', 0.5, 'threshold', 'Spec 01: probability that a FAQ is on the same topic (tier related).'),
    _s('BASE_LAYER_DECISIONS', 'flag', False, 'flag', 'Prefix every Decisions question with prompts/base/decisions.txt. Off until an eval run.'),
    _s('PANEL_CONTEXT_IN_DCR', 'flag', True, 'flag', 'Keep the help panel context in the Panel_Context event of the DCR graph.'),
    _s('OUTCOME_MODE', 'str', 'code', 'flag', 'Spec 03: who decides the turn outcome: code, shadow (code decides, DMN compared) or dcr.'),
    _s('FOLLOWUP_SURFACE', 'str', 'panel', 'flag', 'Spec 03: where follow-up determinations are asked: panel, or chat to restore the old behaviour.'),
    _s('PANEL_TRIAGE', 'flag', True, 'flag', 'Spec 03: the help panel triages unscoped typed messages; 0 restores the unconditional FAQ_Triage = 1.'),
    _s('PROMPT_TTL', 'int', 1800, 'constant', 'Seconds a chat prompt stays answerable.', env=False),
    _s('MISSES_BEFORE_HANDOVER', 'int', 2, 'constant', 'Unanswered panel questions before the handover offer.', env=False),
    _s('ANSWER_PREVIEW_CHARS', 'int', 300, 'constant', 'Characters of the answer shown to the relevance checks.', env=False),
    _s('INTERACTION_LOG', 'str', '1', 'ops', 'Set to 0 to stop writing interaction logs and registry snapshots.'),
    _s('INTERACTION_LOG_DIR', 'path', 'traces/interactions', 'ops', 'Folder of the per-interaction JSONL files.'),
    _s('RUNTIME_TRACE_DIR', 'path', 'traces/runtime', 'ops', 'Folder of simulation snapshots and choice diagnostics.'),
    _s('APPLICATION_ENABLED_FALLBACK', 'flag', False, 'ops', 'Diagnostic switch: treat the application as enabled. Read once at import.'),
    _s('FAQ_API_PORT', 'int', 8090, 'ops', 'Port of the FAQ search API.'),
    _s('FAQ_API_EXTRA_KEYS', 'str', '', 'secret', 'Further accepted keys of the FAQ search API.'),
    _s('FAQ_API_KEY', 'str', '', 'secret', 'Key of the FAQ search API.'),
    _s('OPENAI_API_KEY', 'str', None, 'secret', 'OpenAI key.'),
    _s('API_KEY', 'str', None, 'secret', 'DCR API key.'),
    _s('TOKEN', 'str', None, 'secret', 'DCR bearer token.'),
    _s('ROOT_URL', 'str', None, 'ops', 'Base URL of the DCR REST API.'),
]}


def _parse(setting, raw):
    kind = setting.type
    if kind == 'flag':
        return raw == '1'
    if kind == 'float':
        return float(raw)
    if kind == 'int':
        return int(raw)
    return raw


def get(name):
    """Typed effective value. Environment first, then the default. Read on every call, never cached."""
    try:
        setting = SETTINGS[name]
    except KeyError:
        raise KeyError(f'Unknown setting {name!r}; add it to dcrai/registry.py') from None
    if setting.cls == 'secret':
        raise KeyError(f'{name} is a secret and is never read through the registry')
    if not setting.env:
        return setting.default
    raw = os.environ.get(name)
    if raw is None:
        return setting.default
    try:
        return _parse(setting, raw)
    except ValueError:
        log.warning('Setting %s has an unparsable value; using the default %r', name, setting.default)
        return setting.default


def flag(name):
    """A flag as a bool: true only for the string 1."""
    value = get(name)
    if SETTINGS[name].type != 'flag':
        raise TypeError(f'{name} is not a flag')
    return value


def describe():
    """The table as dicts. Secrets carry no value."""
    rows = []
    for s in SETTINGS.values():
        row = dict(name=s.name, type=s.type, default=s.default, cls=s.cls, description=s.description, env=s.env)
        if s.cls != 'secret':
            row['value'] = get(s.name)
        else:
            row['default'] = None
        rows.append(row)
    return rows


_digests = {}


def _file_digest(path):
    """12 hex characters over the file bytes, cached by (mtime_ns, size). 'missing' when the file is absent."""
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        return 'missing'
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _digests.get(str(path))
    if cached and cached[0] == key:
        return cached[1]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    _digests[str(path)] = (key, digest)
    return digest


def snapshot():
    """Everything that decides behaviour, with its version. Secrets and ops settings are left out."""
    values = {n: get(n) for n, s in SETTINGS.items() if s.cls in VERSIONED}
    data = {key: _file_digest(paths.FAQ_DATA / filename) for key, filename in DATA_FILES.items()}
    body = {'schema': SCHEMA, 'prompts': prompts.registry(), 'settings': values, 'data': data}
    version = hashlib.sha256(json.dumps(body, sort_keys=True).encode('utf-8')).hexdigest()[:12]
    return dict(version=version, prompts_version=prompts.version(), **body)


def version():
    return snapshot()['version']


def write_snapshot(directory=None):
    """Write <version>.json with the full prompt texts, once. Returns the path. Does nothing when it exists."""
    directory = Path(directory if directory is not None else paths.REGISTRY_SNAPSHOTS)
    snap = snapshot()
    target = directory / f"{snap['version']}.json"
    if target.exists():
        return target
    snap['prompt_texts'] = {name: prompts.get(name) for name in snap['prompts']}
    directory.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.tmp')
    temporary.write_text(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    os.replace(temporary, target)
    return target
