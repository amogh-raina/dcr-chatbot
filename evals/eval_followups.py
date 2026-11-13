"""Help panel follow-up eval: runs the real application_runtime.ask on seeded panel state, without DCR.

    python -m evals.eval_followups                           # all cases, report to evals/reports/followup_report.md
    python -m evals.eval_followups --cases n01,f01,s01  # a few cases, printed in detail
    python -m evals.eval_followups --repeat 3           # each case 3 times (the LLM steps are not deterministic)
    python -m evals.eval_followups --regrade evals/runs/followup_results.json --report evals/reports/X.md
                                                        # grade a stored results file again with the current case
                                                        # labels; calls no model and needs no retriever

Needs the embedding model (like calibrate_thresholds.py), OPENAI_API_KEY and DECISIONS_ENABLED=1 in .env (the
classifier, rewrite and relevance steps only run with Decisions on). Thresholds come from .env as in the app:
FAQ_SINGLE/MIN/MARGIN_THRESHOLD, DECISIONS_CONTEXT_MIN, DECISIONS_RELEVANT_MIN, DECISIONS_DISTRESS_MIN.

How it works. Cases are in evals/cases/eval_followup_queries.json. For each case the panel state is seeded the
way the app keeps it: the field on screen (label and help text from the Clean graph, HelpFAQ links), the previous
panel question (help_last_message) and the FAQ shown for it (help_last_faq). Then application_runtime.ask runs
unchanged, with only the DCR calls replaced: the search goes to the local retriever with the same decision rule as
the FAQ API (faq_search.api.decide, top-3 options) and then through the real relevance check. So the classifier,
the rewrite, the search order, the relevance check and the "same FAQ" rule are exactly what the app runs.

What is recorded per case: the contextual and distress probabilities, the rewrite, every search (query, API
decision, candidates, relevance probabilities), the outcome (answered / options / same_faq / no_match), latency.
The report has the scores, threshold sweeps for DECISIONS_CONTEXT_MIN and DECISIONS_RELEVANT_MIN, and a line per
case. The JSON file next to it (followup_results.json) has everything, including the rewrites to read by hand.

Scoring (expect in the case file):
  answer [ids]         correct = one of them answered; partial = shown among options; WRONG = another FAQ answered;
                       missed = nothing shown
  no_answer            correct = no match or "the answer above is the closest"; shown_options = options offered
                       (not an answer, but not a clean refusal either); WRONG = an FAQ answered
  same_or_answer [ids] correct = pointed back to the FAQ just shown, or one of the ids answered
A Confirm ("Is this what you are asking?") is graded apart from options: confirm_right (the one candidate is an
expected id), confirm_wrong (another FAQ, in an answer or same_or_answer case), confirm_unneeded (a no_answer case).
A Confirm shows no answer, so it is never WRONG. A related offer is graded like options.
"""
import argparse
import json
import os
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from dcrai import prompts, registry  # noqa: E402 - needs the repo root on the path
CASES = HERE / 'cases' / 'eval_followup_queries.json'
GRAPH = ROOT / 'xml graphs' / 'SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml'
FLAGS = {'CONFIRM_LONE_SURVIVOR': '1', 'RELEVANCE_TIERS': '1', 'PANEL_FALLBACK_REWRITE': '0'}


def graph_fields(graph=GRAPH):
    """{event id: {label, html, related ids}} from the Clean graph, as the app's help card reads them."""
    root = ET.parse(graph).getroot()
    labels = {m.get('eventId'): m.get('labelId') for m in root.iter('labelMapping')}
    out = {}
    for e in root.iter('event'):
        eid = e.get('id')
        desc = e.find('custom/eventDescription')
        groups = [g.text or '' for g in e.findall('custom/groups/group')]
        out[eid] = dict(label=labels.get(eid, eid), html=(desc.text or '') if desc is not None else '',
                        related=[g.split(':', 1)[1] for g in groups if g.startswith('HelpFAQ:')])
    return out


def load_records():
    raw = json.loads((ROOT / 'faq_search' / 'data' / 'faq_qa_records.json').read_text())
    records = raw if isinstance(raw, list) else raw.get('records', raw)
    return {r['id']: r for r in records}


class Trace:
    """What one ask() did, collected through thin wrappers around the LLM and search calls."""
    def __init__(self):
        self.signals = None
        self.rewrite = None
        self.searches = []
        self._candidates = []


