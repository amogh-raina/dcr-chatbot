# Handoff: Help panel follow-up eval (written 2026-10-09)

**Task for the next session:** run the follow-up eval, read the results with Amogh, and calibrate the Help panel's
gating (classifier, rewrite, relevance check) until it never answers with a wrong FAQ, while still answering what the
FAQ does cover. Read this file, then `CLAUDE.md` sections "Session 2026-10-09 (summary)", "Follow-up gating" and
"Relevance check fix".

## 1. Why this eval exists

The Help panel beside the application form answers questions from the FAQ. On 2026-10-09 it gave a confidently
wrong answer: on "Did you have work in the last three years?", after showing FAQ_17 ("Does my previous work history
count against me?"), the applicant asked "okay, but would the number of hours matter here?" and got FAQ_16 (5-6 hours
of *current* work capacity). No FAQ answers how hours of *past* work count, so the right reply was "the FAQ does not
cover that". The trace showed three separate weaknesses:

1. The follow-up was searched as raw words, and the relevance check judged it out of context.
2. The Decisions relevance check was too strict elsewhere: it dropped clear matches (FAQ_17 at 0.06, FAQ_P05 at 0.11).
3. Nothing measured any of this. The earlier composed-query eval (36 field cases) has no history and no "no FAQ answers
   this" cases, and `evals/cases/triage_labels.json` has only 2 follow-ups.

The code was changed the same day (see CLAUDE.md "Follow-up gating"), but only checked with unit tests and fake LLM
answers. This eval is the first measurement with the real model, the real prompts and the real thresholds.

## 2. What it runs

`evals/eval_followups.py` runs the unchanged `application_runtime.ask` for each case. Only DCR is replaced:
- the search goes to the local retriever with the FAQ API's own decision rule (`faq_search.api.decide`, single 0.80 /
  min 0.50 / margin 0.12, top-3 options);
- every LLM step is real: the contextual/distress classifier (`panel_signals_decisions`), the rewrite
  (`PANEL_REWRITE_PROMPT`), the relevance check (`relevant_decisions`, or `relevant` without Decisions).

Each case seeds the panel state the way the app keeps it: the field on screen (label, help text and HelpFAQ links
from `xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean.xml`), the previous panel question (`help_last_message`) and
the FAQ shown for it (`help_last_faq`, with the first 300 characters of its answer). The question is then asked with
the field as context, as the panel does by default.

Cases: `evals/cases/eval_followup_queries.json`, 49 cases in 9 groups:

| group | what it tests | n | right behaviour |
|---|---|---|---|
| F | follow-up that a *different* FAQ answers ("how old can they be?" after the documents FAQ) | 14 | answer that FAQ |
| N | follow-up no FAQ answers ("do they have to be translated into Danish?") | 8 | say it cannot answer |
| S | follow-up the FAQ just shown already covers ("so they won't contact my old employers?") | 3 | point back to it |
| C | self-contained question, no history | 6 | answer, no rewrite |
| T | topic switch after a previous FAQ | 4 | answer the new topic, not pulled back |
| V | vague, depends on the field on screen ("what does this mean?") | 6 | answer from the field's FAQs |
| A | an answer typed into Help ("about 10 hours a week") | 3 | no answer |
| O | out of scope, or "will I get it?" | 3 | no answer |
| M | second-step follow-up | 2 | answer |

The labels were written by the agent and reviewed by nobody. Some are judgment calls and say so in `note` (n08, s01,
o01, m02). **Correct a label rather than tune the system to it.**

## 3. How to run

```bash
conda activate dcr
# .env must have OPENAI_API_KEY and DECISIONS_ENABLED=1 (the script warns otherwise)
python -m evals.eval_followups                          # all 49 cases, ~2-4 s each
python -m evals.eval_followups --repeat 3               # LLM steps vary: run 3x before trusting a number
python -m evals.eval_followups --cases n01,s01,f04      # a few cases, with every search printed
```

Outputs: `evals/reports/followup_report.md` (summary, sweeps, a line per case) and
`evals/runs/followup_results.json` (everything per run: classifier probabilities, the rewrite, each search with
top-3 scores, relevance probabilities and what was kept, the final response). No DCR session is created and nothing
is logged to `traces/interactions`. It does call OpenAI (about 2-4 calls per case).

To try a setting without editing `.env`: `DECISIONS_RELEVANT_MIN=0.4 python -m evals.eval_followups`.

## 4. What to look for (in this order)

1. **WRONG** (an FAQ was answered that does not answer the question). This is the number that matters most: a wrong
   answer shown as an official answer is worse than "I don't know". Target 0. Read every WRONG case in the JSON: was
   the rewrite wrong, the search, or the relevance check?
2. **N, A, O groups**: should be all `correct` (no answer). `shown_options` there is not a wrong answer, but the
   panel offered FAQs as "may fit" for something no FAQ covers.
3. **F, M, V, C, T groups**: `correct` = answered with the right FAQ, `partial` = it was among the options,
   `missed` = nothing shown (a false refusal). Misses cost less than WRONG, but too many make the panel useless.
