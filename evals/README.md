# evals/

Everything that measures the system. Scripts here call real models and cost money; the unit tests in `tests/` never do.

```
evals/
  cases/      inputs: labelled queries (checked in)
  runs/       outputs: cached scores and raw results (regenerated)
  reports/    outputs: readable reports (regenerated)
  *.py        the runners
```

Run from the repo root with `python -m evals.<name>`.

| Runner | Question it answers | Cases | Writes |
|---|---|---|---|
| `calibrate_thresholds` | Where should the retrieval score thresholds sit? | `cases/eval_queries.json` | `runs/eval_scores*.json`, optional `--report` |
| `eval_composed` | Does retrieval work for questions composed from application field help? | `cases/eval_composed_queries.json` | optional `--report` (convention: `reports/composed_report.md`) |
| `eval_followups` | Do follow-up messages in the help panel get the right FAQ, and how often is an answer wrong? | `cases/eval_followup_queries.json` | `reports/followup_report.md`, `runs/followup_results.json` |
| `eval_live` | Does the real Portal graph and the running app behave as the spec gates say? `table`: the nine rows through the Portal (no model). `panel`: the follow-up cases as real sessions over HTTP, plus the handover, person, deadline, out-of-scope and Confirm scenarios | `cases/eval_followup_queries.json` (groups F, C, N, S, T, A, O, M) | `reports/live_table_report.md`, `reports/live_outcome_report.md`, `runs/live_outcome_results.json` |
| `diagnose_queries` | Why did this one query retrieve what it did? | ad hoc | stdout |

`eval_followups --regrade PATH` grades a stored results file again with the current case labels and writes the report
(`--report`), without calling a model or loading the retriever, and writes no JSON. The report starts with a metrics
table (WRONG, answered and correct, correct total, `confirm_right`, `confirm_wrong`, `confirm_unneeded`, related offers,
options, missed, latency) and, for a live run, the `prompts.version()` and the three phase 1 flags. Example, the 2026-10-09
baseline with the f08 label corrected (WRONG 30, correct 51, answered and correct 35):
`python -m evals.eval_followups --regrade evals/runs/followup_results.json --report evals/reports/followup_baseline_regraded.md`.
A live run also records `registry.version()` in the report header, so a result can be tied to the exact settings, prompts and FAQ data of its snapshot in `traces/registry/`.
A frozen copy of that results file is `tests/fixtures/followup_results_2026-10-09.json`. For the phase 1 gate run, write
to new files so the baseline stays: `--report evals/reports/followup_report_phase1.md --json evals/runs/followup_results_phase1.json`.

Spec 03 (outcome table): the panel now runs the outcome function on every question turn, and an unscoped typed message
goes through a two-value triage first (`PANEL_TRIAGE`, default on). The stub in `eval_followups` still replaces DCR (it has
no `FAQ_Triage` choices, so the triage step falls back to a search and the table runs with the code function). To report after
a re-run: the outcome mix by row (the `faq_outcome` lines carry `outcome_row`), and how many group O (out of scope) turns now end in row 1.
No tolerance is set by the spec; WRONG 0 is still the gate. `Help_UserQuestion` is a known input of the stub.

`cases/triage_labels.json` holds the labelled triage cases used by the probe in `tools/probe_decisions.py`.

Needs `OPENAI_API_KEY` in `.env` (the runners load it) and, for retrieval, the embedding model (`faq_search/requirements.txt`).
When you report a result, record `prompts.version()` (see `prompts/README.md`) and the thresholds in effect.

Live eval (`eval_live`). It needs the app running for `panel` (`python app.py`, restarted after any `.env` change) and the Portal credentials in `.env`. Both parts exit 1 when a gate fails.

    python -m evals.eval_live table --graph <graph id>
    python -m evals.eval_live panel --graph <graph id> --expect-mode shadow --repeat 3

`--expect-mode` must match the `OUTCOME_MODE` the running app was started with: `shadow` needs `outcome_dcr` in every logged outcome and no `outcome_mismatch`; `dcr` also needs `outcome_source: dcr`; `code` needs no DMN result. Group V of the follow-up cases needs a field on screen and is not replayed. The live run replays each case as two turns (the previous question, then the message), so the panel's own context is built by the app, not seeded.
