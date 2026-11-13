"""Live outcome eval: drives the real Portal graph and the running app, scores against the spec gates.

Two parts. Both need the Portal credentials in .env (API_KEY, TOKEN, ROOT_URL).

    python -m evals.eval_live table --graph 2014118
        The nine rows of the outcome table through the Portal, no model, no app. For each input set it executes
        TurnStart and the four gates, reads TurnResult, executes TurnOutcome and checks which outcome event is
        pending. Run once per input set in a fresh simulation, then all input sets in one simulation (the table
        must run again each turn: fixture F4). It also settles fixture F1 (the REST event list shows the result).

    python -m evals.eval_live panel --graph 2014118 --base http://127.0.0.1:8080 --expect-mode shadow --repeat 3
        The Help panel over HTTP against a running `python app.py` (restart it after changing .env). It replays the
        follow-up eval cases (groups F, C, N, S, T, A, O, M; V needs a field on screen and is skipped) as real
        two-turn sessions, then runs the mechanics scenarios (misses and handover, person request, deadline words,
        out of scope, Confirm accept and reject). Every turn is read back from traces/interactions and checked.

Gates reported (spec 01 5.5, spec 03 6): WRONG = 0; every logged row equals the table for its logged inputs;
in shadow no mismatch, in dcr every turn has source dcr; the second miss in a row carries a handover, once.
Exit code 1 when a gate fails. Writes evals/reports/live_outcome_report.md and evals/runs/live_outcome_results.json
(the table part writes evals/reports/live_table_report.md).
"""
import argparse
import json
import os
import statistics
import sys
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')

from dcrai import paths  # noqa: E402
from dcrai.chat import outcome as oc  # noqa: E402

CASES = HERE / 'cases' / 'eval_followup_queries.json'
REPORT = HERE / 'reports' / 'live_outcome_report.md'
RESULTS = HERE / 'runs' / 'live_outcome_results.json'

# Representative inputs per row (spec 03 7.2) plus the two extra in-scope pairs the host can produce.
TABLE_CASES = [
    ('out_of_scope', 'none', 'none', 0), ('unsure', 'none', 'none', 0), ('in_scope', 'none', 'none', 0),
    ('in_scope', 'single', 'one_answers', 0), ('in_scope', 'list', 'related', 0),
    ('in_scope', 'list', 'one_answers', 0), ('in_scope', 'list', 'several', 0), ('in_scope', 'list', 'several', 1),
    ('in_scope', 'list', 'none', 0), ('in_scope', 'single', 'related', 0), ('in_scope', 'single', 'none', 0),
]

# In-scope questions the FAQ is not expected to cover; used to produce misses. Some may be answered or offered.
MISS_POOL = ['will you also send me a text message?', 'what if they pay me in gift cards instead of money?',
             'do you have a mobile app?', 'can I bring my dog to the meeting?', 'can I pay to have it processed faster?']
PERSON_YES = ['can I speak to a caseworker?', 'I want to talk to somebody', "I'd like to talk to a real person",
              'can I call someone about my case']
PERSON_PROBE = ['I need a human', 'put me through to an advisor', 'give me a phone number',
                'kan jeg tale med en sagsbehandler']
OUT_OF_SCOPE = ["what's the weather like in Copenhagen today?", 'how do I apply for housing benefit?',
                'will I get the supplement with my condition?']
CONFIRM_POOL = ['what medical documentation do i need to provide in my application?', 'which documents do I need?',
                'what counts as proof of my condition?']
URGENT_MSG = 'how do I appeal a decision?'
GROUPS = 'FCNSTAOM'
ALL_VIOLATIONS = []   # (message, violation) from every session of the run, mechanics included


# ----------------------------------------------------------------------------------------------- scoring

def kind_of(line):
    """The shape of a turn from its faq_outcome log line."""
    if not line:
        return 'none'
    if line.get('same_faq'):
        return 'same_faq'
    return line.get('outcome') or 'none'