def install(retriever, settings, records):
    """Replace DCR (and only DCR) around application_runtime.ask. Returns a function that runs one case."""
    import dcrai.application.application_runtime as app
    import dcrai.llm.retrieval_llm as llm
    import dcrai.chat.retrieval_runtime as rr
    from faq_search.api import decide

    current = {'trace': None}

    app.fetch = lambda state: {'events': []}
    rr.is_retrieval = lambda payload: True
    rr.event = lambda payload, eid: {'enabled': True} if eid in (rr.TRIAGE, rr.INPUT, 'Help_UserQuestion') else None
    rr.execute = lambda *a, **k: True
    app.repo.execute_raw_event = lambda *a, **k: True
    app.application_marking = lambda payload: 'unchanged'
    app._unchanged = lambda state, before: {'events': []}
    app.view = lambda state, payload: {'application': True, 'status': 'question'}
    app.escalate = lambda *a, **k: None
    app.ilog.record = lambda *a, **k: None

    def search(state, query, comment='', judge=None):
        results = retriever.retrieve(query, top_k=max(settings.maximum, 2))
        decision = decide(results, settings)
        chosen = results[:1] if decision == 'single_match' else \
            results[:settings.maximum] if decision == 'clarify_match' else []
        found = [dict(id=r.id, question=r.canonical_question, answer=r.answer_text, citation=r.citation)
                 for r in chosen]
        entry = dict(query=query, judge=judge or query, decision=decision,
                     scores=[(r.id, round(float(r.score), 3)) for r in results[:3]],
                     candidates=[c['id'] for c in found], relevance={}, kept=[], tiers={})
        current['trace'].searches.append(entry)
        # What rr.search records for its callers: the search's own decision and what was retrieved.
        state['last_search'] = dict(decision=decision, retrieved=[c['id'] for c in found])
        if found:
            current['trace']._candidates = [c['id'] for c in found]
            found = rr.check_relevance(judge or query, found)     # the same code the app runs: tiers, fail closed
            entry['kept'] = [c['id'] for c in found]
            entry['tiers'] = {c['id']: c['tier'] for c in found}
        if not found:
            return 'no_match', [], 'I could not find an answer to that in the handicaptillæg FAQ.'
        return 'found', found, ''
    rr.search = search

    original_decide = llm._decide

    def recorded_decide(evidence, questions, http=None):
        found = original_decide(evidence, questions, http)
        names = [q['name'] for q in questions]
        trace = current['trace']
        if names and names[0].startswith('fits_') and trace.searches:
            ids = trace._candidates
            trace.searches[-1]['relevance'] = {ids[int(n[5:])]: round(float(found[n].get('probability') or 0), 3)
                                               for n in names if int(n[5:]) < len(ids)}
        elif names and names[0].startswith('answers_') and trace.searches:
            # Tiered check: {'answers': {id: p("answers it")}, 'topic': {id: p("same topic")}}
            ids = trace._candidates
            rel = {'answers': {}, 'topic': {}}
            for n in names:
                kind, _, index = n.partition('_')
                if kind in ('answers', 'topic') and index.isdigit() and int(index) < len(ids):
                    rel[kind][ids[int(index)]] = round(float(found[n].get('probability') or 0), 3)
            trace.searches[-1]['relevance'] = rel
        elif 'contextual' in names:
            trace.signals = {n: round(float(found[n].get('probability') or 0), 3) for n in names}
        return found
    llm._decide = recorded_decide

    original_rewrite = llm.rewrite

    def recorded_rewrite(*a, **k):
        text = original_rewrite(*a, **k)
        current['trace'].rewrite = text
        return text
    llm.rewrite = recorded_rewrite

    fields = graph_fields()
    titles = rr.faq_titles()

    def run(case):
        info = fields[case['field']]
        field = dict(id=case['field'], label=info['label'], type='choice',
                     help=dict(html=info['html'], related=[dict(id=i, question=titles[i]) for i in info['related']
                                                           if i in titles]))
        state = {'application_prompt': {'field': field}}
        if case.get('previous'):
            state['help_last_message'] = case['previous']
        if case.get('previous_faq'):
            r = records[case['previous_faq']]
            state['help_last_faq'] = dict(id=r['id'], question=r['canonical_question'],
                                          answer_start=' '.join(r['answer_text'].split())[:300])
        current['trace'] = Trace()
        started = time.monotonic()
        try:
            result = app.ask(state, {'message': case['message'], 'scope': 'field'})
            error = None
        except Exception as exc:  # noqa: BLE001 - reported per case
            result, error = {}, f'{type(exc).__name__}: {exc}'
        trace = current['trace']
        return dict(result=result, error=error, latency=round(time.monotonic() - started, 2), signals=trace.signals,
                    rewrite=trace.rewrite, searches=trace.searches, searched_for=result.get('searched_for'))
    return run


