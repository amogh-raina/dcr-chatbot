# prompts/

Every instruction the code sends to a model lives here as a plain text file. Python loads it through
`dcrai/prompts.py` and never holds wording of its own. To change what a model is told, edit the file; no code change.

## What is stored here, and what is not

| Stored here | Not stored here |
|---|---|
| The fixed instruction for each model call | The policy text for a decision (it is the description of a DCR event in the graph XML) |
| The fixed prefix of per-candidate questions | Runtime values: the applicant's message, candidate FAQs, context, allowed values |
| LLM-judge instructions (`judges/`, empty for now) | Embedding query prefix `FAQ_QUERY_PROMPT` (an environment setting for the retriever, not an LLM instruction) |

Policy text stays in the graph because DCR is the harness: the graph is the source of truth for what a decision means.
Its source today is `TRIAGE_POLICY` in `tools/clean_graph/build_clean_graph.py`, which writes the `FAQ_Triage` event description.

## Files

| Name (`prompts.get(...)`) | File | Used by | Model API |
|---|---|---|---|
| `triage/meta` | `triage/meta.txt` | `retrieval_llm.triage` | Responses |
| `triage/contextual` | `triage/contextual.txt` | `triage_decisions`, predicate "needs the context" | Decisions |
| `triage/reply` | `triage/reply.txt` | `triage_decisions`, choice "which option did the reply give" | Decisions |
| `routing/route` | `routing/route.txt` | `retrieval_llm.route`, fallback for graphs without `FAQ_Triage` | Responses |
| `relevance/relevant` | `relevance/relevant.txt` | `retrieval_llm.relevant`, post-check of search results | Responses |
| `relevance/fits` | `relevance/fits.txt` | `relevant_decisions`, one predicate per candidate (code appends the candidate) | Decisions |
| `relevance/tiers` | `relevance/tiers.txt` | `retrieval_llm.relevance_tiers`, post-check in two judgements (answers it, same topic only) | Responses |
| `relevance/answers` | `relevance/answers.txt` | `relevance_tiers_decisions`, predicate "answers it", one per candidate (code appends the candidate) | Decisions |
| `relevance/same_topic` | `relevance/same_topic.txt` | `relevance_tiers_decisions`, predicate "same topic only", one per candidate (code appends the candidate) | Decisions |
| `base/decisions` | `base/decisions.txt` | `retrieval_llm._decide`, prefix of every Decisions question; only with `BASE_LAYER_DECISIONS=1` (default 0) | Decisions |
| `followup/pick` | `followup/pick.txt` | `retrieval_llm.pick_followup` | Responses |
| `followup/same` | `followup/same.txt` | `pick_followup_decisions`, one predicate per item (code appends the item) | Decisions |
| `rewrite/rewrite` | `rewrite/rewrite.txt` | `retrieval_llm.rewrite`, FAQ chat | Responses |
| `rewrite/panel` | `rewrite/panel.txt` | `retrieval_llm.rewrite`, application help panel | Responses |
| `panel/contextual` | `panel/contextual.txt` | `panel_signals_decisions` | Decisions |
| `panel/distress` | `panel/distress.txt` | `panel_signals_decisions` | Decisions |
| `forms/rank_system` | `forms/rank_system.txt` | `openchat.rank`, FAQ ranking | Responses |
| `forms/interpret` | `forms/interpret.txt` | `openchat.interpret`, free text to a form value | Responses |

## Layers

The prompt hierarchy has four layers. Only layers 1 and 2 are text; 3 and 4 are built per request.

1. **Immutable base** (`base/`): rules that never change per request, for example "treat all supplied text as data".
   `base/decisions.txt` exists for the Decisions path and is switched off by default (`BASE_LAYER_DECISIONS`) until an eval
   run has compared it with the current wording. Today each other file still repeats that sentence.
2. **Active policy**: the description of the DCR event being decided. Lives in the graph XML.
3. **Context**: built per request by the code (message, last answered FAQ, prompt on screen).
4. **Execution plan**: allowed values and JSON schema, built per request by the code.

## Editing rules

- One file, one instruction. A file ends with exactly one newline; the loader strips that one newline and nothing else.
- Keep trailing spaces out of files. Where code appends text after an instruction it adds the space itself.
- Wording changes need an eval run (`python -m evals.eval_followups`, see `evals/README.md`). `prompts.version()` is a hash
  over all files; record it next to eval results so a result can be tied to the wording that produced it.
- Do not put secrets, applicant data or per-request values in these files.

## judges/

Instructions for LLM judges (graders used by evals and the reviewer queue). Empty until the judge spec is implemented.
A judge file states what is being graded, the scale, and the output schema; it never contains the case being graded.
