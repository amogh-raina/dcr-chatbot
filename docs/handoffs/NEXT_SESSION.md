# Next session (written 2026-10-09)

**Task: run the Help panel follow-up eval and calibrate the panel's gating from the results.**

Read first:
1. `docs/handoffs/HANDOFF_2026-10-09_followup_eval.md`: why the eval exists, what it runs, how to run it, what to look for, the
   calibration levers and the decisions to make with Amogh.
2. `CLAUDE.md`: "Session 2026-10-09 (summary)", then "Follow-up gating" and "Relevance check fix".

Start with: `python -m evals.eval_followups --repeat 3` (needs the model, `OPENAI_API_KEY`,
`DECISIONS_ENABLED=1`), then read `evals/reports/followup_report.md` with Amogh, starting with the WRONG cases.

State: live graph **2014078**; the rebuilt Clean graph (with `FAQ_Welcome`) is not imported yet. Restart
`python app.py` after backend changes. Tests 204 OK.

Earlier UI work: `docs/handoffs/UI_HANDOFF.md` (2026-10-08); much of it was done or reshaped on 2026-10-09 (see CLAUDE.md).
Still open: delete `zz_delete_probe`; stale bundles (CLAUDE.md); second labeller for the eval files; rotate
`FAQ_API_KEY`; fixed tunnel hostname; update the design system artifact to the 2026-10-09 decisions.