def outcome(run):
    r = run['result']
    if run['error']:
        return 'error', []
    if r.get('answered'):
        return 'answered', [r.get('faq_id')]
    if r.get('same_faq'):
        return 'same_faq', []
    if r.get('status') == 'faq_confirm':
        return 'confirm', [c['candidate_key'] for c in r.get('candidates', [])]
    if r.get('status') == 'faq_related':
        return 'related', [c['candidate_key'] for c in r.get('candidates', [])]
    if r.get('status') == 'faq_clarify':
        return 'options', [c['candidate_key'] for c in r.get('candidates', [])]
    if r.get('status') == 'faq_unavailable':
        return 'unavailable', []
    return 'no_match', []


def grade(case, kind, ids):
    expect = case['expect']
    if kind in ('error', 'unavailable'):
        return kind
    if 'answer' in expect:
        good = set(expect['answer'])
        if kind == 'answered':
            return 'correct' if ids[0] in good else 'WRONG'
        if kind == 'confirm':
            return 'confirm_right' if good & set(ids) else 'confirm_wrong'
        if kind in ('options', 'related'):
            return 'partial' if good & set(ids) else 'options_wrong'
        return 'missed'
    if 'same_or_answer' in expect:
        good = set(expect['same_or_answer'])
        if kind == 'same_faq' or (kind == 'answered' and ids[0] in good):
            return 'correct'
        if kind == 'answered':
            return 'WRONG'
        if kind == 'confirm':
            return 'confirm_right' if good & set(ids) else 'confirm_wrong'
        return 'partial' if kind in ('options', 'related') and good & set(ids) else 'missed'
    if kind == 'answered':
        return 'WRONG'
    if kind == 'confirm':
        return 'confirm_unneeded'
    return 'shown_options' if kind in ('options', 'related') else 'correct'


def sweep_context(rows, threshold):
    """Contextual detection at several thresholds, on cases labelled followup true/false."""
    lines = ['| DECISIONS_CONTEXT_MIN | follow-ups caught | self-contained left alone | accuracy |', '|---|---|---|---|']
    labelled = [(r['case']['followup'], (r['run']['signals'] or {}).get('contextual')) for r in rows
                if r['case']['followup'] is not None and r['run']['signals']]
    for t in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        pos = [p for y, p in labelled if y]
        neg = [p for y, p in labelled if not y]
        tp = sum(p >= t for p in pos)
        tn = sum(p < t for p in neg)
        mark = ' (current)' if abs(t - float(os.getenv('DECISIONS_CONTEXT_MIN', '0.7'))) < 1e-9 else ''
        lines.append(f'| {t:.1f}{mark} | {tp}/{len(pos)} | {tn}/{len(neg)} | '
                     f'{(tp + tn) / max(1, len(labelled)):.2f} |')
    return lines


def answer_probabilities(search):
    """{FAQ id: probability} the relevance check gave a search: the 'answers' probabilities of the tiered check, or
    the single probability of the old check (files written before 2026-10-10 hold the old shape)."""
    rel = search.get('relevance') or {}
    return rel.get('answers') or {} if isinstance(rel.get('answers'), dict) else rel


def sweep_relevance(rows, threshold):
    """Relevance check at several thresholds, over every candidate it scored (the 'answers it' probability). A
    candidate counts as positive when it is in the case's expected ids (answer / same_or_answer); everything else,
    and every candidate of a no_answer case, is negative. Other FAQs that would also be acceptable count as negative,
    so precision is a lower bound."""
    pairs = []
    for r in rows:
        good = set(r['case']['expect'].get('answer') or r['case']['expect'].get('same_or_answer') or [])
        for s in r['run']['searches']:
            for fid, p in answer_probabilities(s).items():
                pairs.append((fid in good, p))
    lines = ['| DECISIONS_ANSWERS_MIN (old runs: DECISIONS_RELEVANT_MIN) | expected FAQs kept | other FAQs kept | precision |',
             '|---|---|---|---|']
    for t in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        tp = sum(1 for y, p in pairs if y and p >= t)
        fp = sum(1 for y, p in pairs if not y and p >= t)
        pos = sum(1 for y, _ in pairs if y)
        mark = ' (current)' if abs(t - float(os.getenv('DECISIONS_ANSWERS_MIN', '0.5'))) < 1e-9 else ''
        lines.append(f'| {t:.1f}{mark} | {tp}/{pos} | {fp} | {tp / max(1, tp + fp):.2f} |')
    return lines


