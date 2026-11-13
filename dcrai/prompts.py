"""Loads model instructions from the prompts/ folder.

The text of every instruction the code sends to a model lives in prompts/<area>/<name>.txt, not in Python.
This module only reads it. Names are the path under prompts/ without the extension, for example 'triage/meta'.

    prompts.get('triage/meta')   the instruction text (exactly one trailing newline is stripped)
    prompts.digest(name)         12-character hash of one instruction, for logging which wording a turn used
    prompts.registry()           {name: digest} for every instruction
    prompts.version()            one hash over the whole registry; changes when any wording changes

Runtime values (the graph's policy text, candidate FAQs, the applicant's message) are never stored here.
They are added by the code that calls the model. See prompts/README.md.
"""
import hashlib
import json
from functools import lru_cache

from dcrai import paths


@lru_cache(maxsize=None)
def get(name):
    path = paths.PROMPTS / f'{name}.txt'
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise KeyError(f'No prompt named {name!r} (expected {path})') from None
    return text[:-1] if text.endswith('\n') else text


def names():
    return sorted(p.relative_to(paths.PROMPTS).with_suffix('').as_posix() for p in paths.PROMPTS.rglob('*.txt'))


def digest(name):
    return hashlib.sha256(get(name).encode('utf-8')).hexdigest()[:12]


def registry():
    return {name: digest(name) for name in names()}


def version():
    return hashlib.sha256(json.dumps(registry(), sort_keys=True).encode('utf-8')).hexdigest()[:12]