def grade(expect, line):
    """Verdict for one replayed case. expect is the case's expect object; line the final faq_outcome line."""
    kind, ids = kind_of(line), list((line or {}).get('faq_ids') or [])
    if 'no_answer' in expect:
        if kind == 'none':
            return 'missed'
        return {'answer': 'WRONG', 'confirm': 'confirm_unneeded', 'offer': 'shown_options',
                'clarify': 'shown_options'}.get(kind, 'correct')
    want = set(expect.get('answer') or expect.get('same_or_answer') or [])
    if kind == 'answer':
        return 'correct' if want & set(ids) else 'WRONG'
    if kind == 'same_faq':
        return 'correct' if 'same_or_answer' in expect else 'missed'
    if kind == 'confirm':
        return 'confirm_right' if want & set(ids) else 'confirm_wrong'
    if kind in ('offer', 'clarify'):
        return 'partial' if want & set(ids) else 'options_miss'
    return 'missed'


def check_line(line, expect_mode):
    """Invariants on one logged outcome line. Returns a list of violation strings."""
    out = []
    inputs = line.get('outcome_inputs')
    row = line.get('outcome_row')
    if inputs and row is not None:
        try:
            table_row, _ = oc.table(inputs['scope'], inputs['search'], inputs['relevance'], inputs['clarified'])
        except (KeyError, ValueError) as exc:
            out.append('inputs not valid for the table: %s' % exc)
        else:
            if table_row != row:
                out.append('logged row %s but the table gives %s for %s' % (row, table_row, inputs))
    if line.get('outcome_mismatch'):
        out.append('DMN and code disagree: code row %s, DMN row %s' % (row, line.get('outcome_row_dcr')))
    if inputs and row is not None and expect_mode in ('shadow', 'dcr'):
        if line.get('outcome_dcr') is None:
            out.append('mode %s but no DMN result in the log (the table did not run)' % expect_mode)
        if expect_mode == 'dcr' and line.get('outcome_source') != 'dcr':
            out.append('mode dcr but outcome_source is %s' % line.get('outcome_source'))
    if expect_mode == 'code' and line.get('outcome_dcr') is not None:
        out.append('mode code but the log has a DMN result')
    if line.get('outcome_source') == 'failclosed':
        out.append('failed closed to not_covered')
    return out


def summarize(turns):
    """Metrics over a list of turn dicts (each with kind, row, source, latency, mismatch)."""
    mix = Counter((t['kind'], t.get('row')) for t in turns if t.get('kind') not in (None, 'none'))
    lat = sorted(t['latency'] for t in turns if t.get('latency') is not None)
    return dict(turns=len(turns), mix=mix, sources=Counter(t.get('source') for t in turns if t.get('source')),
                mismatches=sum(1 for t in turns if t.get('mismatch')),
                median=statistics.median(lat) if lat else None, p95=lat[int(0.95 * (len(lat) - 1))] if lat else None)


# ----------------------------------------------------------------------------------------------- panel driver