def metrics_lines(rows):
    """The numbers the phase 1 gate reads (spec 01, 5.5)."""
    v = Counter(r['verdict'] for r in rows)
    kinds = Counter(r['kind'] for r in rows)
    answered_right = sum(1 for r in rows if r['kind'] == 'answered' and r['verdict'] == 'correct')
    latencies = [r['run']['latency'] for r in rows] or [0]
    return ['| metric | runs |', '|---|---|',
            f"| WRONG (an FAQ answered that is not expected) | {v['WRONG']} |",
            f'| answered and correct | {answered_right} |',
            f"| correct, all kinds (answered, right refusal, same FAQ) | {v['correct']} |",
            f"| confirm_right | {v['confirm_right']} |",
            f"| confirm_wrong | {v['confirm_wrong']} |",
            f"| confirm_unneeded | {v['confirm_unneeded']} |",
            f"| related offers | {kinds['related']} |",
            f"| options | {kinds['options']} |",
            f"| missed | {v['missed']} |",
            f'| latency median / max (s) | {statistics.median(latencies):.1f} / {max(latencies):.1f} |']


def regrade(path, cases):
    """Rows from a stored results file, graded again with the current case labels. Calls no model."""
    by_id = {c['id']: c for c in cases}
    rows = []
    for item in json.loads(Path(path).read_text()):
        run = {k: v for k, v in item.items() if k not in ('id', 'repeat', 'verdict', 'outcome', 'ids', 'response')}
        run['result'] = {'response': item.get('response')}
        case, kind, ids = by_id[item['id']], item['outcome'], item['ids']
        rows.append(dict(case=case, run=run, kind=kind, ids=ids, verdict=grade(case, kind, ids), repeat=item['repeat']))
    return rows