4. **S group**: did it point back ("same_faq")? Note the current wording ("It does not say more about this.") is
   wrong for these cases, because the FAQ above *does* answer them. A wording decision is needed (section 6).
5. **Classifier sweep** (`DECISIONS_CONTEXT_MIN`): follow-ups caught vs self-contained left alone. A self-contained
   question wrongly flagged is only rewritten (mild risk); a follow-up missed is searched as raw words (the 2026-10-09
   bug). Prefer catching follow-ups.
6. **Relevance sweep** (`DECISIONS_RELEVANT_MIN`): expected FAQs kept vs other FAQs kept at each threshold. "Other
   FAQs" includes some that would also be fine, so precision is a lower bound. Look for the threshold where the
   expected FAQs are kept and the N-group candidates are not.
7. **Rewrites** (`rewrite` in the JSON, also "understood as" in the console): read them all once. A rewrite that
   changes the meaning (pulls in the previous topic on a T case, or drops "before my studies" on n01) is the root
   cause to fix first, because every later step trusts it.
8. **Latency**: median and max in the report. The panel waits for all steps; above ~4 s it feels slow.

## 5. How to calibrate (levers, cheapest first)

Change one lever at a time and rerun with `--repeat 3`. Record each run's verdict counts in CLAUDE.md.

| lever | where | when to touch it |
|---|---|---|
| `DECISIONS_RELEVANT_MIN` (0.5) | `.env` | relevance sweep shows a clearly better cut-off |
| `DECISIONS_CONTEXT_MIN` (0.7) | `.env` | classifier sweep: follow-ups missed (lower it) or self-contained ones flagged (raise it) |
| relevance predicate wording | `retrieval_llm.relevant_decisions` | WRONG cases where the check passed an FAQ on a different situation, or misses where it dropped the right one |
| contextual predicate wording and examples | `retrieval_llm.panel_signals_decisions` | classifier sweep has no good threshold (the probabilities overlap) |
| rewrite prompt | `retrieval_llm.PANEL_REWRITE_PROMPT` | rewrites change the meaning, or keep the previous topic on topic switches |
| answer preview length (300 chars) | `retrieval_llm.ANSWER_PREVIEW_CHARS` | the check misjudges FAQs whose key point comes later in the answer |
| search thresholds (single/min/margin) | `.env` `FAQ_*_THRESHOLD` | only with `evals/calibrate_thresholds.py`; they also change the FAQ chat |
| question variants | `faq_qa_records.json` + `python faq_search/embed_faq_data.py` | the right FAQ is not in the search top 3 even for a good rewrite |

Ideas for the Decisions questions, in case wording alone is not enough:
- **Two predicates per candidate** instead of one: `answers` ("does this FAQ answer the question?") and `same_topic`
  ("is it about the same situation?"). Then: answers -> show the answer; same_topic only -> show it as "related, but
  does not answer exactly this"; neither -> drop. This is the middle tier that does not exist yet.
- **Pass the field on screen to the relevance check** as well as the resolved question, so "here" and "this" are
  judged in context even when the classifier missed the follow-up.
- **One "is this a question at all?" predicate** in the classifier call (it already returns `contextual` and
  `distress`) for the A group, instead of relying on the search finding nothing.

About models: the misses so far came from wrong inputs (no history, judging a composed string), not from a weak
model. Try the levers above first. A reasoning model would add seconds to every question; if used at all, use it
offline to re-grade the eval, not in the panel.

## 6. Decisions to make with Amogh after the first run

1. The "same FAQ" reply: keep "does not say more about this", or say "The answer above covers this." when the check
   says the shown FAQ answers the follow-up (needs one predicate)?
2. A middle tier ("related, may help") for candidates on the right topic that do not answer: yes or no, and the
   wording?
3. Should a statement typed into Help (group A) get "If that was your answer, give it in the form instead." (it does
   today, when it looks like a statement and nothing is found) or be detected up front?
4. Are the agent's labels right? A second labeller for this file and `eval_composed_queries.json` was already an open
   item.

## 7. State at handoff

- Graph in use: **2014078**. The rebuilt Clean graph file (with `FAQ_Welcome`) is not imported yet; Amogh imports the
  final version at the end of this work. The eval reads field labels, help text and links from the graph *file*, not
  from 2014078; they are the same for Form0.
- Bundle: `static/demo/assets/index-BMLDYZF-.js` + `index-BabljOgH.css` + `icons8-bot-K3HB9ED8.gif`.
- `.env` was recreated from `.env.example` on 2026-10-09; it needs `DECISIONS_ENABLED=1` for the panel as designed.
- Restart `python app.py` after any backend change (a stale server caused one round of confusion on 2026-10-09).
- Tests: 204 OK (`python -m unittest` over `tests/test_*.py` except the two that need the model).
- Also open: delete `zz_delete_probe` in the repo root; stale bundles listed in CLAUDE.md; rotate `FAQ_API_KEY`;
  fixed tunnel hostname.