class Panel:
    """One panel session against a running app, with its interaction log read back after each call."""

    def __init__(self, base, graph):
        import requests
        self.http, self.base, self.graph = requests.Session(), base.rstrip('/'), str(graph)
        self.sid = uuid.uuid4().hex
        self.http.headers['X-Session-ID'] = self.sid
        self.log_path, self.offset, self.turns, self.violations = None, 0, [], []

    def _post(self, route, body):
        t0 = time.time()
        r = self.http.post(self.base + route, json=body, timeout=120)
        try:
            data = r.json()
        except ValueError:
            data = {'error': r.text[:200]}
        return r.status_code, data, round(time.time() - t0, 2)

    def start(self):
        before = {p.name for p in paths.INTERACTION_LOGS.glob('*.jsonl')}
        code, data, _ = self._post('/application/init', {'demo_continue': True, 'graph_id': self.graph})
        if code != 200:
            raise RuntimeError('init failed (%s): %s' % (code, data))
        deadline = time.time() + 5
        while time.time() < deadline and not self.log_path:
            fresh = [p for p in paths.INTERACTION_LOGS.glob('*.jsonl') if p.name not in before]
            if fresh:
                self.log_path = max(fresh, key=lambda p: p.stat().st_mtime)
            else:
                time.sleep(0.2)
        if not self.log_path:
            raise RuntimeError('no new interaction log appeared; is the app writing to %s?' % paths.INTERACTION_LOGS)
        self._new_lines()
        return data

    def _new_lines(self):
        if not self.log_path or not self.log_path.exists():
            return []
        with open(self.log_path, encoding='utf-8') as fh:
            fh.seek(self.offset)
            text = fh.read()
            self.offset = fh.tell()
        rows = []
        for raw in text.splitlines():
            try:
                rows.append(json.loads(raw))
            except ValueError:
                pass
        return rows

    def ask(self, message, expect_mode=None, **extra):
        code, data, latency = self._post('/application/ask', dict(message=message, **extra))
        time.sleep(0.15)
        rows = self._new_lines()
        outcomes = [r for r in rows if r.get('kind') == 'faq_outcome']
        line = outcomes[-1] if outcomes else None
        handovers = [r for r in rows if r.get('kind') == 'handover']
        turn = dict(message=message, http=code, status=data.get('status'), latency=latency, line=line,
                    kind=kind_of(line), row=(line or {}).get('outcome_row'), source=(line or {}).get('outcome_source'),
                    mismatch=bool((line or {}).get('outcome_mismatch')), handover=bool(data.get('handover')),
                    handover_reasons=[h.get('reason') for h in handovers], data=data,
                    searched=any(r.get('kind') == 'faq_ask' and r.get('decision') != 'out_of_scope' for r in rows), error=data.get('error'))
        turn['violations'] = check_line(line, expect_mode) if line else []
        self.violations += turn['violations']
        ALL_VIOLATIONS.extend((message, v) for v in turn['violations'])
        self.turns.append(turn)
        return turn

    def react(self, turn, accept, key=None):
        data = turn['data']
        body = dict(match_id=data.get('match_id'),
                    candidate_key=(key or data['candidates'][0]['candidate_key'] if accept else 'none'))
        code, out, _ = self._post('/application/confirm', body)
        time.sleep(0.15)
        self._new_lines()
        return code, out


def replay_cases(base, graph, repeat, expect_mode, only=None, progress=print):
    cases = [c for c in json.loads(CASES.read_text(encoding='utf-8'))['queries'] if c['group'] in GROUPS]
    if only:
        cases = [c for c in cases if c['id'] in only]
    results = []
    for case in cases:
        for rep in range(repeat):
            p = Panel(base, graph)
            try:
                p.start()
                context = None
                if case.get('previous'):
                    first = p.ask(case['previous'], expect_mode)
                    context = first['kind'] == 'answer'
                    keys = [c['candidate_key'] for c in first['data'].get('candidates') or []]
                    want = case.get('previous_faq')
                    if first['status'] in ('faq_confirm', 'faq_related', 'faq_clarify') and keys and \
                            (want in keys or first['status'] == 'faq_confirm'):
                        p.react(first, True, key=want if want in keys else None)   # the click a person would make
                        context = True
                turn = p.ask(case['message'], expect_mode)
                verdict = grade(case['expect'], turn['line'])
                results.append(dict(id=case['id'], group=case['group'], rep=rep, verdict=verdict, kind=turn['kind'], context=context,
                                    row=turn['row'], status=turn['status'], faq_ids=(turn['line'] or {}).get('faq_ids'),
                                    source=turn['source'], mismatch=turn['mismatch'], latency=turn['latency'],
                                    violations=p.violations, error=turn['error'], expect=case['expect']))
            except Exception as exc:   # one broken session must not stop the run
                results.append(dict(id=case['id'], group=case['group'], rep=rep, verdict='error', error=str(exc),
                                    violations=[], kind='none', row=None, source=None, mismatch=False, latency=None,
                                    context=None, expect=case['expect']))
            progress('  %s r%d %s' % (case['id'], rep + 1, results[-1]['verdict']))
    return results