def report_lines(rows, intro, sweeps=True):
    """The markdown report. `intro` is the header paragraph(s); the sweeps need live probabilities from a run."""
    verdicts = Counter(r['verdict'] for r in rows)
    by_group = defaultdict(Counter)
    for r in rows:
        by_group[r['case']['group']][r['verdict']] += 1
    wrong = [r for r in rows if r['verdict'] == 'WRONG']
    lines = ['# Help panel follow-up eval', ''] + intro + ['', '## Metrics', ''] + metrics_lines(rows)
    lines += ['', '## Verdicts', '', '| verdict | runs |', '|---|---|']
    lines += [f'| {v} | {n} |' for v, n in verdicts.most_common()]
    lines += ['', '**WRONG = an FAQ was answered that does not answer the question. This is the number to drive to '
                  'zero.**', '', '## By group', '', '| group | ' + ' | '.join(sorted(verdicts)) + ' |',
              '|---|' + '---|' * len(verdicts)]
    for g in sorted(by_group):
        lines.append(f'| {g} | ' + ' | '.join(str(by_group[g][v]) for v in sorted(verdicts)) + ' |')
    if sweeps:
        lines += ['', '## Contextual classifier (DECISIONS_CONTEXT_MIN)', ''] + sweep_context(rows, None)
        lines += ['', '## Relevance check, "answers it" probability', ''] + sweep_relevance(rows, None)
    lines += ['', '## Cases', '', '| case | verdict | outcome | ctx | understood as | searches (query: kept) |',
              '|---|---|---|---|---|---|']
    for r in rows:
        searches = '; '.join(f"{s['query'][:50]}: {','.join(s['kept']) or '-'}" for s in r['run']['searches'])
        ctx = (r['run']['signals'] or {}).get('contextual')
        lines.append(f"| {r['case']['id']} | {r['verdict']} | {r['kind']} {','.join(r['ids'])} | "
                     f"{ctx if ctx is not None else '-'} | {(r['run']['searched_for'] or '-').replace('|', '/')} | "
                     f"{searches.replace('|', '/')} |")
    if wrong:
        lines += ['', '## Wrong answers', '']
        lines += [f"- {r['case']['id']}: \"{r['case']['message']}\" answered with {r['ids'][0]}; expected "
                  f"{r['case']['expect']}" for r in wrong]
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cases', help='comma-separated case ids (default: all)')
    parser.add_argument('--repeat', type=int, default=1, help='runs per case (LLM steps vary between runs)')
    parser.add_argument('--report', default=str(HERE / 'reports' / 'followup_report.md'))
    parser.add_argument('--json', default=str(HERE / 'runs' / 'followup_results.json'))
    parser.add_argument('--regrade', metavar='PATH', help='grade a stored results JSON again with the current case '
                        'labels and write the report; calls no model, needs no retriever, writes no JSON')
    args = parser.parse_args()
    if args.regrade:
        cases = json.loads(CASES.read_text())['queries']
        rows = regrade(args.regrade, cases)
        intro = [f"{len(rows)} runs regraded from `{args.regrade}` with the labels in `{CASES.name}`. No model was "
                 'called. The prompts, flags and thresholds of the original run are not stored in that file, so they '
                 'are not shown here.']
        Path(args.report).write_text('\n'.join(report_lines(rows, intro, sweeps=False)) + '\n')
        print(f"{dict(Counter(r['verdict'] for r in rows))}\nreport: {args.report}")
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
    except ImportError:
        pass
    import logging
    logging.basicConfig(level=logging.WARNING)
    if os.getenv('DECISIONS_ENABLED') != '1':
        print('WARNING: DECISIONS_ENABLED is not 1: no classifier, no rewrite, Responses relevance check. '
              'This is not what the app runs with Decisions on.')
    from faq_search.retriever import get_retriever
    from dcrai.llm.openchat import Settings
    settings = Settings.from_env()
    run_case = install(get_retriever(), settings, load_records())
    cases = json.loads(CASES.read_text())['queries']
    if args.cases:
        wanted = set(args.cases.split(','))
        cases = [c for c in cases if c['id'] in wanted]

    rows = []
    for case in cases:
        for n in range(args.repeat):
            run = run_case(case)
            kind, ids = outcome(run)
            verdict = grade(case, kind, ids)
            rows.append(dict(case=case, run=run, kind=kind, ids=ids, verdict=verdict, repeat=n))
            ctx = (run['signals'] or {}).get('contextual')
            print(f"{case['id']:4} {verdict:13} {kind:9} {','.join(ids):18} ctx={ctx if ctx is not None else '-':<5} "
                  f"{run['latency']:5.1f}s  understood as: {run['searched_for'] or '-'}")
            if args.cases:
                for s in run['searches']:
                    print(f"       search[{s['query'][:70]}] {s['decision']} {s['scores']} relevance={s['relevance']} "
                          f"kept={s['kept']}")

    verdicts = Counter(r['verdict'] for r in rows)
    latencies = [r['run']['latency'] for r in rows]
    flags = ', '.join(f'{k}={os.getenv(k, d)}' for k, d in FLAGS.items())
    intro = [f"{len(rows)} runs ({len(cases)} cases x {args.repeat}). DECISIONS_ENABLED="
             f"{os.getenv('DECISIONS_ENABLED')}, context min {os.getenv('DECISIONS_CONTEXT_MIN', '0.7')}, relevance "
             f"min {os.getenv('DECISIONS_RELEVANT_MIN', '0.5')}, search single/min/margin {settings.single}/"
             f"{settings.minimum}/{settings.margin}. Latency median {statistics.median(latencies):.1f}s, max "
             f"{max(latencies):.1f}s.", '',
             f"registry.version() {registry.version()}, prompts.version() {prompts.version()}. Flags: {flags}. DECISIONS_ANSWERS_MIN "
             f"{os.getenv('DECISIONS_ANSWERS_MIN', '0.5')}, DECISIONS_TOPIC_MIN {os.getenv('DECISIONS_TOPIC_MIN', '0.5')}."]
    lines = report_lines(rows, intro)
    Path(args.report).write_text('\n'.join(lines) + '\n')
    Path(args.json).write_text(json.dumps([dict(id=r['case']['id'], repeat=r['repeat'], verdict=r['verdict'],
                                                outcome=r['kind'], ids=r['ids'], **{k: v for k, v in r['run'].items()
                                                                                   if k != 'result'},
                                                response=r['run']['result'].get('response'))
                                           for r in rows], indent=1, ensure_ascii=False))
    print(f"\n{dict(verdicts)}\nreport: {args.report}\ndetails: {args.json}")


if __name__ == '__main__':
    main()
