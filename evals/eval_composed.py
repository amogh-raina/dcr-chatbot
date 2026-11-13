"""Help-panel searches about the field on screen: typed words vs composed query vs what the app does.

    python -m evals.eval_composed [--report evals/reports/composed_report.md]

Needs the embedding model (sentence-transformers), like calibrate_thresholds.py. Uses the thresholds the API uses
(FAQ_SINGLE_THRESHOLD, FAQ_MIN_THRESHOLD, FAQ_MARGIN_THRESHOLD, else defaults).

Three columns per case:
  typed     the message as typed
  composed  '<field label> <message>'
  app       what application_runtime.ask does for scope='field': the typed search; if none of the field's linked
            FAQs (HelpFAQ tags in the graph) is shown, the composed search instead

hit = a shown suggestion is expected; top1 = the first shown suggestion is expected; single_wrong = a single match
that is not expected (one confident wrong answer); none = nothing shown.
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
CASES = HERE / "cases"
GRAPH = ROOT / "xml graphs" / "SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"
SIDES = ("typed", "composed", "app")


def field_labels(graph=GRAPH):
    root = ET.parse(graph).getroot()
    return {m.get("eventId"): m.get("labelId") for m in root.iter("labelMapping")}


def field_links(graph=GRAPH):
    """HelpFAQ ids per event, as the host reads them from the event's tags."""
    root = ET.parse(graph).getroot()
    out = {}
    for e in root.iter("event"):
        groups = [g.text or "" for g in e.findall("custom/groups/group")]
        if groups:
            out[e.get("id")] = [g.split(":", 1)[1] for g in groups if g.startswith("HelpFAQ:")]
    return out


def compose(case, labels):
    return f"{labels[case['target']]} {case['message']}"


def shown(ranked, settings, decide):
    """What the applicant sees for one search: (decision, [ids shown])."""
    decision = decide([s for _, s in ranked], settings.single, settings.minimum, settings.margin)
    ids = [ranked[0][0]] if decision == "single_match" else \
        [rid for rid, _ in ranked[:settings.maximum]] if decision == "clarify_match" else []
    return decision, ids


def score(decision, ids, expected):
    hit = bool(set(ids) & set(expected))
    top1 = bool(ids) and ids[0] in expected
    return dict(hit=hit, top1=top1, single_wrong=decision == "single_match" and not top1, none=not ids)


def run_case(case, retrieve, labels, links, settings, decide):
    typed_ranked = retrieve(case["message"])
    comp_ranked = retrieve(compose(case, labels))
    typed, comp = shown(typed_ranked, settings, decide), shown(comp_ranked, settings, decide)
    linked = set(links.get(case["target"], []))
    use_typed = bool(set(typed[1]) & linked)
    app = (typed, typed_ranked) if use_typed else (comp, comp_ranked)
    return dict(typed=(typed, typed_ranked), composed=(comp, comp_ranked), app=app,
                note="" if use_typed else "composed")


def cell(result, expected):
    (decision, ids), ranked = result
    s = score(decision, ids, expected)
    top = f"{ranked[0][1]:.3f}" if ranked else "-"
    return f"{decision.replace('_match', '')} {','.join(ids)} ({top})", s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path)
    args = ap.parse_args(argv)
    from evals.calibrate_thresholds import current_settings, decide
    from faq_search.retriever import get_retriever
    cases = [c for c in json.loads((CASES / "eval_composed_queries.json").read_text(encoding="utf-8"))["queries"]
             if c["scope"] == "field"]
    labels, links, settings, retriever = field_labels(), field_links(), current_settings(), get_retriever()

    def retrieve(query):
        return [[r.id, float(r.score)] for r in retriever.retrieve(query, top_k=5)]

    keys = ("hit", "top1", "single_wrong", "none")
    totals = {side: dict.fromkeys(keys, 0) for side in SIDES}
    rows, composed_used = [], 0
    yn = lambda b: "yes" if b else "no"
    for c in cases:
        r = run_case(c, retrieve, labels, links, settings, decide)
        composed_used += r["note"] == "composed"
        line = [c["id"], c["target"], c["message"]]
        for side in SIDES:
            text, s = cell(r[side], c["expected"])
            for k in keys:
                totals[side][k] += s[k]
            line += [text + (" [composed]" if side == "app" and r["note"] else ""), yn(s["hit"]), yn(s["top1"])]
        rows.append(line)
    n = len(cases)
    out = ["# Help-panel field questions: typed vs composed vs app", "",
           f"Thresholds: single {settings.single}, min {settings.minimum}, margin {settings.margin}. {n} cases; "
           f"the app used the composed search in {composed_used}.", "",
           "| side | hit | top1 | single_wrong | none |", "|---|---|---|---|---|"]
    for side in SIDES:
        t = totals[side]
        out.append(f"| {side} | {t['hit']}/{n} | {t['top1']}/{n} | {t['single_wrong']} | {t['none']} |")
    out += ["", "| id | target | message | typed | hit | top1 | composed | hit | top1 | app | hit | top1 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    text = "\n".join(out)
    print(text)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