def scenarios(base, graph, expect_mode, progress=print):
    """The mechanics scenarios. Each entry has status pass, FAIL, inconclusive or info."""
    out = []

    def add(name, status, detail=''):
        out.append(dict(name=name, status=status, detail=detail))
        progress('  %s: %s %s' % (name, status, detail))

    # Misses and handover: the second miss in a row hands over; later misses do not hand over again.
    p = Panel(base, graph)
    p.start()
    misses, second, later, again = 0, None, 0, False
    for message in MISS_POOL:
        t = p.ask(message, expect_mode)
        is_miss = t['kind'] == 'not_covered' or (t['kind'] == 'handover' and t['row'] is not None)
        if second is None:
            if is_miss:
                misses += 1
                if misses == 2:
                    second = t['kind'] == 'handover'
            elif t['kind'] in ('answer', 'confirm'):
                misses = 0   # a good answer resets the count
        elif is_miss:
            later += 1
            again = again or t['kind'] == 'handover'
    if second is None:
        add('second miss carries a handover', 'inconclusive', 'two misses in a row were not produced by the pool')
    else:
        add('second miss carries a handover', 'pass' if second else 'FAIL')
        add('no second handover after it', 'FAIL' if again else ('pass' if later else 'inconclusive'),
            '%d later misses' % later)

    # Explicit request for a person.
    for message in PERSON_YES:
        p = Panel(base, graph)
        p.start()
        t = p.ask(message, expect_mode)
        add('person request: ' + message, 'pass' if t['status'] == 'handover' else 'FAIL', 'status %s' % t['status'])
    for message in PERSON_PROBE:
        p = Panel(base, graph)
        p.start()
        t = p.ask(message, expect_mode)
        add('probe (no expectation): ' + message, 'info', 'status %s, outcome %s' % (t['status'], t['kind']))

    # Deadline or appeal wording: a handover block once per session.
    p = Panel(base, graph)
    p.start()
    first, again = p.ask(URGENT_MSG, expect_mode), p.ask(URGENT_MSG + ' and how long do I have?', expect_mode)
    add('deadline wording gives a handover block once',
        'pass' if first['handover'] and not again['handover'] else 'FAIL',
        'first %s, second %s' % (first['handover'], again['handover']))

    # Out of scope: row 1, no search.
    for message in OUT_OF_SCOPE:
        p = Panel(base, graph)
        p.start()
        t = p.ask(message, expect_mode)
        good = t['status'] == 'faq_out_of_scope' and t['row'] == 1 and not t['searched']
        add('out of scope: ' + message, 'pass' if good else 'FAIL',
            'status %s, outcome %s, row %s, searched %s' % (t['status'], t['kind'], t['row'], t['searched']))

    # Confirm: accept shows the answer, reject counts as a miss.
    for accept in (True, False):
        found = None
        for message in CONFIRM_POOL:
            p = Panel(base, graph)
            p.start()
            t = p.ask(message, expect_mode)
            if t['status'] == 'faq_confirm':
                found = (p, t)
                break
        name = 'confirm %s' % ('accepted' if accept else 'rejected')
        if not found:
            add(name, 'inconclusive', 'no message in the pool produced a Confirm')
            continue
        code, data = found[0].react(found[1], accept)
        want = 'question' if accept else 'faq_none'
        add(name, 'pass' if data.get('status') == want else 'FAIL', 'status %s' % data.get('status'))
    return out


# ----------------------------------------------------------------------------------------------- table driver

