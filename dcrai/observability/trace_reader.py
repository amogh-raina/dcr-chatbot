"""Reads the per-interaction JSONL files back (spec 02, 4.2.8).

    python -m dcrai.observability.trace_reader PATH [PATH ...] [--check] [--rates]

    load(path)                lines as dicts; a blank or broken line is skipped and counted (`.skipped`);
                              `.legacy` is true for files written before 2026-10-10 (key `interaction`, no `schema`)
    turns(lines)              the `turn` lines in order, each with `reaction` (the next_action of the faq_reaction line
                              whose `turn` equals its own) and `reaction_line` when there is one
    confirm_accept_rate(lines)  accepted confirms / confirm outcomes (spec 01, 4.6); None when there are no confirms
    re_explain_rate(lines)      re-explained triggers / triggers; None when there are no triggers
    check(lines)              list of problems; empty when the file is complete

Outcome records are the `faq_outcome` lines. A `turn` line that carries an outcome but has no `faq_outcome` line of its
own turn (for example a trace written by another recorder) counts as one.
Exit code of the command line: 1 when --check finds a problem, 0 otherwise.
"""
import argparse
import json
import sys

CONFIRM = 'confirm'
TRIGGER_OUTCOMES = {'clarify', 'offer', 'not_covered'}
TYPED_VIA = {'typed', 'field-typed', 'field-composed', 'rewritten'}


class Lines(list):
    """The lines of one file, plus what was skipped and whether the file is in the old format."""
    skipped = 0
    legacy = False


def load(path):
    lines = Lines()
    with open(path, encoding='utf-8') as handle:
        for text in handle:
            if not text.strip():
                continue
            try:
                line = json.loads(text)
            except ValueError:
                lines.skipped += 1
                continue
            if not isinstance(line, dict):
                lines.skipped += 1
                continue
            if 'interaction_id' not in line and 'interaction' in line:
                line['interaction_id'] = line['interaction']
                if line.get('kind') == 'start' and 'schema' not in line:
                    lines.legacy = True
            lines.append(line)
    return lines


def _legacy(lines):
    if getattr(lines, 'legacy', False):
        return True
    start = next((x for x in lines if x.get('kind') == 'start'), None)
    return bool(start) and 'schema' not in start and 'interaction' in start


def turns(lines):
    """The turn lines, each copied with its reaction joined."""
    reactions = {}
    for line in lines:
        if line.get('kind') == 'faq_reaction' and line.get('turn') is not None:
            reactions.setdefault(line['turn'], line)
    joined = []
    for line in lines:
        if line.get('kind') != 'turn':
            continue
        row = dict(line)
        reaction = reactions.get(line.get('turn'))
        if reaction is not None:
            row['reaction'] = reaction.get('next_action')
            row['reaction_line'] = reaction
        joined.append(row)
    return joined


def _outcomes(lines):
    """Outcome records in file order: faq_outcome lines, plus turn lines whose outcome has no faq_outcome line."""
    # Dedicated outcome records take precedence regardless of their position in the file.
    dedicated = {line.get('turn') for line in lines if line.get('kind') == 'faq_outcome'}
    records, seen = [], set()
    for line in lines:
        number = line.get('turn')
        if line.get('kind') == 'faq_outcome' or (
                line.get('kind') == 'turn' and line.get('outcome') is not None and number not in dedicated):
            if number is None or number not in seen:
                records.append(line)
                seen.add(number)
    return records


def _reaction_of(lines):
    reactions = {}
    for line in lines:
        if line.get('kind') == 'faq_reaction' and line.get('turn') is not None:
            reactions.setdefault(line['turn'], line.get('next_action'))
    return reactions


def confirm_accept_counts(lines):
    confirms = [x for x in _outcomes(lines) if x.get('outcome') == CONFIRM]
    reactions = _reaction_of(lines)
    accepted = sum(reactions.get(x.get('turn')) == 'accepted' for x in confirms)
    return accepted, len(confirms)


def confirm_accept_rate(lines):
    accepted, confirms = confirm_accept_counts(lines)
    return accepted / confirms if confirms else None


def re_explain_counts(lines):
    """(re-explained triggers, triggers). A trigger is a clarify, offer or not_covered outcome, or a confirm the
    applicant rejected. It is re-explained when the next outcome in the file has a typed or rewritten route."""
    records, reaction = _outcomes(lines), _reaction_of(lines)
    triggers = explained = 0
    for index, record in enumerate(records):
        outcome = record.get('outcome')
        if not (outcome in TRIGGER_OUTCOMES or (outcome == CONFIRM and reaction.get(record.get('turn')) == 'rejected')):
            continue
        triggers += 1
        following = records[index + 1] if index + 1 < len(records) else None
        if following is not None and following.get('via') in TYPED_VIA:
            explained += 1
    return explained, triggers


def re_explain_rate(lines):
    explained, triggers = re_explain_counts(lines)
    return explained / triggers if triggers else None


