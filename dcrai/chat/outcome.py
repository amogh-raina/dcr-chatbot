"""The outcome function: which of seven outcomes a question turn ends in.

Pure code, no I/O, no imports from this repository. Four categorical inputs go into a nine-row table (first match
wins); a Handover rule and two counters sit around it. ROWS is the single source for this module and for the DMN
that tools/clean_graph/dmn_table.py generates, so the two cannot drift.

Inputs
  scope      in_scope | out_of_scope | unsure          from triage
  search     none | single | list                      API decision no_match | single_match | clarify_match
  relevance  none | related | one_answers | several    from the tiers of the kept candidates
  clarified  0 | 1                                     a candidate Clarify was already shown for this question
"""
from typing import NamedTuple, Optional

SCOPES = ('in_scope', 'out_of_scope', 'unsure')
SEARCHES = ('none', 'single', 'list')
RELEVANCE = ('none', 'related', 'one_answers', 'several')
CLARIFIED = (0, 1)
OUTCOMES = ('answer', 'confirm', 'offer', 'clarify', 'not_covered', 'out_of_scope', 'handover')
MISSES_BEFORE_HANDOVER = 2

# (row, (scope, search, relevance, clarified), outcome); None means any. Single source for code and DMN.
ROWS = (
    (1, ('out_of_scope', None, None, None), 'out_of_scope'),
    (2, ('unsure', None, None, None), 'clarify'),
    (3, ('in_scope', 'none', 'none', None), 'not_covered'),
    (4, ('in_scope', 'single', 'one_answers', None), 'answer'),
    (5, ('in_scope', None, 'related', None), 'offer'),
    (6, ('in_scope', 'list', 'one_answers', None), 'confirm'),
    (7, ('in_scope', 'list', 'several', 0), 'clarify'),
    (8, ('in_scope', 'list', 'several', 1), 'offer'),
    (9, (None, None, None, None), 'not_covered'),
)

# The event DCR makes pending for each outcome (existing events are reused).
OUTCOME_EVENT = {'answer': 'Outcome_Answer', 'confirm': 'Outcome_Confirm', 'offer': 'Outcome_Offer',
                 'clarify': 'Outcome_Clarify', 'not_covered': 'FAQ_NoMatch',
                 'out_of_scope': 'FAQ_OutOfScope', 'handover': 'Help_Handover'}

# (search, relevance) pairs the host can produce for an in-scope question.
_VALID_IN_SCOPE = frozenset(
    [('none', 'none')]
    + [('single', r) for r in ('none', 'related', 'one_answers')]
    + [('list', r) for r in RELEVANCE])

DECISIONS = ('no_match', 'single_match', 'clarify_match')
TIERS = ('answers', 'related')


class Decision(NamedTuple):
    outcome: str                       # one of OUTCOMES
    row: Optional[int]                 # 1..9; None only for an explicit request for a person
    table_outcome: str                 # what the table said before the Handover rule (equals outcome otherwise)
    clarify_kind: Optional[str]        # 'scope' (row 2), 'candidates' (row 7), else None
    label: Optional[str]               # 'related' (row 5), 'may_fit' (row 8), else None
    handover_reason: Optional[int]     # 1 asked for a person, 2 second miss; 3 and 4 are set by the caller
    inputs: tuple                      # (scope, search, relevance, clarified) as sent to the table


def _tier(candidate):
    return candidate.get('tier') if isinstance(candidate, dict) else candidate


def _tiers(tiers):
    out = [_tier(t) for t in (tiers or [])]
    for t in out:
        if t not in TIERS:
            raise ValueError('unknown tier %r' % (t,))
    return out


def derive_inputs(decision, tiers):
    """Map the API decision and the tiers of the kept candidates to (search, relevance)."""
    ts = _tiers(tiers)
    answers = ts.count('answers')
    related = ts.count('related')
    if decision == 'no_match':
        if ts:
            raise ValueError('no_match cannot have candidates')
        return 'none', 'none'
    if decision == 'single_match':
        if answers:
            return 'single', 'one_answers'
        if related:
            return 'single', 'related'
        return 'single', 'none'
    if decision == 'clarify_match':
        if answers >= 2:
            return 'list', 'several'
        if answers == 1:
            return 'list', 'one_answers'
        if related:
            return 'list', 'related'
        return 'list', 'none'
    raise ValueError('unknown decision %r' % (decision,))