def table_check(graph, progress=print):
    import xml.etree.ElementTree as ET
    import dcrai.dcr.dcr_repository as repo
    import dcrai.chat.outcome_runtime as ort
    creds = dict(api_key=os.getenv('API_KEY'), token=os.getenv('TOKEN'), root_url=os.getenv('ROOT_URL'),
                 graph_id=str(graph))
    if not all(creds.values()):
        raise SystemExit('API_KEY, TOKEN and ROOT_URL must be set in .env')

    def new_sim():
        state = dict(creds)
        graph_elem = repo.get_graph(state)
        if graph_elem is None:
            raise SystemExit('Graph %s not found' % graph)
        state['graph_xml'] = ET.tostring(graph_elem, encoding='unicode')
        state['simulation_id'] = repo.create_simulation(state)
        if not state['simulation_id']:
            raise SystemExit('Could not create a simulation')
        return state

    def one(state, case):
        scope, search, relevance, clarified = case
        row, outcome = oc.table(scope, search, relevance, clarified)
        res = dict(inputs=case, want='result %d:%s' % (row, outcome), got=None, readable=False, pending=None, ok=False)
        if not ort._exec(state, ort.TURN_START, ''):
            res['note'] = 'TurnStart could not be executed'
            return res
        for gate, value in zip(ort.GATES, (scope, search, relevance, str(clarified))):
            if not ort._exec(state, gate, value):
                res['note'] = '%s could not be executed' % gate
                return res
        fresh = repo.get_raw_events(state)
        ev = next((e for e in fresh.get('events', []) if e.get('id') == ort.RESULT), None)
        res['got'] = ev.get('value') if ev else None
        res['readable'] = ev is not None and ev.get('value') not in (None, '')
        if not res['readable']:
            tbl = next((e for e in fresh.get('events', []) if e.get('id') == ort.TABLE), None)
            res['got'] = 'result ' + str(tbl.get('value')) if tbl and tbl.get('value') else None
        parsed = ort.parse_result(res['got'])
        if ort._exec(state, ort.TURN_OUTCOME, outcome, 'eval_live'):
            pend = ort._pending_outcomes(repo.get_raw_events(state))
            res['pending'] = sorted(pend)
            for e in pend:       # acknowledge so the next turn starts clean
                ort.acknowledge(state, e)
            res['ok'] = parsed == (row, outcome) and pend == {oc.OUTCOME_EVENT[outcome]}
        else:
            res['note'] = 'TurnOutcome could not be executed'
        return res

    report = dict(isolated=[], sequential=[])
    probe = new_sim()
    events = {e.get('id') for e in repo.get_raw_events(probe).get('events', [])}
    need = {ort.TURN_START, ort.TABLE, ort.RESULT, ort.TURN_OUTCOME, *ort.GATES}
    report['missing_events'] = sorted(need - events)
    if report['missing_events']:
        return report
    progress('isolated: one simulation per input set')
    for case in TABLE_CASES:
        report['isolated'].append(one(new_sim(), case))
        progress('  %s %s' % (case, report['isolated'][-1]['ok']))
    progress('sequential: all input sets in one simulation (F4)')
    state = new_sim()
    for case in TABLE_CASES:
        report['sequential'].append(one(state, case))
        progress('  %s %s' % (case, report['sequential'][-1]['ok']))
    return report


# ----------------------------------------------------------------------------------------------- reports

def table_report(rep):
    lines = ['# Outcome table through the Portal', '']
    if rep['missing_events']:
        return '\n'.join(lines + ['The graph lacks events: %s. Import the graph built with --outcome dmn.'
                                  % ', '.join(rep['missing_events'])])
    f1 = all(r['readable'] for r in rep['isolated'])
    iso = sum(r['ok'] for r in rep['isolated'])
    seq = sum(r['ok'] for r in rep['sequential'])
    lines += ['| Check | Result |', '|---|---|',
              '| F1: the REST event list shows the result | %s |' % ('yes' if f1 else 'NO (dcr mode is blocked)'),
              '| Each input set in a fresh simulation | %d of %d correct |' % (iso, len(rep['isolated'])),
              '| All input sets in one simulation (F4) | %d of %d correct |' % (seq, len(rep['sequential'])), '',
              '| Run | Inputs | Want | Got | Pending after TurnOutcome | OK |', '|---|---|---|---|---|---|']
    for kind in ('isolated', 'sequential'):
        for r in rep[kind]:
            lines.append('| %s | %s | %s | %s | %s | %s |' % (kind, ', '.join(map(str, r['inputs'])), r['want'], r['got'],
                                                              r['pending'], 'ok' if r['ok'] else 'FAIL ' + r.get('note', '')))
    return '\n'.join(lines)