def check(lines):
    """Problems that make a file unusable for the gate: every turn line names its registry version and graph revision."""
    problems = []
    if not lines:
        problems.append('trace is empty')
    if getattr(lines, 'skipped', 0):
        problems.append(f'{lines.skipped} malformed JSON or non-object lines were skipped')
    if lines and not any(x.get('kind') == 'start' for x in lines):
        problems.append('trace has no start record')
    ids = {x.get('interaction_id') or x.get('interaction') for x in lines}
    if len(ids - {None}) > 1:
        problems.append('trace mixes multiple interaction IDs')
    legacy = _legacy(lines)
    previous = None
    for line in lines:
        kind, seq = line.get('kind'), line.get('seq')
        if kind == 'start' and not legacy and 'schema' not in line:
            problems.append(f'line seq={seq}: start line has no schema')
        if kind != 'turn':
            continue
        for key in ('registry_version', 'graph_revision'):
            if not line.get(key):
                problems.append(f'line seq={seq}: turn {line.get("turn")} has no {key}')
        number = line.get('turn')
        if isinstance(number, int):
            if previous is not None and number <= previous:
                problems.append(f'line seq={seq}: turn number goes backwards or repeats ({previous} then {number})')
            previous = number
        elif not legacy:
            problems.append(f'line seq={seq}: turn number is missing or is not an integer')
    return problems


def _percent(value):
    return 'n/a' if value is None else f'{value:.1%}'


def markdown(lines, source='interaction'):
    """Readable export; JSONL remains the source of truth. Does not render raw HTML."""
    def text(value):
        import html
        return html.escape(str(value)).replace('`', '&#96;')

    start = next((x for x in lines if x.get('kind') == 'start'), {})
    out = [f'# Trace: {text(source)}', '',
           f'Interaction: {text(start.get("interaction_id", "unknown"))}', '',
           f'Graph: {text(start.get("graph_revision", start.get("graph_id", "unknown")))}; '
           f'registry: {text(start.get("registry_version", "unknown"))}', '',
           f'Confirm acceptance: {_percent(confirm_accept_rate(lines))}; '
           f're-explain rate: {_percent(re_explain_rate(lines))}', '']
    for row in turns(lines):
        out += [f'## Turn {text(row.get("turn", "?"))} — {text(row.get("interface", "unknown"))}', '',
                f'Entry: {text(row.get("entry", "message"))}; outcome: '
                f'{text(row.get("outcome", row.get("status", "unknown")))}; '
                f'latency: {text(row.get("latency_s", "?"))} s', '']
        for key in ('message', 'input_value', 'reaction', 'error'):
            if row.get(key) is not None:
                out += [f'**{key.replace("_", " ").title()}**', '', text(row[key]), '']
        if row.get('faq_ids'):
            out += ['FAQs: ' + ', '.join(text(x) for x in row['faq_ids']), '']
        for search in row.get('searches') or []:
            out += [f'- Search: {text(search.get("query", ""))}; '
                    f'status: {text(search.get("status", "unknown"))}; '
                    f'kept: {text(", ".join(search.get("kept") or []))}']
        out += ['', f'Model calls: {len(row.get("calls") or [])}; '
                f'DCR events: {len(row.get("dcr_events") or [])}', '']
        if row.get('truncated'):
            out += ['Some detail was omitted by the trace size limit.', '']
    return '\n'.join(out).rstrip() + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m dcrai.observability.trace_reader',
                                     description='Read interaction trace files (JSONL).')
    parser.add_argument('paths', nargs='+', metavar='PATH')
    parser.add_argument('--check', action='store_true', help='fail when a turn line lacks registry_version or graph_revision')
    parser.add_argument('--rates', action='store_true', help='print the confirm accept rate and the re-explain rate')
    parser.add_argument('--format', choices=('summary', 'markdown'), default='summary',
                        help='readable Markdown exports to stdout; keep exports private like the JSONL')
    args = parser.parse_args(argv)
    failed = False
    for path in args.paths:
        lines = load(path)
        if args.format == 'markdown':
            if args.check:
                problems = check(lines)
                for problem in problems:
                    print(f'{path}: {problem}', file=sys.stderr)
                failed = failed or bool(problems)
            print(markdown(lines, path), end='')
            continue
        turn_lines = [x for x in lines if x.get('kind') == 'turn']
        print(f'{path}: {len(lines)} lines, {len(turn_lines)} turns, {lines.skipped} skipped'
              + (', old format' if _legacy(lines) else ''))
        if args.check:
            problems = check(lines)
            for problem in problems:
                print('  PROBLEM ' + problem)
            print('  check: ' + ('FAILED' if problems else 'ok'))
            failed = failed or bool(problems)
        if args.rates:
            accepted, confirms = confirm_accept_counts(lines)
            explained, triggers = re_explain_counts(lines)
            print(f'  confirm accept rate: {_percent(confirm_accept_rate(lines))} ({accepted} of {confirms})')
            print(f'  re-explain rate: {_percent(re_explain_rate(lines))} ({explained} of {triggers})')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
