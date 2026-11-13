#!/usr/bin/env python3
"""
calibrate_thresholds.py -- measure retrieval quality on labelled queries and pick the
single / minimum / margin thresholds from data instead of guessing.

Input: evals/cases/eval_queries.json. Every query has a category:
  in_scope      the KB answers it; `expected` lists the acceptable record ids
  unanswerable  on topic (SU, handicaptillæg) but not covered by the KB; should end as no_match
  off_topic     unrelated to SU; should end as no_match

Each query is scored once with the real retriever and the top-5 (id, score) pairs are cached in
evals/runs/eval_scores.json. The threshold sweep then runs on the cache, so it takes
seconds and does not need the model. Re-score only when the records, the embeddings, the model
or the query file change.

How a query ends up, using the same rule as the API (faq_search.api.decide):
  single_match   top >= single and (top - runner-up) >= margin
  clarify_match  top >= minimum (up to `maximum` options are offered)
  no_match       otherwise

Outcomes counted:
  in_scope:  single_correct | single_wrong | clarify_hit | clarify_miss | rejected
  out of scope (unanswerable + off_topic): rejected (good) | false_clarify | false_single

single_wrong and false_single are the costly errors: the bot states a wrong answer with
confidence. The recommendation maximises useful answers (single_correct counts 1, clarify_hit
counts 0.5) subject to caps on those two error rates, then takes the middle of the tied region
so the choice does not sit on a knife edge.

Usage (repo root, dcr env):
    python -m evals.calibrate_thresholds                      # score + sweep + report
    python -m evals.calibrate_thresholds --from-scores        # sweep only, no model
    python -m evals.calibrate_thresholds --report evals/reports/calibration_report.md
    python -m evals.calibrate_thresholds --max-wrong-single 0.0 --max-oos-single 0.0

Query prompt: the retriever can prepend a prompt to the user query only (FAQ_QUERY_PROMPT). To try it:
    python -m evals.calibrate_thresholds --query-prompt query     # Qwen3's built-in "query" prompt
    python -m evals.calibrate_thresholds --ab                     # no prompt vs "query", side by side
Each prompt setting gets its own score cache and needs its own thresholds. The recommended values
printed for a prompt only apply when the app runs with the same FAQ_QUERY_PROMPT.

Caveat: ~100 queries is a small sample. One query is about 1 point of a rate. Treat the result as
a defensible starting point, add real user queries to eval_queries.json, and re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
DEFAULT_QUERIES = HERE / "cases" / "eval_queries.json"
DEFAULT_SCORES = HERE / "runs" / "eval_scores.json"
TOP_K = 5
IN_SCOPE = "in_scope"
OUT_OF_SCOPE = ("unanswerable", "off_topic")


def load_queries(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    queries = data["queries"]
    for q in queries:
        if q["category"] not in (IN_SCOPE, *OUT_OF_SCOPE):
            raise ValueError(f"{q['id']}: unknown category {q['category']!r}")
        if q["category"] == IN_SCOPE and not q["expected"]:
            raise ValueError(f"{q['id']}: in_scope query without expected ids")
    return queries


def file_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def score_queries(queries: list[dict], retriever) -> dict:
    """Runs every query through the retriever and keeps the top-K (id, score) pairs."""
    scored = {}
    for q in queries:
        results = retriever.retrieve(q["query"], top_k=TOP_K)
        scored[q["id"]] = [[r.id, round(float(r.score), 5)] for r in results]
    return scored


def decide(top_scores: list[float], single: float, minimum: float, margin: float) -> str:
    """Same rule as faq_search.api.decide, on a plain list of descending scores."""
    if not top_scores:
        return "no_match"
    top = top_scores[0]
    second = top_scores[1] if len(top_scores) > 1 else 0.0
    if top >= single and (top - second) >= margin:
        return "single_match"
    if top >= minimum:
        return "clarify_match"
    return "no_match"


def classify(query: dict, ranked: list, single: float, minimum: float, margin: float,
             maximum: int = 3) -> str:
    """Outcome label for one query at one threshold setting. `ranked` is [[id, score], ...]."""
    decision = decide([s for _, s in ranked], single, minimum, margin)
    if query["category"] == IN_SCOPE:
        expected = set(query["expected"])
        if decision == "single_match":
            return "single_correct" if ranked[0][0] in expected else "single_wrong"
        if decision == "clarify_match":
            offered = {rid for rid, _ in ranked[:maximum]}
            return "clarify_hit" if offered & expected else "clarify_miss"
        return "rejected"
    return {"no_match": "rejected", "clarify_match": "false_clarify", "single_match": "false_single"}[decision]


def evaluate(queries: list[dict], scores: dict, single: float, minimum: float, margin: float,
             maximum: int = 3) -> dict:
    """Rates for one threshold setting. Rates are fractions of the relevant query group."""
    in_scope = [q for q in queries if q["category"] == IN_SCOPE]
    oos = [q for q in queries if q["category"] in OUT_OF_SCOPE]
    counts: dict[str, int] = {}
    for q in queries:
        label = classify(q, scores[q["id"]], single, minimum, margin, maximum)
        key = label if q["category"] == IN_SCOPE else f"oos_{label}"
        counts[key] = counts.get(key, 0) + 1

    def rate(key: str, group: list) -> float:
        return counts.get(key, 0) / len(group) if group else 0.0

    single_correct = rate("single_correct", in_scope)
    clarify_hit = rate("clarify_hit", in_scope)
    return {
        "single": single, "minimum": minimum, "margin": margin,
        "single_correct": single_correct,
        "single_wrong": rate("single_wrong", in_scope),
        "clarify_hit": clarify_hit,
        "clarify_miss": rate("clarify_miss", in_scope),
        "rejected": rate("rejected", in_scope),
        "oos_rejected": rate("oos_rejected", oos),
        "oos_false_clarify": rate("oos_false_clarify", oos),
        "oos_false_single": rate("oos_false_single", oos),
        "useful": single_correct + 0.5 * clarify_hit,
    }


def summary_metrics(queries: list[dict], scores: dict) -> dict:
    """Threshold-free quality numbers, used to compare embedding set-ups such as prompt vs no prompt."""
    in_scope = [q for q in queries if q["category"] == IN_SCOPE]
    oos = [q for q in queries if q["category"] != IN_SCOPE]
    top1 = sum(bool(scores[q["id"]]) and scores[q["id"]][0][0] in q["expected"] for q in in_scope)
    top3 = sum(bool({rid for rid, _ in scores[q["id"]][:3]} & set(q["expected"])) for q in in_scope)
    in_tops = [scores[q["id"]][0][1] for q in in_scope if scores[q["id"]]]
    oos_tops = [scores[q["id"]][0][1] for q in oos if scores[q["id"]]]
    in_p10 = percentile(in_tops, 0.10)
    oos_p90 = percentile(oos_tops, 0.90)
    return {
        "top1_accuracy": top1 / len(in_scope) if in_scope else 0.0,
        "top3_recall": top3 / len(in_scope) if in_scope else 0.0,
        "in_scope_top_p10": in_p10,
        "oos_top_p90": oos_p90,
        "separation": in_p10 - oos_p90,  # > 0: a score threshold can split the two groups
    }


def scores_path_for(base: Path, query_prompt: str) -> Path:
    """eval_scores.json for no prompt, eval_scores_<prompt>.json otherwise."""
    if not query_prompt:
        return base
    tag = "".join(c if c.isalnum() else "_" for c in query_prompt)[:24].strip("_") or "prompt"
    return base.with_name(f"{base.stem}_{tag}{base.suffix}")


def frange(start: float, stop: float, step: float) -> list[float]:
    n = int(round((stop - start) / step))
    return [round(start + i * step, 4) for i in range(n + 1)]


def sweep(queries: list[dict], scores: dict, step: float = 0.02, maximum: int = 3) -> list[dict]:
    rows = []
    for single in frange(0.60, 0.96, step):
        for minimum in frange(0.30, 0.80, step):
            if minimum > single:
                continue
            for margin in frange(0.0, 0.20, step):
                rows.append(evaluate(queries, scores, single, minimum, margin, maximum))
    return rows


def recommend(rows: list[dict], max_wrong_single: float, max_oos_single: float,
              max_oos_accept: float | None = None) -> dict | None:
    """Best setting under the error caps, taking the centre of the tied region."""
    feasible = [r for r in rows
                if r["single_wrong"] <= max_wrong_single + 1e-9
                and r["oos_false_single"] <= max_oos_single + 1e-9
                and (max_oos_accept is None
                     or r["oos_false_single"] + r["oos_false_clarify"] <= max_oos_accept + 1e-9)]
    if not feasible:
        return None
    best = max(r["useful"] for r in feasible)
    tied = [r for r in feasible if r["useful"] >= best - 1e-9]
    centre = {k: statistics.median(r[k] for r in tied) for k in ("single", "minimum", "margin")}
    return min(tied, key=lambda r: sum((r[k] - centre[k]) ** 2 for k in centre))


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    idx = (len(ordered) - 1) * p
    lo, hi = int(idx), min(int(idx) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


def score_distribution(queries: list[dict], scores: dict) -> list[tuple[str, list[float]]]:
    """Top-1 and margin groups used to eyeball where the thresholds should sit."""
    groups: dict[str, list[float]] = {"in_scope, top-1 correct": [], "in_scope, top-1 wrong": [],
                                      "unanswerable": [], "off_topic": []}
    margins_correct: list[float] = []
    margins_wrong: list[float] = []
    for q in queries:
        ranked = scores[q["id"]]
        top = ranked[0][1] if ranked else 0.0
        gap = top - (ranked[1][1] if len(ranked) > 1 else 0.0)
        if q["category"] == IN_SCOPE:
            ok = ranked and ranked[0][0] in q["expected"]
            groups["in_scope, top-1 correct" if ok else "in_scope, top-1 wrong"].append(top)
            (margins_correct if ok else margins_wrong).append(gap)
        else:
            groups[q["category"]].append(top)
    out = list(groups.items())
    out.append(("margin (top1 - top2), top-1 correct", margins_correct))
    out.append(("margin (top1 - top2), top-1 wrong", margins_wrong))
    return out


def pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def format_report(queries: list[dict], scores: dict, rows: list[dict], current: dict, best: dict | None,
                  args, meta: dict) -> str:
    prompt = meta.get("query_prompt", "")
    n_in = sum(q["category"] == IN_SCOPE for q in queries)
    n_oos = len(queries) - n_in
    lines = ["# FAQ retrieval calibration report", "",
             f"Model: {meta.get('model', '?')}. Records: {meta.get('records', '?')}. "
             f"Queries: {len(queries)} ({n_in} in scope, {n_oos} out of scope). "
             f"Query prompt: {prompt!r}." if prompt else "Query prompt: none.", f"Sweep step: {args.step}.", ""]

    lines += ["## Score distributions (top-1 cosine unless noted)", "",
              "| group | n | min | p10 | median | p90 | max |", "|---|---|---|---|---|---|---|"]
    for name, vals in score_distribution(queries, scores):
        if vals:
            lines.append(f"| {name} | {len(vals)} | {min(vals):.3f} | {percentile(vals, .1):.3f} | "
                         f"{statistics.median(vals):.3f} | {percentile(vals, .9):.3f} | {max(vals):.3f} |")
    lines.append("")

    def row_line(label: str, r: dict) -> str:
        return (f"| {label} | {r['single']:.2f} / {r['minimum']:.2f} / {r['margin']:.2f} | "
                f"{pct(r['single_correct'])} | {pct(r['single_wrong'])} | {pct(r['clarify_hit'])} | "
                f"{pct(r['rejected'])} | {pct(r['oos_false_single'])} | {pct(r['oos_false_clarify'])} |")

    lines += ["## Settings compared", "",
              "In-scope columns are percentages of in-scope queries. The last two columns are percentages of "
              "out-of-scope queries (lower is better). `useful` = single_correct + 0.5 x clarify_hit.", "",
              "| setting | single / min / margin | single correct | single WRONG | clarify hit | rejected "
              "| oos single | oos clarify |",
              "|---|---|---|---|---|---|---|---|",
              row_line("current (env / defaults)", current)]
    if best:
        lines.append(row_line("recommended", best))
    lines.append("")
    if best:
        lines += ["Recommended environment values:", "", "```",
                  f"FAQ_SINGLE_THRESHOLD={best['single']:.2f}",
                  f"FAQ_MIN_THRESHOLD={best['minimum']:.2f}",
                  f"FAQ_MARGIN_THRESHOLD={best['margin']:.2f}"]
        if prompt:
            lines.append(f"FAQ_QUERY_PROMPT={prompt}")
        lines += ["```", ""]
    else:
        lines += [f"No setting met the caps (single_wrong <= {pct(args.max_wrong_single).strip()}, "
                  f"oos single <= {pct(args.max_oos_single).strip()}). Relax a cap or improve the data "
                  "(variants, decoy questions) and re-run.", ""]

    # Frontier: best useful rate at each wrong-single level, for the cost of a stricter cap.
    lines += ["## Trade-off: strictness versus useful answers", "",
              "Best achievable `useful` score for different caps on confident wrong answers "
              "(single_wrong and oos single both capped).", "",
              "| cap | single / min / margin | useful | single correct | clarify hit | oos accepted (single + clarify) |",
              "|---|---|---|---|---|---|"]
    for cap in (0.0, 0.01, 0.02, 0.05):
        r = recommend(rows, cap, cap)
        if r:
            lines.append(f"| {pct(cap).strip()} | {r['single']:.2f} / {r['minimum']:.2f} / {r['margin']:.2f} | "
                         f"{pct(r['useful'])} | {pct(r['single_correct'])} | {pct(r['clarify_hit'])} | "
                         f"{pct(r['oos_false_single'] + r['oos_false_clarify'])} |")
        else:
            lines.append(f"| {pct(cap).strip()} | not reachable | | | | |")
    lines.append("")

    shown = best or current
    lines += [f"## Queries that go wrong at {'the recommended' if best else 'the current'} setting", ""]
    by_id = {q["id"]: q for q in queries}
    bad = []
    for q in queries:
        label = classify(q, scores[q["id"]], shown["single"], shown["minimum"], shown["margin"], args.maximum)
        if q["category"] == IN_SCOPE:
            if label in ("single_wrong", "clarify_miss", "rejected"):
                bad.append((label, q))
        elif label != "rejected":
            bad.append((f"oos_{label}", q))
    # Worst first: confident wrong answers, then wrongly accepted out-of-scope queries, then misses.
    order = {"single_wrong": 0, "oos_false_single": 1, "oos_false_clarify": 2, "clarify_miss": 3, "rejected": 4}
    bad.sort(key=lambda item: order.get(item[0], 9))
    if not bad:
        lines.append("None.")
    for label, q in bad:
        top = ", ".join(f"{rid} {s:.2f}" for rid, s in scores[q["id"]][:3])
        exp = f" expected {'/'.join(q['expected'])};" if q["expected"] else ""
        lines.append(f"- `{label}` ({q['category']}) \"{by_id[q['id']]['query']}\":{exp} got {top}")
    lines.append("")
    return "\n".join(lines)


def current_settings() -> SimpleNamespace:
    """Thresholds the chat app would use right now (FAQ_* env vars, else defaults)."""
    sys.path.insert(0, str(HERE.parent))
    from dcrai.llm.openchat import Settings
    return Settings.from_env()


def format_ab(queries: list[dict], runs: list[tuple[str, dict, dict]], args) -> str:
    """Side-by-side comparison of query-prompt settings."""
    lines = ["# Query prompt comparison", "",
             "Threshold-free numbers first, then the best thresholds each setting reaches under the same caps "
             f"(single_wrong <= {pct(args.max_wrong_single).strip()}, oos single <= {pct(args.max_oos_single).strip()}).",
             "", "| query prompt | top-1 accuracy | top-3 recall | in-scope top-1 p10 | off-scope top-1 p90 | separation |",
             "|---|---|---|---|---|---|"]
    detail = []
    for prompt, scores, _meta in runs:
        m = summary_metrics(queries, scores)
        name = repr(prompt) if prompt else "none"
        lines.append(f"| {name} | {pct(m['top1_accuracy'])} | {pct(m['top3_recall'])} | "
                     f"{m['in_scope_top_p10']:.3f} | {m['oos_top_p90']:.3f} | {m['separation']:+.3f} |")
        rows = sweep(queries, scores, args.step, args.maximum)
        best = recommend(rows, args.max_wrong_single, args.max_oos_single, args.max_oos_accept)
        if best:
            detail.append(f"| {name} | {best['single']:.2f} / {best['minimum']:.2f} / {best['margin']:.2f} | "
                          f"{pct(best['useful'])} | {pct(best['single_correct'])} | {pct(best['clarify_hit'])} | "
                          f"{pct(best['oos_false_single'] + best['oos_false_clarify'])} |")
        else:
            detail.append(f"| {name} | caps not reachable | | | | |")
    lines += ["", "Separation is (in-scope top-1 p10) minus (off-scope top-1 p90). Positive means a score "
              "threshold can split the groups; larger is easier to tune.", "",
              "| query prompt | best single / min / margin | useful | single correct | clarify hit | oos accepted |",
              "|---|---|---|---|---|---|"] + detail + [""]
    return "\n".join(lines)


def load_or_score(queries: list[dict], digest: str, prompt: str, scores_base: Path, from_scores: bool,
                  shared_model=None):
    """Scores for one prompt setting, from the cache or from the real retriever.

    Returns (scores, meta, retriever_or_None). The retriever is returned so a second setting can reuse
    its loaded model instead of loading another copy.
    """
    path = scores_path_for(scores_base, prompt)
    if from_scores:
        cache = json.loads(path.read_text(encoding="utf-8"))
        if cache.get("queries_digest") != digest:
            raise SystemExit(f"{path.name} was made for a different query file. Re-run without --from-scores.")
        if cache.get("meta", {}).get("query_prompt", "") != prompt:
            raise SystemExit(f"{path.name} was made with a different query prompt. Re-run without --from-scores.")
        return cache["scores"], cache.get("meta", {}), None

    sys.path.insert(0, str(HERE.parent))
    from faq_search.retriever import FAQRetriever
    retriever = FAQRetriever(query_prompt=prompt)
    if shared_model is not None:
        retriever._model = shared_model
    print(f"Scoring {len(queries)} queries, query prompt {prompt!r} (first call loads the model)...", file=sys.stderr)
    scores = score_queries(queries, retriever)
    emb_meta = json.loads((HERE.parent / "faq_search" / "data" / "faq_embeddings_meta.json").read_text(encoding="utf-8"))
    meta = {"model": emb_meta.get("model"), "records": emb_meta.get("num_records_covered"),
            "embeddings_generated_at": emb_meta.get("generated_at"), "query_prompt": prompt}
    path.write_text(json.dumps({"queries_digest": digest, "meta": meta, "scores": scores}), encoding="utf-8")
    print(f"Cached scores in {path}", file=sys.stderr)
    return scores, meta, retriever


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES,
                        help="base name of the score cache (a prompt tag is added when a query prompt is used)")
    parser.add_argument("--from-scores", action="store_true", help="skip the model, use the cached scores")
    parser.add_argument("--query-prompt", default=None,
                        help="prompt name or text applied to the query only (default: FAQ_QUERY_PROMPT, else none)")
    parser.add_argument("--ab", action="store_true", help="compare no prompt against the model's 'query' prompt")
    parser.add_argument("--step", type=float, default=0.02, help="grid step for the sweep")
    parser.add_argument("--maximum", type=int, default=3, help="options offered on clarify_match")
    parser.add_argument("--max-wrong-single", type=float, default=0.02,
                        help="cap on in-scope queries answered confidently with the wrong FAQ (default 2%%)")
    parser.add_argument("--max-oos-single", type=float, default=0.0,
                        help="cap on out-of-scope queries answered confidently (default 0%%)")
    parser.add_argument("--max-oos-accept", type=float, default=None,
                        help="optional cap on out-of-scope queries that get any answer or options")
    parser.add_argument("--report", type=Path, help="also write the report to this markdown file")
    args = parser.parse_args(argv)

    queries = load_queries(args.queries)
    digest = file_digest(args.queries)

    if args.ab:
        runs, model = [], None
        for prompt in ("", "query"):
            scores, meta, retriever = load_or_score(queries, digest, prompt, args.scores, args.from_scores, model)
            if retriever is not None:
                model = retriever.model
            runs.append((prompt, scores, meta))
        report = format_ab(queries, runs, args)
    else:
        prompt = args.query_prompt if args.query_prompt is not None else os.getenv("FAQ_QUERY_PROMPT", "")
        scores, meta, _ = load_or_score(queries, digest, prompt.strip(), args.scores, args.from_scores)
        missing = [q["id"] for q in queries if q["id"] not in scores]
        if missing:
            print(f"No scores for {missing[:5]}... Re-run without --from-scores.", file=sys.stderr)
            return 2
        rows = sweep(queries, scores, args.step, args.maximum)
        cur = current_settings()
        current = evaluate(queries, scores, cur.single, cur.minimum, cur.margin, cur.maximum)
        best = recommend(rows, args.max_wrong_single, args.max_oos_single, args.max_oos_accept)
        report = format_report(queries, scores, rows, current, best, args, meta)

    print(report)
    if args.report:
        args.report.write_text(report + "\n", encoding="utf-8")
        print(f"Wrote {args.report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