def panel_report(args, replay, mech):
    tally = Counter(r['verdict'] for r in replay)
    wrong = tally.get('WRONG', 0)
    viol = sorted(set(ALL_VIOLATIONS))
    summ = summarize([dict(kind=r['kind'], row=r['row'], source=r['source'], latency=r['latency'], mismatch=r['mismatch'])
                      for r in replay])
    fails = [m for m in mech if m['status'] == 'FAIL']
    verdicts = sorted(tally)
    lines = ['# Live outcome eval (Help panel)', '',
             'Graph %s, base %s, expected mode `%s`, %d runs.' % (args.graph, args.base, args.expect_mode, len(replay)), '',
             '## Gates', '', '| Gate | Result |', '|---|---|',
             '| WRONG answers | %d%s |' % (wrong, '' if wrong == 0 else ' (FAIL)'),
             '| Logged row differs from the table, DMN mismatch, mode not in effect | %d%s |' % (len(viol), '' if not viol else ' (FAIL)'),
             '| Mechanics scenarios failed | %d%s |' % (len(fails), '' if not fails else ' (FAIL)'), '',
             '## Verdicts', '', '| Verdict | Runs |', '|---|---|']
    lines += ['| %s | %d |' % (k, tally[k]) for k in verdicts]
    lines += ['', '## By group', '', '| Group | ' + ' | '.join(verdicts) + ' |', '|---|' + '---|' * len(verdicts)]
    by = defaultdict(Counter)
    for r in replay:
        by[r['group']][r['verdict']] += 1
    for g in sorted(by):
        lines.append('| %s | %s |' % (g, ' | '.join(str(by[g].get(k, 0)) for k in verdicts)))
    lines += ['', '## Outcome mix', '', '| Outcome | Row | Turns |', '|---|---|---|']
    lines += ['| %s | %s | %d |' % (k, row, n) for (k, row), n in sorted(summ['mix'].items(), key=lambda x: (x[0][0], str(x[0][1])))]
    lines += ['', 'Sources: %s. Mismatches: %d. Latency median %s s, p95 %s s.' % (
        dict(summ['sources']), summ['mismatches'], summ['median'], summ['p95'])]
    ctx = [r for r in replay if r.get('context') is not None]
    lines += ['', 'Two-turn cases whose first turn left the FAQ on screen (answered or clicked): %d of %d.' % (sum(1 for r in ctx if r['context']), len(ctx))]
    g_o = [r for r in replay if r['group'] == 'O']
    lines += ['', 'Group O turns ending in row 1: %d of %d.' % (sum(1 for r in g_o if r['row'] == 1), len(g_o))]
    wrongs = [r for r in replay if r['verdict'] == 'WRONG']
    if wrongs:
        lines += ['', '## WRONG runs', ''] + ['- %s r%d: answered %s, expected %s' % (r['id'], r['rep'] + 1, r['faq_ids'], r['expect']) for r in wrongs]
    if viol:
        lines += ['', '## Violations', ''] + ['- %s: %s' % (i, v) for i, v in viol[:40]]
    lines += ['', '## Mechanics', '', '| Scenario | Result | Detail |', '|---|---|---|']
    lines += ['| %s | %s | %s |' % (m['name'], m['status'], m['detail']) for m in mech]
    lines += ['', 'Not covered by this run: group V (needs a field on screen), the chat, and Danish input beyond the probe.']
    return '\n'.join(lines), wrong == 0 and not viol and not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('table')
    t.add_argument('--graph', required=True)
    p = sub.add_parser('panel')
    p.add_argument('--graph', required=True)
    p.add_argument('--base', default='http://127.0.0.1:8080')
    p.add_argument('--expect-mode', choices=('code', 'shadow', 'dcr'), default=os.getenv('OUTCOME_MODE', 'code'))
    p.add_argument('--repeat', type=int, default=1)
    p.add_argument('--cases', help='comma separated case ids')
    p.add_argument('--skip-mechanics', action='store_true')
    args = ap.parse_args(argv)
    if args.cmd == 'table':
        rep = table_check(args.graph)
        text = table_report(rep)
        out = HERE / 'reports' / 'live_table_report.md'
        out.parent.mkdir(exist_ok=True)
        out.write_text(text + '\n', encoding='utf-8')
        print('\n' + text + '\n\nWritten to', out)
        bad = bool(rep['missing_events']) or not all(r['ok'] for r in rep['isolated'] + rep['sequential'])
        return 1 if bad else 0
    ALL_VIOLATIONS.clear()
    replay = replay_cases(args.base, args.graph, args.repeat, args.expect_mode,
                          set(args.cases.split(',')) if args.cases else None)
    mech = [] if args.skip_mechanics else scenarios(args.base, args.graph, args.expect_mode)
    text, passed = panel_report(args, replay, mech)
    REPORT.parent.mkdir(exist_ok=True)
    RESULTS.parent.mkdir(exist_ok=True)
    REPORT.write_text(text + '\n', encoding='utf-8')
    RESULTS.write_text(json.dumps(dict(args=vars(args), replay=replay, mechanics=mech), indent=1, default=str),
                       encoding='utf-8')
    print('\n' + text + '\n\nWritten to', REPORT, 'and', RESULTS)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