def _check(scope, search, relevance, clarified):
    if scope not in SCOPES:
        raise ValueError('scope %r' % (scope,))
    if search not in SEARCHES:
        raise ValueError('search %r' % (search,))
    if relevance not in RELEVANCE:
        raise ValueError('relevance %r' % (relevance,))
    if isinstance(clarified, bool) or clarified not in CLARIFIED:
        raise ValueError('clarified %r' % (clarified,))
    # Only an in-scope question runs a search, so only there is the pair constrained. Other scopes are
    # decided by row 1 or 2 whatever else is passed.
    if scope == 'in_scope' and (search, relevance) not in _VALID_IN_SCOPE:
        raise ValueError('combination the host cannot produce: %r' % ((scope, search, relevance, clarified),))


def table(scope, search, relevance, clarified):
    """Return (row, outcome) for the four inputs. First match wins. Raises ValueError outside the domains."""
    _check(scope, search, relevance, clarified)
    values = (scope, search, relevance, clarified)
    for row, cond, outcome in ROWS:
        if all(c is None or c == v for c, v in zip(cond, values)):
            return row, outcome
    raise ValueError('no row matched')   # unreachable: row 9 is all dashes


def decide(scope, decision, tiers, clarified=0, misses=0, asked_person=False, handover_shown=False):
    """The outcome of one question turn. `decision` and `tiers` are only read when scope is in_scope."""
    if asked_person:
        return Decision('handover', None, 'handover', None, None, 1, (scope, 'none', 'none', clarified))
    if scope == 'in_scope':
        search, relevance = derive_inputs(decision, tiers)
    else:
        search, relevance = 'none', 'none'
    row, table_outcome = table(scope, search, relevance, clarified)
    return from_table(row, table_outcome, (scope, search, relevance, clarified), misses, handover_shown)


def from_table(row, table_outcome, inputs, misses=0, handover_shown=False):
    """A Decision from a table result: apply the Handover rule, the clarify kind and the label.

    Used by decide, and by the host when the DMN in DCR supplies the (row, outcome) instead of table().
    """
    outcome, reason = table_outcome, None
    if table_outcome == 'not_covered' and misses + 1 >= MISSES_BEFORE_HANDOVER and not handover_shown:
        outcome, reason = 'handover', 2
    return Decision(outcome, row, table_outcome,
                    {2: 'scope', 7: 'candidates'}.get(row),
                    {5: 'related', 8: 'may_fit'}.get(row),
                    reason, tuple(inputs))


def shown_for(row, candidates):
    """The candidates the reply presents for a row (candidates are dicts with a 'tier')."""
    candidates = list(candidates or [])
    answers = [c for c in candidates if _tier(c) == 'answers']
    related = [c for c in candidates if _tier(c) == 'related']
    if row in (4, 6):
        return answers[:1]
    if row == 5:
        return candidates
    if row in (7, 8):
        return answers + related
    return []


# signal -> (clarified, misses): 'keep' leaves the counter alone, 'inc' adds one, an int sets it.
_COUNTERS = {
    'clarify_candidates': (1, 'keep'),
    'scope_question': ('keep', 'keep'),
    'answered': (0, 0), 'accepted': (0, 0), 'chose': (0, 0),
    'not_covered': ('keep', 'inc'),
    'none_of_these': ('keep', 'inc'), 'rejected': ('keep', 'inc'),
    'handover': ('keep', 0),
    'out_of_scope': (0, 'keep'), 'end': (0, 'keep'),
    'rephrase': ('keep', 'keep'), 'offer': ('keep', 'keep'), 'confirm_shown': ('keep', 'keep'),
}


def _apply(value, rule):
    if rule == 'keep':
        return value
    if rule == 'inc':
        return value + 1
    return rule


def next_clarified(clarified, signal):
    """The clarified flag after a turn or a reaction. A rephrase does not clear it."""
    if signal not in _COUNTERS:
        raise ValueError('unknown signal %r' % (signal,))
    return _apply(clarified, _COUNTERS[signal][0])


def next_misses(misses, signal):
    """The consecutive-miss count after a turn or a reaction."""
    if signal not in _COUNTERS:
        raise ValueError('unknown signal %r' % (signal,))
    return _apply(misses, _COUNTERS[signal][1])
