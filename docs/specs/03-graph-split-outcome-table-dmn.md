# Spec 03: Graph split, outcome table, DMN

Roadmap phase 3 and the graph part of phase 5. Gate: the chat never fires a determination; all nine rows tested.
Written 2026-10-10 against the layout restructured that day and against `docs/specs/01-stop-wrong-answers.md` (458 lines). Read `docs/specs/00-brief.md` and `docs/specs/00-scope-and-roadmap.md` first. Spec 02 (`docs/specs/02-registry-and-trace-record.md`, sections 9 and 10) was read for its task order, expected spec 03 edits and assumptions about this spec; section 4.4 and section 10 list what this spec assumes of it.

## 1. Status and scope

Draft for review. This spec defines the outcome function (signature, inputs, the nine rows, seven outcomes, first match wins), splits the Clean graph into two retrieval Robots (FAQ chat, application Help panel) that share triage, scope, the out-of-scope message, the outcome table and the handover, moves follow-up determinations from the chat to the application session, and builds the outcome table as an embedded DMN in the graph XML so Amogh can import it into the Portal and debug it. The table is written first as code (`dcrai/chat/outcome.py`) and the DMN is generated from the same row data, so the two cannot drift. The DMN is introduced in three host modes (`code`, `shadow`, `dcr`); `code` is the default and is also the fallback if the Portal does not behave. Constructs that no export in this repository shows are labelled and come with a Portal fixture request (section 7).

In scope:
- Outcome function in code: nine rows, seven outcomes, derived inputs, Handover rule, clarified and miss counters, one unit test per row.
- Graph split inside one graph file: session events, panel search Robot and events, shared core, determinations gated to the application session, builder changes.
- Outcome table in the graph: gate input events, DMN Robot, result label, `TurnOutcome` event, one pending outcome event per outcome, outcome message events.
- Host wiring in both interfaces: replace spec 01's `interim_outcome`, scope input, panel triage, handover in the chat, determinations in the panel only, DMN modes.
- Portal import checklist, fixture requests, fallback, file ownership and edit order.

Out of scope:
- The trace schema, registry, versioned settings, panel context record (spec 02). This spec says which fields it needs populated.
- Relevance tiers, Confirm behaviour, fallback-rewrite removal, f08, wording decisions WD1 to WD4 (spec 01).
- Judges, reviewer queue, question variants (spec 04).
- Response deadlines that read a date from an event; hit policy ALL; Robot:Prime and Robot:Terminator; spawned subgraphs (not used here).
- The embedding floor (gate 1 of the roadmap pipeline) and a panel-only policy event (see Q5).
- Moving the WD1 same-FAQ texts and the WD3 statement note into DCR events (they stay host constants).

## 2. Current state (observed)

All line numbers read on 2026-10-10. Commands run on the device: `tools/clean_graph/simulate_clean_graph.py` on the NoEffect graph (39 checks pass, FAILURES 0) and `validate_dcr_xml.py` on the same graph and on the DMN export (0 errors).

### 2.1 Graph and builder

| # | Claim | Source |
|---|---|---|
| C1 | One graph file serves both interfaces. The builder prunes the Structured graph to `Form0` and adds the FAQ layer; the chat and the application are two simulations of the same graph | `tools/clean_graph/build_clean_graph.py:1-8,76-85`; `dcrai/chat/retrieval_runtime.py:367-376`; `dcrai/application/application_runtime.py:790` |
| C2 | There is one Robot, `FAQ_Retrieve`, effect `handicap-faq-v2`, `q` = `FAQ_UserQuestion`, quoted continuations to `FAQ_RetrievalOk`, `FAQ_RetrievalFail`, `FAQ_RetrievalTimeout` | `build_clean_graph.py:55,204-207,219-231`; `simulate_clean_graph.py:149-150` |
| C3 | `FAQ_Triage` has values 1, 2, 4, 5. Value 1 includes `FAQ_UserQuestion`, other values exclude it; 4 makes `FAQ_Goodbye` pending, 5 makes `FAQ_OutOfScope` pending. The host refuses any other dictionary | `build_clean_graph.py:309-310,327-333`; `retrieval_runtime.py:40,425-427` |
| C4 | The selector `FAQ_DeterminationSelector` and the `Det*` events have no precondition; the `*_Ask` events start excluded | `build_clean_graph.py:243-269,408` |
| C5 | Message events (`FAQ_Scope`, `FAQ_Welcome`, `FAQ_OutOfScope`, `FAQ_NoMatch`, `FAQ_Goodbye`, `Help_Handover`) are label events the host reads by group and executes; `FAQ_NoMatch` is executed inside `search()` | `build_clean_graph.py:278-305,330-333,370-378`; `retrieval_runtime.py:89-101,215` |
| C6 | `relation()` supports response, condition, coresponse, include, exclude only; `event_data()` supports text, label, yesno, intchoice only; `add_event()` has no `computation` | `build_clean_graph.py:118-146,149-184,192-200` |
| C7 | The effect is stripped from `FAQ_Retrieve` only, for the NoEffect variant | `build_clean_graph.py:446-458` |
| C8 | Marking: all new events are included except the `*_Ask` events and `FAQ_UserQuestion`; nothing is pending | `build_clean_graph.py:404-415` |
| C9 | The local simulator asserts exactly one Robot and exactly three System events, runs Robots as effect calls only, and executes `FAQ_UserQuestion` and the selector with no session precondition | `simulate_clean_graph.py:68-78,98-108,118,149-150` |

### 2.2 Host behaviour

| # | Claim | Source |
|---|---|---|
| C10 | Chat and panel share one `search()` and one set of search event ids | `retrieval_runtime.py:36,171-216`; `application_runtime.py:689-698` |
| C11 | Outcome is chosen by candidate count in two places (chat `len(found)==1`, panel `direct = ... len(found)==1`). Spec 01 replaces these with `interim_outcome` | `retrieval_runtime.py:236-244`; `application_runtime.py:741-756`; spec 01 section 4.3 |
| C12 | The chat asks a scope question when the Decisions triage is unsure (confidence below `DECISIONS_TRIAGE_MIN`, top two values 1 and 5) and executes `FAQ_Triage` after the answer | `retrieval_llm.py:261`; `retrieval_runtime.py:360-363,433-435,466-469` |
| C13 | The panel executes `FAQ_Triage = 1` itself for every question and runs no scope check | `application_runtime.py:585-587,674-678,691` |
| C14 | The chat fires a follow-up determination after every answer: selector by exact label, else a `pick_followup` model call | `retrieval_runtime.py:295-315` |
| C15 | The panel does not fire determinations; its docstring says they belong to the chat | `application_runtime.py:563-580,587` |
| C16 | Misses: the panel counts no match and "None of these", hands over at 2 (reason 2, once per session); the chat counts nothing and has no handover | `application_runtime.py:512,528-561,735-736,763-768` |
| C17 | The application view picks its field from `Form0:` children and tagged application events only, and `_unchanged` fingerprints only those, so new FAQ-layer events do not disturb it | `application_runtime.py:27-31,48-58,134-141,498-506` |
| C18 | Outcome texts are host strings: confirm and options responses, options prompt, rephrase, scope question | `retrieval_runtime.py:243-244,356,467-469`; `application_runtime.py:727-728,752` |
| C19 | The panel starts with no entry event; this is the place to execute a session event | `application_runtime.py:200-236` |

### 2.3 DMN evidence

| # | Claim | Source |
|---|---|---|
| C20 | DMN chatbot export: Robot event with `computation="DMN-computation"` and no eventData; `hitPolicy="FIRST"`; string input (`Country`) and integer input (`Age`) whose labels equal event ids; last rule all dashes; conditions and milestones from inputs to the Robot (same `link`); responses from inputs to the Robot; an update relation to a label with value expression `"Can you purchase alcohol? " + DMN` | `xml graphs/DMN chatbot - english.xml:90,176-192,319-336` |
| C21 | Corona export: DMN outputs are strings and are used as guards on relations whose source is the DMN-computed event (`CloseContact = "retry"`, `CloseContact = "yes"`). Integer entries (`1`, `0`), dashes, three inputs and five inputs occur. No `hitPolicy` attribute on those tables. Date range entries such as `[WhenSymptoms-PT48H;LastSymptoms+PT48H]` occur. The source event there is a computed subprocess, not a Robot | `xml graphs/Corona - ChatBot SOP.xml:1038-1041,1066,1086,1161,1197,1347-1352` |
| C22 | A generator for the compiled expression (right-nested `AND`, `[If] THEN [..] ELSE [..]` chain ending in `ELSE ( null )`, `-` as `true`) reproduces the compiled `value` of `DMN-computation` and of `CloseContact-computation` byte for byte (run 2026-10-10 on a scratch copy; the code is in section 4.7) | scratch run, both exports |
| C23 | The same generator output for the nine-row table below, evaluated by a small evaluator, agrees with the Python table on all 64 valid input combinations | scratch run, 2026-10-10 |

## 3. Requirements

| Id | Requirement | Level |
|---|---|---|
| R1 | `outcome.table(scope, search, relevance, clarified)` MUST return `(row, outcome)` for the nine rows of section 4.2, first match wins, with no I/O. | MUST |
| R2 | The domains MUST be exactly those of section 4.2. A value outside its domain, or a combination that the host can never produce (section 4.2, "valid combinations"), MUST raise `ValueError`. Every row 1 to 9 MUST be reachable by a valid input. | MUST |
| R3 | `outcome.derive_inputs(decision, tiers)` MUST map the API decision (`single_match`, `clarify_match`, `no_match`) and the tiers (`answers`, `related`) of the kept candidates to `(search, relevance)`. A lone survivor of a pruned list MUST give row 6 (Confirm); a true single match that answers MUST give row 4 (Answer); candidates all dropped MUST give row 9. | MUST |
| R4 | `outcome.decide(...)` MUST return one of the seven outcomes with its row. A Handover MUST be returned for an explicit request for a person (reason 1) and for a Not covered result that is the second miss in a row (reason 2, row kept), at most once per session. Reasons 3 and 4 stay annotations and MUST NOT change the outcome. | MUST |
| R5 | `next_clarified` and `next_misses` MUST implement the counter rules of section 4.2. A rephrase MUST NOT clear `clarified`. | MUST |
| R6 | No code outside `outcome.py` MUST choose an outcome from a candidate count. Both interfaces MUST call `decide`. | MUST |
| R7 | Scope input: in the chat, an unsure triage MUST give row 2 (Clarify, kind scope). In the panel, an unscoped typed message MUST go through the shared `FAQ_Triage` with the model restricted to values 1 and 5, out of scope MUST give row 1, and `unsure` MUST be treated as in scope. A related-question click and a field-scoped message MUST skip triage. | MUST |
| R8 | The graph MUST stay one file with a chat part (existing ids unchanged) and a panel part (`Help_` ids): `Help_UserQuestion`, `Help_Retrieve` (Robot, same effect), `Help_RetrievalOk`, `Help_RetrievalFail`, `Help_RetrievalTimeout`, `Help_RetrievalUnavailable`. `Session_Chat` and `Session_Panel` MUST gate the two search inputs and `Session_Panel` MUST gate the selector, by conditions. | MUST |
| R9 | The shared core MUST exist once: `FAQ_Triage`, `FAQ_Scope`, `FAQ_OutOfScope`, `FAQ_NoMatch`, `FAQ_Goodbye`, `Help_Escalate`, `Help_Handover`, the table events and `TurnOutcome`. No panel copy of any of them. | MUST |
| R10 | The chat MUST NOT execute the selector or call `pick_followup`. The panel MUST fire a determination after it shows an answer, with the same selection logic, and MUST accept the applicant's reply. `FOLLOWUP_SURFACE` (default `panel`) selects the surface. | MUST |
| R11 | `Form0` relations and initial marking MUST be unchanged, no relation may run from the FAQ layer into `Form0`, and every event id of the graph before the split (including any event spec 02 adds) MUST still exist after it. | MUST |
| R12 | The host MUST feature-detect every new event. A graph without `Session_*`, `Help_Retrieve`, `TurnOutcome` or the gate events (graph 2014078) MUST behave as today. | MUST |
| R13 | The builder MUST generate the DMN from the same row data as `outcome.py`: four inputs whose labels equal the gate event ids, nine rules, `hitPolicy="FIRST"`, compiled `value` by the observed rule, `<definitions>` in step. | MUST |
| R14 | The compile generator MUST reproduce the compiled value of the two observed exports exactly. Table, definitions and compiled form MUST agree on every valid input. | MUST |
| R15 | A turn MUST evaluate the table once: `TurnStart` makes the four gate inputs pending, each input responds to `OutcomeTable`, milestones block it until all four are executed. The local simulator MUST show that `OutcomeTable` runs after the last input and not before. | MUST |
| R16 | `TurnOutcome` MUST be a choice event with exactly the seven outcome values. After it executes with any one value, exactly one outcome event MUST be pending: the one mapped in `OUTCOME_EVENT`. | MUST |
| R17 | `OUTCOME_MODE` MUST take `code` (default), `shadow`, `dcr`. `code`: the function decides, only `TurnOutcome` is written. `shadow`: the function decides, the DMN is also run and compared. `dcr`: the DMN result decides; the function is used only if the DMN is unreadable. On a mismatch the host MUST log it and, in `shadow`, keep the function's result. | MUST |
| R18 | When the graph has `TurnOutcome`, each question turn MUST execute it once, with the outcome as value and row, source and miss count in the comment. If not exactly one outcome event is pending afterwards, the host MUST fail closed to Not covered and log an error. | MUST |
| R19 | Confirm, Clarify, Offer, scope question and rephrase texts MUST be read from DCR events when the graph has them, and fall back to the current host strings (identical wording) otherwise. | MUST |
| R20 | The chat SHOULD render a Handover message; the panel SHOULD render the determination prompt. | SHOULD |
| R21 | The spec MUST contain a Portal import checklist, fixture requests and a fallback; the `--outcome code` build MUST omit the DMN machinery and work with `OUTCOME_MODE=code`. | MUST |
| R22 | No test in this spec MUST call a model. | MUST |

## 4. Design

### 4.1 Overview

```
typed message -> triage (shared FAQ_Triage) -> scope: in_scope | out_of_scope | unsure
   in_scope -> search (chat: FAQ_UserQuestion / panel: Help_UserQuestion) -> relevance tiers (spec 01)
   outcome.decide(scope, decision, tiers, clarified, misses, ...) -> Decision(outcome, row, ...)
   outcome_runtime.settle(...)  code: write TurnOutcome | shadow, dcr: also run the DMN in DCR
   DCR makes exactly one outcome event pending -> host renders it -> counters updated -> trace
```

A turn that is only a reply to a prompt or an end of conversation (triage 2 or 4) is not a question turn and does not go through the table; its `outcome` in the trace is null.

### 4.2 The outcome function

Inputs are four categorical values. The host computes them; the function and the DMN read only these.

| Input | Values | Meaning |
|---|---|---|
| `scope` | `in_scope`, `out_of_scope`, `unsure` | From triage: value 1, value 5, and the Decisions "unsure" flag (C12) |
| `search` | `none`, `single`, `list` | API decision `no_match`, `single_match`, `clarify_match` |
| `relevance` | `none`, `related`, `one_answers`, `several` | From the tiers of the kept candidates: no candidate kept; none answers and at least one is related; exactly one answers; two or more answer |
| `clarified` | `0`, `1` | A candidate Clarify was already shown for this question |

Valid combinations (a stage that did not run is passed as `none`): `scope` other than `in_scope` takes `none`, `none`. For `in_scope`: `search=none` only with `relevance=none`; `single` with `none`, `related`, `one_answers`; `list` with all four. Anything else raises `ValueError` in code (R2).

| Row | scope | search | relevance | clarified | Outcome | Note |
|---|---|---|---|---|---|---|
| 1 | out_of_scope | - | - | - | out_of_scope | |
| 2 | unsure | - | - | - | clarify | kind `scope`; does not set `clarified` |
| 3 | in_scope | none | none | - | not_covered | API found nothing |
| 4 | in_scope | single | one_answers | - | answer | true single match that answers |
| 5 | in_scope | - | related | - | offer | label `related`: nothing answers, same topic only |
| 6 | in_scope | list | one_answers | - | confirm | lone survivor of a pruned list |
| 7 | in_scope | list | several | 0 | clarify | kind `candidates`; sets `clarified` |
| 8 | in_scope | list | several | 1 | offer | label `may_fit`: the best offer, no second clarify |
| 9 | - | - | - | - | not_covered | candidates existed and all were dropped, or fail closed |

Differences from the roadmap table, both deliberate:
- Row 5 takes `-` in the Search column (roadmap: single match). A list in which nothing answers but something is related would otherwise match no row. The result is Offer labelled related, which is what spec 01 rule 6 does.
- Row 9 is all dashes (roadmap: in scope, any, none, any). After rows 1 to 8 the two are equal for every valid input; the dash row is also what the DMN export ends with (C20) and makes the table total. Row 9 is reached only when candidates existed and all were dropped (`single` or `list` with `none`).
- "Several answer or fit" (roadmap rows 7 and 8) is narrowed to two or more that answer. A list in which none answers is `related` (row 5).

Signatures (`dcrai/chat/outcome.py`, new, no I/O):

```python
SCOPES = ('in_scope', 'out_of_scope', 'unsure')
SEARCHES = ('none', 'single', 'list')
RELEVANCE = ('none', 'related', 'one_answers', 'several')
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

class Decision(NamedTuple):
    outcome: str            # one of OUTCOMES
    row: int | None         # 1..9; None only for an explicit request for a person
    table_outcome: str      # what the table said before the Handover rule (equals outcome otherwise)
    clarify_kind: str | None  # 'scope' (row 2), 'candidates' (row 7), else None
    label: str | None       # 'related' (row 5), 'may_fit' (row 8), else None
    handover_reason: int | None  # 1 asked for a person, 2 second miss; 3 and 4 are set by the caller
    inputs: tuple           # (scope, search, relevance, clarified) as sent to the table

def derive_inputs(decision, tiers) -> tuple[str, str]: ...   # (search, relevance)
def table(scope, search, relevance, clarified) -> tuple[int, str]: ...
def decide(scope, decision, tiers, clarified=0, misses=0, asked_person=False, handover_shown=False) -> Decision: ...
def shown_for(row, candidates) -> list: ...                   # which candidates the reply presents
def next_clarified(clarified, signal) -> int: ...
def next_misses(misses, signal) -> int: ...
```

`derive_inputs(decision, tiers)`, with A = tiers equal to `answers`, R = tiers equal to `related`:

| decision | tiers | search | relevance |
|---|---|---|---|
| `no_match` | empty | none | none |
| `no_match` | not empty | `ValueError` | |
| `single_match` | empty (dropped) | single | none |
| `single_match` | `[answers]` | single | one_answers |
| `single_match` | `[related]` | single | related |
| `clarify_match` | empty (all dropped) | list | none |
| `clarify_match` | A = 1 (R any) | list | one_answers |
| `clarify_match` | A >= 2 | list | several |
| `clarify_match` | A = 0, R >= 1 | list | related |

`decide`:
1. `asked_person` gives `Decision('handover', None, ...)` with reason 1. No search runs, no table row.
2. Otherwise `scope` other than `in_scope` skips `derive_inputs` (search and relevance `none`). `table` gives `(row, table_outcome)`.
3. If `table_outcome == 'not_covered'`, `misses + 1 >= MISSES_BEFORE_HANDOVER` and not `handover_shown`, the outcome is `handover`, reason 2, the row stays 3 or 9.
4. `clarify_kind`: `scope` for row 2, `candidates` for row 7. `label`: `related` for row 5, `may_fit` for row 8.

`shown_for(row, candidates)`: rows 4 and 6 give the one `answers` candidate; row 5 gives all candidates (all are `related`); rows 7 and 8 give `answers` first, then `related`; other rows give an empty list. This reproduces the `shown` of spec 01 section 4.3.

Counter rules. The caller passes a signal after every turn or reaction:

| Signal | `next_clarified` | `next_misses` |
|---|---|---|
| `clarify_candidates` (row 7 shown) | 1 | unchanged |
| `scope_question` (row 2 shown) | unchanged | unchanged |
| `answered`, `accepted`, `chose` | 0 | 0 |
| `not_covered` (row 3 or 9) | unchanged | +1 |
| `none_of_these`, `rejected` | unchanged | +1 |
| `handover` (reason 2 shown) | unchanged | 0 |
| `out_of_scope`, `end` | 0 | unchanged |
| `rephrase`, `offer`, `confirm_shown` | unchanged | unchanged |

Open decision Q4 covers whether a topic switch should clear `clarified`; the default above clears it only when a question is resolved.

### 4.3 Contract with spec 01

Spec 01 section 10 lists A4 and A5. This section confirms or corrects them and names the exact change spec 01 needs.

| Item | Spec 01 says | Spec 03 | Change in spec 01 |
|---|---|---|---|
| A4 outcome names | `answer`, `confirm`, `offer`, `clarify`, `not_covered`, `out_of_scope`, `handover` | Confirmed, same strings (`OUTCOMES`) | None |
| A4 row numbers | Roadmap rows 1 to 9 | Confirmed, with the two deviations of section 4.2 (row 5 search `-`, row 9 dashes) | None |
| Rule 3 (single, related) | `offer`, row 5 | Row 5 | None |
| Rule 2 (single, answers) | `answer`, row 4 | Row 4 | None |
| Rule 4 (list, one answers) | `confirm`, row 6 | Row 6 | None |
| Rule 1 (no candidates) | row 3 for `no_match`, else row 9 | Same: row 3 needs search `none`; row 9 is candidates all dropped | None |
| Rule 6 (list, zero answers, some related) | `offer`, row null | Row 5 | Section 4.3 rule 6 and the test `test_interim_outcome_rows`: expected row `5` instead of `None` |
| Rule 5 (list, two or more answers) | `clarify`, row null | Row 7 if `clarified=0`, row 8 (`offer`) if `clarified=1`. Spec 01 has no clarified flag, so its interim result stays until spec 03 replaces it | None |
| `same_faq` as a logged outcome | Section 4.2 (`application_runtime.py` same-FAQ rule): "Logged as outcome `same_faq`, row null" | `same_faq` is not one of the seven. It is a render flag on an `answer`, `confirm` or `offer` outcome | The same-FAQ branch calls `log_outcome` with the interim outcome and row, plus `same_faq=True`; the eval runner's verdict group `same_faq` is unaffected (it is an eval classification) |
| `via='example'` outcome `answer`, row null | Section 4.2 `ask_example` | Unchanged: an example click is a chosen FAQ, not a table evaluation | None |
| A5 inputs | The function takes the API decision and per-candidate tiers `answers`, `related` | Confirmed for `decide` and `derive_inputs`: they take exactly `state['last_search']['decision']` (`single_match`, `clarify_match`, `no_match`) and the list of candidate `tier` strings. The table itself takes four categorical values | None |
| Fail closed (R6) | Relevance down gives every candidate `related` | Gives search `single` or `list` with relevance `related`: row 5, Offer. No Answer is possible | None |
| `CONFIRM_LONE_SURVIVOR=0` | `interim_outcome` returns `answer` | The flag stays in the caller. When off and the outcome is `confirm`, the caller treats it as `answer` and logs `outcome='answer'`, `outcome_row=6` | `interim_outcome` and its flag test are deleted by spec 03 task T6a/T6b; until then no change |
| `state['last_search']` | Spec 01 writes `{'decision', 'retrieved'}` | Required: `decide` reads `decision` from it | None |
| Log events `faq_outcome`, `faq_reaction` | Fields `outcome`, `outcome_row`, `faq_ids`, `via` | Spec 03 adds `clarify_kind`, `label`, `handover_reason`, `same_faq`, `source` to `faq_outcome` (names are placeholders for spec 02) | None; spec 03 task T6a/T6b adds them |

What spec 03 replaces: `interim_outcome`, its two unit tests, and the branching in `ask()` (chat) and `ask()` (panel) that spec 01 task T4 adds. The rendering per outcome that spec 01 task T4 builds (Confirm prompt, Offer text, options turn) stays and is reused.

### 4.4 Contract with spec 02

Spec 02 owns the trace schema, the registry and the panel context record. Spec 03 does not define them. Assumptions:

| Id | Assumption | If wrong |
|---|---|---|
| A6 | The trace record has `outcome` and `outcome_row` (brief section 2). Spec 03 fills `outcome` with one of the seven names, or null for turns that are not question turns, and `outcome_row` with 1 to 9 or null | Rename in `log_outcome` only |
| A7 | Spec 02 (its A6) accepts an optional `outcome_inputs` object whose keys this spec defines: `scope`, `search`, `relevance`, `clarified`, `misses`. It also provides fields for `outcome_source` (`code`, `dcr`, `failclosed`), the DMN result in `shadow` mode (`outcome_dcr`, `outcome_row_dcr`), `handover_reason`, `clarify_kind`, `same_faq`. Names here are placeholders | Spec 03 tasks T6a and T6b adapt the keyword names |
| A8 | `interface` is `chat` or `panel`. Spec 03 reads it through one accessor, `interface_of(state)` in `retrieval_runtime.py` (`'panel'` if `'application_answers' in state`, else `'chat'`), until spec 02 sets one | Change the accessor body |
| A9 | The panel context record is added to the graph by a builder step of spec 02. Spec 03 adds no relation that has an event of that record as source or target, and keeps every event id present in the pre-split build (R11, test `test_split_keeps_every_event_id`) | The id-preservation test fails at the build |
| A10 | Spec 02 does not change the search event id constants in `retrieval_runtime.py` lines 36 to 37 | Resolve at the edit-order step (section 9.1) |
| A11 | Spec 02's registry can supply the text of the outcome message events to the builder. Until it does, the builder uses the constants in section 4.6, which equal today's host strings | None needed |

### 4.5 Code changes

New settings (env; spec 02 moves them into the registry): `OUTCOME_MODE` (`code` default, `shadow`, `dcr`), `FOLLOWUP_SURFACE` (`panel` default, `chat` restores today; works only on a graph without the `Session_Panel` condition), `PANEL_TRIAGE` (`1` default, `0` restores the unconditional `FAQ_Triage = 1`).

#### `dcrai/chat/outcome.py` (new)

The module of section 4.2: `ROWS`, `OUTCOME_EVENT`, `derive_inputs`, `table`, `decide`, `shown_for`, `next_clarified`, `next_misses`, `Decision`. No imports from the repo. `table` validates domains and valid combinations (R2) by looking up the tuple in a precomputed set of the 64 valid combinations of section 4.2 plus the non-`in_scope` scopes.

#### `dcrai/chat/outcome_runtime.py` (new, DCR I/O for the table)

| Item | Behaviour |
|---|---|
| `GATES = ('GateScope', 'GateSearch', 'GateRelevance', 'GateClarified')` | Table input events, in DMN order |
| `settle(state, payload, decision, interface)` returns `Settled(decision, source, event_id, text, mismatch)` | 1. If `TurnOutcome` is not in `payload`, return the decision unchanged, source `code` (R12). 2. In `shadow` and `dcr`, and only if `OutcomeTable` exists and `decision.row` is not None: execute `TurnStart`, then the four gates with the string forms of `decision.inputs`, refresh, read `TurnResult.value` (fall back to `OutcomeTable.value`), parse with `parse_result`. 3. `dcr` with a readable result and `table_outcome` equal to the parsed outcome uses it as is; `dcr` with a different readable result uses the DMN's `(row, outcome)` and applies the Handover rule to it; `dcr` with no readable result falls back to the code decision, source `code`. `shadow` and `code` always keep the code decision. 4. `mismatch` is true when a readable DMN result differs from `(row, table_outcome)`. 5. Execute `TurnOutcome` with `decision.outcome` and comment `row N; source S; misses M`. 6. Refresh and collect pending events of `OUTCOME_EVENT.values()`. If the pending set is not exactly `{OUTCOME_EVENT[outcome]}`, return Not covered, source `failclosed`, and log an error. Before step 2, if the `TurnOutcome` dictionary is not exactly the seven `OUTCOMES`, treat the event as absent and log an error (same refusal as the `FAQ_Triage` dictionary check, C3). |
| `parse_result(value)` | `'result 6:confirm'` gives `(6, 'confirm')`; anything else gives `None` |
| `outcome_text(payload, row, shown_count)` | Description of the text event for the row (table in 4.6), or `None` if the graph lacks it |
| `acknowledge(state, event_id)` | Executes the outcome event so it is no longer pending |
| `handover(state, reason, signal)` | The part of the panel's `escalate` that executes `Help_Escalate`, reads and acknowledges `Help_Handover` and returns `{reason, html}`; the panel's `escalate` calls it and keeps its marking check and once-per-session rule |
| `PERSON`, `URGENT` | The two regexes moved from `application_runtime.py:508-511` so the chat can use them |

#### `dcrai/chat/retrieval_runtime.py` (edit, named functions only)

| Item | Old | New |
|---|---|---|
| line 36 `INPUT, OK, UNAVAILABLE` | chat ids only | Keep. Add `SEARCH_EVENTS = {'chat': ('FAQ_UserQuestion', 'FAQ_RetrievalOk', 'FAQ_RetrievalUnavailable'), 'panel': ('Help_UserQuestion', 'Help_RetrievalOk', 'Help_RetrievalUnavailable')}` and `interface_of(state)` (A8). The unnamed `INPUT` stays for old callers |
| `initialize` (155) | no session event | If `Session_Chat` is in the payload and enabled, execute it once. Initialise `state['outcome'] = {'clarified': 0, 'misses': 0, 'handover_shown': False}` |
| `search` (171) | uses `INPUT`, `OK`, `UNAVAILABLE`; executes `FAQ_NoMatch` through `show_label` when nothing is kept (215) | Looks the ids up in `SEARCH_EVENTS[interface_of(state)]` for the panel; for the chat unchanged. When the payload has `TurnOutcome`, reads the `FAQNoMatch` text without executing it (the acknowledgement happens after `settle`). Signature unchanged |
| `ask` (220) | after spec 01 task T4: `interim_outcome(...)` and a branch per outcome | `decision = outcome.decide('in_scope', last_search['decision'], tiers, clarified, misses, handover_shown=...)`; `settled = outcome_runtime.settle(...)`; render by `settled.decision.outcome` using the existing spec 01 renderers; texts through `outcome_text`. Applies the `CONFIRM_LONE_SURVIVOR` mapping of section 4.3. Updates counters with `next_*`. Logs through spec 01's `log_outcome` |
| `route` (410) and `scope_check` (466) | unsure gives a `scope_check` prompt | Unsure now produces `decide('unsure', ...)`, settled, rendered with the `FAQ_Msg_ScopeQuestion` text (fallback: line 467 string). The prompt kind `scope_check` and `SCOPE_CHECK` (389) stay |
| `follow_dcr` (443) | shows and acknowledges pending message events | For an `out_of_scope` message, call `decide('out_of_scope', None, [])` and `settle` before acknowledging, so `FAQ_OutOfScope` is acknowledged once |
| `show_answer` (280) | lines 295-315 execute the selector | Wrapped in `if FOLLOWUP_SURFACE() == 'chat'`; default skips it, including the `pick_followup` model call (R10) |
| `reply_to_prompt` (350) | `options`, `determination`, `scope_check` | Adds the counter updates for reactions (`next_misses` for `none`; `next_clarified` and `next_misses` for a chosen id). On `none` after a Confirm or Offer with misses at the limit, returns the handover (chat gets reasons 1 and 2) |
| `handle` (475) | | Chat messages that match `PERSON` and have no prompt on screen produce `decide(asked_person=True)` and the handover reply |

#### `dcrai/application/application_runtime.py` (edit, named functions only)

| Item | Old | New |
|---|---|---|
| `start` (200), branch at 229-233 | no session event | If `Session_Panel` is in the payload and enabled, execute it. Initialise `state['outcome']` as in the chat |
| `ask` (582), triage block 674-678 and 689-694 | executes `FAQ_Triage = 1` itself; uses `rr.INPUT` | Search event ids from `rr.SEARCH_EVENTS['panel']`. For an unscoped typed message (no `related`, no `scope='field'`) and `PANEL_TRIAGE=1`: classify with `rr.classify('triage', ...)` on the event's description with the values limited to `1` and `5`, execute `FAQ_Triage` with the result (model down: `1`). Value 5 returns `status='faq_out_of_scope'` with the `FAQ_OutOfScope` text after `decide('out_of_scope')` and `settle`. `unsure` is ignored. Other messages execute `FAQ_Triage = 1` as today |
| `ask`, outcome branch 741-756 | after spec 01 task T4: `interim_outcome` | `decide` and `settle` as in the chat; `PERSON` match calls `decide(asked_person=True)` |
| `_miss` (557), `confirm` (758) | counter in `state['help_misses']` | Counter in `state['outcome']['misses']` through `next_misses`; `MISSES_BEFORE_HANDOVER` imported from `outcome`; `escalate` stays |
| `_show` (563) | does not fire a determination | After `FAQ_Answered`, select and execute a follow-up with the same logic as chat `show_answer` lines 295-315 (shared function `rr.open_followup(state, payload, found, message)` extracted from the chat; chat no longer calls it). The result carries `prompt = {id, kind: 'determination', text, options}` |
| new `determination(state, data)` and `POST /application/determination` in `install` (775) | none | Calls `rr.answer_determination` and returns the outcomes; `_unchanged` check afterwards |
| `escalate` (528) | | Calls `outcome_runtime.handover`; keeps the `application_marking` check and the once-per-session rule |

`app.py` is not edited by spec 03. `dcrai/llm/retrieval_llm.py` is not edited: `triage_decisions` already takes a values list (`retrieval_llm.py:231`), and the panel passes two.

#### UI (task T8)

| File | Change |
|---|---|
| `demo-ui/src/SupportChat.jsx` | Render `handover: {reason, html}` on a reply as an amber block, as the panel does |
| `demo-ui/src/ApplicationDemo.jsx` | Treat `faq_out_of_scope` like `faq_no_match`; render `prompt.kind === 'determination'` with its options and post to `/application/determination` |
| `demo-ui/preview/preview.mjs`, `static/demo/` | Add the mocks; rebuild; keep the bundle files `index.html` references |

### 4.6 Graph XML changes

The graph stays one file (decision record 4.9, ADR-2). Builder steps are functions in a new `tools/clean_graph/split_steps.py`, called from `build_clean_graph.py` after the handover block (line 378) and before the unused-expression sweep (line 383). Labels below are plain English and unique (`add_event` asserts, line 152). "Observed" means the shape is used in this repository's graph or an export; "Unverified" is stated per construct in 4.7.

#### New events

| Id | Type | Role | Content | Initial marking | Step | Build |
|---|---|---|---|---|---|---|
| `Session_Chat` | label | Chatbot | Executed by the chat host when the chat opens. Group `Session` | included | S1 | both |
| `Session_Panel` | label | Chatbot | Executed by the application host at start. Group `Session` | included | S1 | both |
| `Help_UserQuestion` | text | Chatbot | The panel's typed question. Group `HelpRetrieval` | excluded | S2 | both |
| `Help_Retrieve` | text | Robot | Effect `handicap-faq-v2`, `q` = `Help_UserQuestion`, quoted continuations `"Help_RetrievalOk"`, `"Help_RetrievalFail"`, `"Help_RetrievalTimeout"`. Group `HelpRetrieval` | included | S2 | both (effect stripped in NoEffect) |
| `Help_RetrievalOk` | text | System | Receives the service JSON | included | S2 | both |
| `Help_RetrievalFail`, `Help_RetrievalTimeout` | label | System | Continuations | included | S2 | both |
| `Help_RetrievalUnavailable` | label | Chatbot | Same text as `FAQ_RetrievalUnavailable`. Group `HelpRetrieval` only, never `FAQAnswer` (the determination result collector reads that group, `retrieval_runtime.py:336`) | included | S2 | both |
| `TurnOutcome` | choice (string) | Chatbot | Values `answer`, `confirm`, `offer`, `clarify`, `not_covered`, `out_of_scope`, `handover`. Group `Outcome` | included | S3 | both |
| `Outcome_Answer`, `Outcome_Confirm`, `Outcome_Offer`, `Outcome_Clarify` | label | Chatbot | Texts in the table below. Groups `Outcome:answer` and so on | included | S4 | both |
| `FAQ_Msg_OfferOne`, `FAQ_Msg_ScopeQuestion`, `FAQ_Msg_Rephrase` | label | Chatbot | Text only, no relations. Group `Msg` | included | S4 | both |
| `TurnStart` | label | Chatbot | Executed at the start of each DMN evaluation. Group `Gate` | included | S3 | dmn |
| `GateScope` | choice (string) | Chatbot | `in_scope`, `out_of_scope`, `unsure`. Group `Gate` | included | S3 | dmn |
| `GateSearch` | choice (string) | Chatbot | `none`, `single`, `list` | included | S3 | dmn |
| `GateRelevance` | choice (string) | Chatbot | `none`, `related`, `one_answers`, `several` | included | S3 | dmn |
| `GateClarified` | choice (int) | Chatbot | `0` No, `1` Yes | included | S3 | dmn |
| `OutcomeTable` | none | Robot | `computation="OutcomeTable-computation"`, no eventData (as the export) | included | S3 | dmn |
| `TurnResult` | label | Chatbot | Receives `"result " + OutcomeTable` | included | S3 | dmn |

Event ids that feed the DMN are alphanumeric (`GateScope`, not `Gate_Scope`): every observed DMN input label is alphanumeric (C20, C21); an underscore in a label is Unverified.

Existing events that change: `FAQ_NoMatch`, `FAQ_OutOfScope`, `Help_Handover` gain a group `Outcome:not_covered`, `Outcome:out_of_scope`, `Outcome:handover`. Nothing else is renamed or removed (R11).

#### Outcome texts (builder constants; spec 02's registry replaces the source later)

| Outcome / row | Event read for the text | Text (equals today's host string, or spec 01's WD2 proposal) |
|---|---|---|
| 3, 9 not_covered | `FAQ_NoMatch` (existing) | existing description |
| 1 out_of_scope | `FAQ_OutOfScope` (existing) | existing description |
| handover | `Help_Handover` (existing) | existing description |
| 4 answer | `Outcome_Answer` | none (the FAQ answer is the content) |
| 6 confirm | `Outcome_Confirm` | Is this what you are asking? |
| 7, 8 clarify, offer | `Outcome_Clarify` | I found a few questions that may fit. Which one is closest? |
| 5 offer, one candidate | `FAQ_Msg_OfferOne` | WD2 one-FAQ text of spec 01 section 4.5 |
| 5 offer, several | `Outcome_Offer` | WD2 several text of spec 01 section 4.5 |
| 2 scope question | `FAQ_Msg_ScopeQuestion` | Is your question about handicaptillæg, the SU disability supplement? |
| rephrase after "No" | `FAQ_Msg_Rephrase` | Could you rephrase your question? A few more words about your situation help. |

Row 8 reads the text of `Outcome_Clarify` although `Outcome_Offer` is the pending event, because "no FAQ answers exactly this" is wrong for row 8. This wording is open (Q2).

#### New relations

All guards are on the source event's own value, in the same pattern as the `FAQ_Triage` guards at `build_clean_graph.py:327-329`.

| Relation | Source to target | Guard | Build |
|---|---|---|---|
| condition | `Session_Chat` to `FAQ_UserQuestion` | none | both |
| condition | `Session_Panel` to `Help_UserQuestion` | none | both |
| condition | `Session_Panel` to `FAQ_DeterminationSelector` | none | both |
| include | `FAQ_Triage` to `Help_UserQuestion` | `FAQ_Triage = 1` | both |
| exclude | `FAQ_Triage` to `Help_UserQuestion` | `FAQ_Triage != 1` | both |
| response | `Help_UserQuestion` to `Help_Retrieve` | none | both |
| response | `Help_RetrievalFail`, `Help_RetrievalTimeout` to `Help_RetrievalUnavailable` | none | both |
| response (7) | `TurnOutcome` to `OUTCOME_EVENT[x]` | `TurnOutcome = "x"` | both |
| coresponse (7) | `TurnOutcome` to `OUTCOME_EVENT[x]` | `TurnOutcome != "x"` | both |
| response (4) | `TurnStart` to each gate | none | dmn |
| condition, milestone, response (4 each) | each gate to `OutcomeTable` | none; condition and milestone share a `link` as in the export | dmn |
| condition, milestone | `OutcomeTable` to `TurnResult` | none, same `link` | dmn |
| update | `OutcomeTable` to `TurnResult` | value expression `"result " + OutcomeTable` (id `OutcomeTable-path-TurnResult--update--value`) | dmn |

Effect on the invariant "exactly one outcome event pending": for each value, one response fires and six co-responses fire, so the other six are not pending even if a previous turn left one unacknowledged (R16, simulator test).

#### Builder edits (named places in `tools/clean_graph/build_clean_graph.py`)

| Place | Edit |
|---|---|
| line 36-41 argument parsing | Add `--outcome {code,dmn}` (default `dmn`; `code` omits the dmn-only events and relations) |
| `event_data` (118) | New kind `strchoice` (choice, `format="string"`, dictionary of `(label, value)`) |
| `add_event` (149) | New parameter `computation=None`, written as the `computation` attribute of the event |
| `relation` (192) | New kinds `milestone`, `update`; optional `link` and `value_expression_id`; `plural` (198) gains `milestones`, `updates` |
| new `add_dmn_expr(id, rows, names)` | Writes the DMN expression with `<definitions>` (section 4.7) |
| lines 398-401 group list | Add `Session`, `HelpRetrieval`, `Gate`, `Outcome`, `Msg`, the `Outcome:<name>` groups |
| line 408 `ask_ids` | Add `Help_UserQuestion` (starts excluded) |
| lines 446-458 | Strip the effect from both `FAQ_Retrieve` and `Help_Retrieve` in the NoEffect variant (loop over the two) |
| `custom/graphDocumentation` (417) | Mention the split and the table |

### 4.7 The DMN in the graph

#### What is built

One decision table in the expression `OutcomeTable-computation`: `type="DMN"`, `hitPolicy="FIRST"`, four inputs (labels `GateScope`, `GateSearch`, `GateRelevance`, `GateClarified`, with `typeRef` `string`, `string`, `string`, `integer` and empty `<text/>`), one output (`label="OutcomeTable"`, `typeRef="string"`), nine rules. Each output entry is `"<row>:<outcome>"`, for example `"6:confirm"`, so one string carries the row and the outcome (several outputs are Unverified). Rule descriptions hold the row number and the roadmap wording. Entries are `"string"` literals, integer literals `0` and `1`, or `-`.

#### Generator (`tools/clean_graph/dmn_table.py`, new)

The compile rule of the observed exports: each rule becomes `( If( COND ) THEN ( "out" ) ELSE ( NEXT ) )`; `COND` is a right-nested `AND` chain of per-input tests, `-` is `true`, a literal is `(Name = literal)`, `>=N` is `((Name = N) OR (Name > N))`; the chain ends in `null`. This code reproduced the compiled `value` of `DMN-computation` and `CloseContact-computation` exactly (C22) and is the oracle for R13 and R14:

```python
def lit(v):
    return str(v) if isinstance(v, int) else '"%s"' % v

def test_expr(name, entry):
    if entry is None:
        return 'true'
    if isinstance(entry, str) and entry.startswith('>='):
        return '((%s = %s) OR (%s > %s))' % (name, entry[2:], name, entry[2:])
    return '(%s = %s)' % (name, lit(entry))

def cond_expr(names, entries):
    parts = [test_expr(n, e) for n, e in zip(names, entries)]
    s = parts[-1]
    for p in reversed(parts[:-1]):
        s = '(%s AND %s)' % (p, s)
    return s

def compile_table(names, rows):          # rows: [(entries, output string)]
    def go(i):
        if i == len(rows):
            return 'null'
        entries, out = rows[i]
        return '( If( %s ) THEN ( "%s" ) ELSE ( %s ) )' % (cond_expr(names, entries), out, go(i + 1))
    return go(0)
```

Called with the four names and `[(cond, '%d:%s' % (row, outcome)) for row, cond, outcome in outcome.ROWS]` it gives this value (1136 characters; quotes become `&quot;` in the XML attribute):

```
( If( ((GateScope = "out_of_scope") AND (true AND (true AND true))) ) THEN ( "1:out_of_scope" ) ELSE ( ( If( ((GateScope = "unsure") AND (true AND (true AND true))) ) THEN ( "2:clarify" ) ELSE ( ( If( ((GateScope = "in_scope") AND ((GateSearch = "none") AND ((GateRelevance = "none") AND true))) ) THEN ( "3:not_covered" ) ELSE ( ( If( ((GateScope = "in_scope") AND ((GateSearch = "single") AND ((GateRelevance = "one_answers") AND true))) ) THEN ( "4:answer" ) ELSE ( ( If( ((GateScope = "in_scope") AND (true AND ((GateRelevance = "related") AND true))) ) THEN ( "5:offer" ) ELSE ( ( If( ((GateScope = "in_scope") AND ((GateSearch = "list") AND ((GateRelevance = "one_answers") AND true))) ) THEN ( "6:confirm" ) ELSE ( ( If( ((GateScope = "in_scope") AND ((GateSearch = "list") AND ((GateRelevance = "several") AND (GateClarified = 0)))) ) THEN ( "7:clarify" ) ELSE ( ( If( ((GateScope = "in_scope") AND ((GateSearch = "list") AND ((GateRelevance = "several") AND (GateClarified = 1)))) ) THEN ( "8:offer" ) ELSE ( ( If( (true AND (true AND (true AND true))) ) THEN ( "9:not_covered" ) ELSE ( null ) ) ) ) ) ) ) ) ) ) ) ) ) ) ) ) ) )
```

`dmn_table.py` also holds `definitions_xml(names, types, rows)` (writes the `<definitions>` element) and `evaluate_compiled(text, env)` (a small recursive evaluator for exactly this grammar, used by the tests and by the simulator).

Definitions skeleton (shape copied from the DMN chatbot export; rules 1, 7 and 9 shown):

```xml
<expression id="OutcomeTable-computation" value="( If( ... ) )" type="DMN">
  <definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/" xmlns:biodi="http://bpmn.io/schema/dmn/biodi/2.0"
               id="definitions_outcome" name="definitions" namespace="http://camunda.org/schema/1.0/dmn"
               exporter="dmn-js (https://demo.bpmn.io/dmn)" exporterVersion="11.0.1">
    <decision id="decision_outcome" name="">
      <decisionTable id="decisionTable_outcome" hitPolicy="FIRST">
        <input id="input_scope" label="GateScope" biodi:width="150">
          <inputExpression id="expr_scope" typeRef="string"><text/></inputExpression></input>
        <input id="input_search" label="GateSearch" biodi:width="150">
          <inputExpression id="expr_search" typeRef="string"><text/></inputExpression></input>
        <input id="input_relevance" label="GateRelevance" biodi:width="150">
          <inputExpression id="expr_relevance" typeRef="string"><text/></inputExpression></input>
        <input id="input_clarified" label="GateClarified" biodi:width="150">
          <inputExpression id="expr_clarified" typeRef="integer"><text/></inputExpression></input>
        <output id="output_outcome" label="OutcomeTable" name="" typeRef="string" biodi:width="150"/>
        <rule id="rule_1"><description>Row 1: out of scope</description>
          <inputEntry id="r1_scope"><text>"out_of_scope"</text></inputEntry>
          <inputEntry id="r1_search"><text>-</text></inputEntry>
          <inputEntry id="r1_relevance"><text>-</text></inputEntry>
          <inputEntry id="r1_clarified"><text>-</text></inputEntry>
          <outputEntry id="r1_out"><text>"1:out_of_scope"</text></outputEntry></rule>
        <!-- rules 2 to 6 -->
        <rule id="rule_7"><description>Row 7: several answer, not yet clarified</description>
          <inputEntry id="r7_scope"><text>"in_scope"</text></inputEntry>
          <inputEntry id="r7_search"><text>"list"</text></inputEntry>
          <inputEntry id="r7_relevance"><text>"several"</text></inputEntry>
          <inputEntry id="r7_clarified"><text>0</text></inputEntry>
          <outputEntry id="r7_out"><text>"7:clarify"</text></outputEntry></rule>
        <!-- rule 8 -->
        <rule id="rule_9"><description>Row 9: nothing usable left, or fail closed</description>
          <inputEntry id="r9_scope"><text>-</text></inputEntry> <!-- three more dashes -->
          <outputEntry id="r9_out"><text>"9:not_covered"</text></outputEntry></rule>
      </decisionTable>
    </decision>
  </definitions>
</expression>
```

Wiring (shape of the DMN chatbot export, lines 90 and 319-336, with four inputs):

```xml
<event id="OutcomeTable" computation="OutcomeTable-computation"> ... <roles><role>Robot</role></roles> ... <eventData/> ... </event>
<conditions>
  <condition sourceId="GateScope" targetId="OutcomeTable" filterLevel="1" description="" time="" groups="" link="GateScope--condition--OutcomeTable"/>
  <!-- GateSearch, GateRelevance, GateClarified likewise; and OutcomeTable to TurnResult -->
</conditions>
<responses>
  <response sourceId="GateScope" targetId="OutcomeTable" filterLevel="1" description="" time="" groups=""/>
  <response sourceId="TurnStart" targetId="GateScope" filterLevel="1" description="" time="" groups=""/>
  <!-- the other three gates likewise -->
</responses>
<milestones>
  <milestone sourceId="GateScope" targetId="OutcomeTable" filterLevel="1" description="" time="" groups="" link="GateScope--condition--OutcomeTable"/>
</milestones>
<updates>
  <update sourceId="OutcomeTable" targetId="TurnResult" filterLevel="1" description="" time="" groups=""
          valueExpressionId="OutcomeTable-path-TurnResult--update--value"/>
</updates>
<expression id="OutcomeTable-path-TurnResult--update--value" value="&quot;result &quot; + OutcomeTable"/>
```

Per turn: the host executes `TurnStart`, which makes the four gates pending. Each gate execution responds to `OutcomeTable`, which is therefore pending after the first gate, but the milestones from the gates (still pending) block it. When the last gate executes, no milestone blocks, and the Robot runs in the same cycle (Documented: Robot phase of the execution cycle). The repeat of this pattern from turn to turn (re-pending the inputs, Robot re-executing when pending again) is Documented but Unverified in an export (fixture F4).

#### Two routes for the result

| | Route A: inside the observed shape (built) | Route B: needs a Portal fixture (not built) |
|---|---|---|
| How DCR's table result reaches the relations | The Robot writes a string to the label `TurnResult` (update relation, Observed). The host reads it and executes `TurnOutcome` with the outcome (choice event with guards, Observed pattern). Relations key on `TurnOutcome` | Relations whose source is `OutcomeTable` with a guard on its value, for example `OutcomeTable = "6:confirm"`, make the outcome event pending directly. No host copy and no `TurnOutcome` |
| What DCR enforces | That exactly one outcome event is pending for the outcome the host wrote. Whether the host copied the DMN result faithfully is checked by the host (modes) and shown in the trace | That the pending event is the DMN's, not the host's |
| Evidence | Update to a label on a Robot DMN: Observed (C20). Guard on a string choice value: Observed (`FAQ_Triage`, `Det*`). Reading the label's value over REST: Unverified (F1) | Guard on a DMN string output: Observed on a computed subprocess (C21). On a Robot event: Unverified (F2) |
| Fixture | F1, F4 | F2 (and F1) |
| Cost of switching later | | Builder adds relations from `OutcomeTable` with guards on the nine output strings (Offer needs `"5:offer" or "8:offer"`, Not covered `"3:not_covered" or "9:not_covered"`), drops `TurnOutcome`; host drops the copy step. About one builder function and one branch in `settle` |

#### Construct register

| Construct | Label | Source |
|---|---|---|
| Robot with `computation` and a DMN expression, responses from inputs, condition and milestone with the same `link` | Observed | C20 |
| `hitPolicy="FIRST"`, string and integer inputs, string output, last rule all dashes | Observed | C20 |
| Integer entries `0`, `1` and string entries on the same table | Observed | C21 (integers), C20 (strings) |
| Right-nested compile for 2, 3 and 5 inputs; the same rule applied to 4 inputs | Observed for 2, 3, 5; Unverified for exactly 4 | C20, C21, C22 |
| Nine rules | Unverified count (seven in C20, five in C21); no reason to differ | C20, C21 |
| Update to a label with `"text " + RobotEvent` | Observed | C20 |
| Input labels alphanumeric and equal to event ids | Observed | C20, C21 |
| Underscore in a DMN input label | Unverified, avoided | |
| Output string with a colon and digits (`"6:confirm"`) | Unverified (a plain string literal; the export has a period and spaces) | F2 |
| Reading `TurnResult` or `OutcomeTable` `value` in the REST event list | Unverified | F1 |
| Robot DMN executing again each time it becomes pending, with `TurnStart` re-pending its inputs | Documented (brief section 4) and Unverified in an export | F4 |
| Guard on a Robot DMN event's output | Unverified (Observed on a computed subprocess) | F2 |
| Guards on `TurnOutcome` values, responses and co-responses, include/exclude on `FAQ_Triage` | Observed | `build_clean_graph.py:261-269,327-333` |
| Label events executed by the host | Observed | `build_clean_graph.py:295-305` |
| Conditions from a session label to an input or selector | Observed relation, new use | |
| Second Robot carrying the same effect with different continuation ids | Unverified (the shape is the observed one, a second instance is not) | F5 |
| Hit policy ALL, comparison operators other than `=` and `>=`, ranges, several outputs, integer output used in a guard, FEEL context, Robot:Prime and Robot:Terminator, spawns, response deadlines | Not used | |

Range entries do occur in the Corona export (C21), contrary to the brief's list of unverified items. This spec does not need them.

### 4.8 Data and schema

`Decision` for a lone survivor in the panel, clarified flag 0, no misses:

```
Decision(outcome='confirm', row=6, table_outcome='confirm', clarify_kind=None, label=None,
         handover_reason=None, inputs=('in_scope', 'list', 'one_answers', 0))
```

DCR events executed for that turn in `dcr` mode (value, comment):

```
TurnStart ''                       GateScope 'in_scope'     GateSearch 'list'
GateRelevance 'one_answers'        GateClarified '0'
TurnOutcome 'confirm'  comment 'row 6; source dcr; misses 0'
Outcome_Confirm (pending) -> acknowledged by the host after rendering
```

`TurnResult` value after the Robot ran: `result 6:confirm`.

Second-miss handover (Not covered, `misses=1` before the turn): `Decision(outcome='handover', row=3, table_outcome='not_covered', handover_reason=2, ...)`, `TurnOutcome 'handover'`, `Help_Handover` pending, the reply carries the `FAQ_NoMatch` text and the handover block.

Session state, both interfaces: `state['outcome'] = {'clarified': 0, 'misses': 0, 'handover_shown': False}` (lost on restart, as `help_misses` is today; spec 02's context record may take it over).

Trace fields spec 03 needs populated per question turn (names are placeholders, A7): `outcome`, `outcome_row`, `outcome_inputs`, `outcome_source`, `outcome_dcr`, `outcome_row_dcr`, `clarify_kind`, `label`, `handover_reason`, `same_faq`.

### 4.9 Decision records

#### ADR-1: Where the outcome table runs

| Option | Assessment |
|---|---|
| A. Code only, DCR is told the result | Lowest risk and effort. DCR still admits the result and the log shows it, but the table is not visible or editable in the Portal |
| B. DMN authoritative from the first release | Matches the roadmap ("computation event holds the table"). Depends on constructs no export shows (F1, F2, F4); a Portal quirk breaks every turn |
| C. Code first, DMN in shadow, then DMN authoritative (chosen) | The function is the test oracle and the fallback; the DMN is checked against it on real turns before it decides. Costs the code and the DMN being maintained together and, in `shadow`, seven extra DCR calls per turn |

Decision: C. `OUTCOME_MODE` default `code`. The row data is one tuple in `outcome.py`, so the DMN cannot drift (R13, R14). Consequences: easier, the Portal import can fail without affecting users; harder, the extra calls add latency in `shadow` and `dcr` (the budget is Q6). Revisit when F1 to F4 are answered: if Route B works, drop `TurnOutcome` copying.

#### ADR-2: One graph file or two

| Option | Assessment |
|---|---|
| A. One file, two simulations, session events gate the two parts (chosen) | One revision id and one import; shared events are single by construction (R9); wording changes reach both. The chat simulation carries unused panel events and `Form0`, as it already does |
| B. Two files generated by the builder from shared steps | Each simulation is smaller. Relations cannot cross files (spawns are Unverified), so the shared core would be duplicated and two graph ids, two imports and two revision ids would have to be kept in step |

Decision: A. Isolation between the two interfaces rests on the conditions on `Session_*` and on separate simulations, not on separate files. Revisit if the chat graph needs to be published without the application.

## 5. Test plan

No test calls a model. Unit tests use the existing fakes (`FakeDCR`, patched `llm` functions) in `tests/test_retrieval_runtime.py` and `tests/test_application_faq.py`. Graph tests run on the built graph and are skipped when `xml graphs/` or `tools/` is absent (both are gitignored). Levels: pure unit (T1), generator and DMN parity (T2, T4), local relation simulation (T3, T4), host integration with fakes (T5 to T7), manual UI (T8), manual Portal (T10).

### 5.1 `tests/test_outcome.py` (new, T1)

| Req | Test | Input | Expected |
|---|---|---|---|
| R1 | `test_table_nine_rows` (one subTest per row) | row 1 `('out_of_scope','none','none',0)`; 2 `('unsure','none','none',0)`; 3 `('in_scope','none','none',1)`; 4 `('in_scope','single','one_answers',0)`; 5 `('in_scope','single','related',0)` and `('in_scope','list','related',1)`; 6 `('in_scope','list','one_answers',1)`; 7 `('in_scope','list','several',0)`; 8 `('in_scope','list','several',1)`; 9 `('in_scope','list','none',0)` and `('in_scope','single','none',1)` | `(1,'out_of_scope')`, `(2,'clarify')`, `(3,'not_covered')`, `(4,'answer')`, `(5,'offer')`, `(6,'confirm')`, `(7,'clarify')`, `(8,'offer')`, `(9,'not_covered')` |
| R1 | `test_first_match_wins` | `('out_of_scope','list','several',1)`; `('in_scope','list','related',0)`; `('in_scope','list','one_answers',1)` | rows 1, 5, 6 (not 9, 7, 8) |
| R2 | `test_every_row_reachable_and_valid_count` | all 3x3x4x2 combinations, keep those that do not raise | exactly 64 valid; rows {1..9} all occur |
| R2 | `test_invalid_values_and_combinations_raise` | `('in_scope','none','related',0)`, `('in_scope','single','several',0)`, `('in_scope','none','one_answers',0)`, `('in_scope','none','several',0)`, `('maybe','none','none',0)` | `ValueError` |
| R3 | `test_derive_inputs_matrix` | the nine-line table of 4.2 | each pair as listed; `no_match` with candidates raises |
| R3 | `test_derive_inputs_never_invalid` | every decision with every tier list of length 0 to 3 (skipping the one raising case) | the pair is a valid combination for scope `in_scope` |
| R3 | `test_lone_survivor_is_confirm_true_single_is_answer` | `('clarify_match',['answers'])`, `('clarify_match',['answers','related'])`, `('single_match',['answers'])` | rows 6, 6, 4 |
| R4 | `test_decide_handover_rules` | asked person; `not_covered` with `misses` 0 and 1; same with `handover_shown=True`; `out_of_scope` with `misses=5` | handover reason 1 row None; not_covered then handover reason 2 with row 3 and `table_outcome='not_covered'`; not_covered; out_of_scope |
| R4 | `test_decide_row_9_also_hands_over` | `('clarify_match',[])`, `misses=1` | handover, row 9 |
| R4 | `test_decide_clarify_kind_and_label` | rows 2, 7, 5, 8 | `scope`, `candidates`, `related`, `may_fit` |
| R4 | `test_shown_for` | spec 01 4.3 cases | row 4 and 6 the answers one; row 5 all; rows 7, 8 answers first then related; others empty |
| R5 | `test_counter_rules` (subTest per signal row of 4.2) | each signal from a start value 1 | as the table; `rephrase` leaves `clarified` at 1 |
| R6 | `test_no_candidate_count_branch_in_runtimes` | read `retrieval_runtime.py` and `application_runtime.py` | no match of `len\(found\)\s*==\s*1` and no `interim_outcome` |
| R6 | `test_outcome_module_has_no_io` | source of `outcome.py` | imports only `typing` and `collections` |
| R16 | `test_outcome_event_map_covers_outcomes` | `OUTCOME_EVENT` | keys equal `OUTCOMES`; values distinct |

### 5.2 `tests/test_outcome_table_graph.py` (new, T2 and T4)

| Req | Test | Input | Expected |
|---|---|---|---|
| R14 | `test_generator_reproduces_dmn_chatbot_export` | parse `DMN chatbot - english.xml`, rebuild names and rows, `compile_table` | equals the export's `DMN-computation` value (skipped if the file is missing) |
| R14 | `test_generator_reproduces_corona_closecontact` | same for `CloseContact-computation` in `Corona - ChatBot SOP.xml` | equal |
| R14 | `test_compiled_matches_table_on_all_valid_inputs` | 64 valid combinations through `evaluate_compiled` | result equals `"%d:%s"` of `outcome.table` for each |
| R13, R14 | `test_definitions_match_table` | `definitions_xml(...)` parsed; first-match evaluation of the rules in the XML | equals `outcome.table` on 64 combinations |
| R13 | `test_definitions_shape` | the generated element | 4 inputs with labels `GateScope`, `GateSearch`, `GateRelevance`, `GateClarified`; typeRefs `string`, `string`, `string`, `integer`; 9 rules; `hitPolicy="FIRST"`; last rule all dashes; every output is `<row>:<outcome>` with row 1 to 9 and the outcome one of the six table outcomes (the table never outputs `handover`) |
| R13 | `test_built_graph_dmn_is_in_step` | the built `--outcome dmn` NoEffect graph | `value` equals `compile_table(...)`; input labels equal ids of events in the graph |
| R11 | `test_split_keeps_every_event_id` | `tests/fixtures/clean_graph_event_ids_2026-10-10.json` (ids of the pre-split build, captured by T3 before its first edit) against the new build | every baseline id present |
| R9 | `test_shared_core_is_single` | the built graph | each id of R9 occurs once; no event id starting `Help_` outside the allowed list of 4.6 |
| R16 | `test_turnoutcome_dictionary_equals_outcomes` | the built graph | the 7 values equal `OUTCOMES` |

### 5.3 `tools/clean_graph/simulate_clean_graph.py` (edit and extend, T3 and T4)

Existing checks that must change: lines 98-108 execute `Session_Chat` before `FAQ_UserQuestion`; line 118 executes `Session_Panel` before the selector; line 149-150 expect the Robots and System events of the build (dmn: `FAQ_Retrieve`, `Help_Retrieve`, `OutcomeTable`; code: the first two; System: six continuations). `run_robot` (68) gains a DMN branch: if the event has `computation` and the expression is `type="DMN"`, set the value with `evaluate_compiled`, run its update relations, then its responses.

| Req | New check | Expected |
|---|---|---|
| R8 | chat simulation: `FAQ_UserQuestion` after triage 1 | not executable until `Session_Chat` ran |
| R8 | panel: `Help_UserQuestion` after triage 1 | not executable until `Session_Panel` ran; then Robot runs, `Help_RetrievalOk` executed; fail and timeout make `Help_RetrievalUnavailable` pending |
| R8 | `Session_Chat` and `FAQ_Triage = 1` executed, no `Session_Panel` | `FAQ_UserQuestion` executable, `Help_UserQuestion` not; and the reverse with `Session_Panel` only |
| R10 | selector in a simulation without `Session_Panel` | not executable; after it, executable |
| R11 | existing Form0 checks (lines 135-146) | unchanged and passing |
| R15 | dmn build: `TurnStart`, then the gates one by one | `OutcomeTable` not executed before the fourth gate; executed once after it |
| R15 | `TurnResult` value for the nine representative inputs of the checklist (7.2, step 6) | `result 1:out_of_scope` through `result 9:not_covered` |
| R15 | a second turn (`TurnStart` and the gates again) | `OutcomeTable` executes again; `TurnResult` updated |
| R16 | for each of the seven values: execute `TurnOutcome` | exactly one event of `OUTCOME_EVENT.values()` pending, the mapped one |
| R16 | `TurnOutcome='confirm'` then `'offer'` with no acknowledgement | only `Outcome_Offer` pending |
| all | `validate_dcr_xml.py` on both builds | 0 errors, 0 warnings |

### 5.4 `tests/test_outcome_runtime.py` (new, T5)

| Req | Test | Input | Expected |
|---|---|---|---|
| R17 | `test_code_mode_writes_only_turnoutcome` | fake repo with `TurnOutcome`, mode `code` | one execute (`TurnOutcome`, value, comment `row 6; source code; misses 0`); no gate executes |
| R17 | `test_shadow_runs_table_and_keeps_code_result` | mode `shadow`; fake returns `TurnResult` `result 6:confirm` | executes `TurnStart`, four gates in order, `TurnOutcome`; `mismatch` false; outcome from code |
| R17 | `test_shadow_mismatch_is_logged_and_code_wins` | fake returns `result 4:answer` for a row 6 decision | `mismatch` true; `TurnOutcome` value is `confirm` |
| R17 | `test_dcr_mode_uses_table_result` | mode `dcr`, readable `result 7:clarify` | `TurnOutcome` `clarify`, source `dcr` |
| R17 | `test_dcr_mode_falls_back_when_unreadable` | `TurnResult` empty | code decision, source `code` |
| R18 | `test_not_exactly_one_pending_fails_closed` | fake leaves two outcome events pending | Not covered, source `failclosed`, error logged |
| R12 | `test_graph_without_turnoutcome_is_untouched` | payload lacks the event | zero executes, decision returned |
| R12 | `test_turnoutcome_with_wrong_dictionary_is_ignored` | six values | treated as absent, error logged |
| R17 | `test_parse_result` | `'result 6:confirm'`, `'6:confirm'`, `''`, `'result x'` | `(6,'confirm')`, `None`, `None`, `None` |
| R19 | `test_outcome_text_reads_the_dcr_event_or_none` | payload with and without `Outcome_Confirm` | description, or `None` |

### 5.5 Host tests (edit existing files, T6a/T6b and T7)

| Req | Test | Expected |
|---|---|---|
| R6, R3 | chat `test_lone_survivor_logs_row_6_and_true_single_row_4` | `faq_outcome` lines carry rows 6 and 4 |
| R7 | chat `test_unsure_gives_scope_question_row_2` | prompt kind `scope_check`, text from `FAQ_Msg_ScopeQuestion` when present, the line 467 string otherwise; `clarified` stays 0 |
| R5 | chat `test_second_list_after_clarify_is_offer_row_8` | two asks with a `clarify_match` and two answers each: row 7 then row 8 |
| R4 | chat `test_second_miss_adds_handover` | two `no_match` turns: second reply has `handover` and the `FAQ_NoMatch` text; a third miss does not repeat it |
| R10 | chat `test_chat_does_not_fire_determination` | `FakeDCR` with an enabled selector: no execute of the selector, `llm.pick_followup` not called |
| R10 | chat `test_followup_surface_chat_restores_today` | `FOLLOWUP_SURFACE=chat`: selector executed as today |
| R12 | chat `test_initialize_executes_session_chat_only_if_present` | one execute with the event, none without |
| R12 | chat `test_out_of_scope_acknowledged_once` | `FAQ_Triage=5` then settle: `FAQ_OutOfScope` executed once |
| R7 | panel `test_unscoped_message_goes_through_triage_with_values_1_and_5` | fake `classify` receives values `['1','5']`; `FAQ_Triage` executed with the result |
| R7 | panel `test_out_of_scope_returns_faq_out_of_scope` | `status='faq_out_of_scope'`, `FAQ_OutOfScope` text, no search |
| R7 | panel `test_related_click_and_field_scope_skip_triage` | no `classify('triage')` call; `FAQ_Triage=1` executed as today |
| R7 | panel `test_unsure_is_treated_as_in_scope` | search runs |
| R7 | panel `test_panel_triage_flag_off` | `PANEL_TRIAGE=0`: no triage call |
| R8 | panel `test_panel_uses_help_search_events` | `Help_UserQuestion` executed, `FAQ_UserQuestion` never |
| R8 | panel `test_start_executes_session_panel` | one execute at start |
| R10 | panel `test_panel_fires_determination_after_answer` | `_show` result has `prompt.kind='determination'`; selector executed |
| R10 | panel `test_determination_endpoint_leaves_application_unchanged` | `/application/determination` returns outcomes; `_unchanged` passes |
| R4 | panel `test_misses_use_outcome_counters` | two misses give reason 2 once per session; a shown answer resets |
| R19 | both `test_confirm_text_comes_from_dcr_event` | description of `Outcome_Confirm` used; host string when absent |

### 5.6 Manual checks

| Check | By | Expected |
|---|---|---|
| UI (T8): chat handover block, panel determination prompt, `faq_out_of_scope` message, using `demo-ui/preview/preview.mjs` mocks | implementer | Each renders; no console error |
| Portal import checklist and fixtures (section 7) | Amogh | Rows recorded in the checklist table |
| Follow-up eval re-run (`python -m evals.eval_followups --repeat 3`), after T6a/T6b | Amogh | WRONG 0 (spec 01 gate unchanged). Also report the outcome mix by row and how many group O turns now end in row 1. No tolerance is set by this spec |

## 6. Acceptance gate

Roadmap gate: "The chat never fires a determination; all nine rows tested." Run from the repo root on the device:

1. `$HOME/venv/bin/python -m pytest tests -q`: all pass except the five known `tests/test_faq_retriever.py` failures (`sentence_transformers` missing). `tests/test_outcome.py::test_table_nine_rows` shows nine rows plus the two extra row-5 and row-9 inputs.
2. `python tools/clean_graph/build_clean_graph.py --outcome dmn` and `--outcome code`; `python .agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py` on each output: `OK: 0 errors, 0 warnings`.
3. `python tools/clean_graph/simulate_clean_graph.py "xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"`: `FAILURES: 0`, including the selector gate and the table checks.
4. `grep -rn "interim_outcome" dcrai tests` returns nothing.
5. `tests/test_outcome.py::test_no_candidate_count_branch_in_runtimes` and `tests/test_retrieval_runtime.py::test_chat_does_not_fire_determination` pass.
6. Amogh: the Portal checklist of 7.2 is filled in (not required for `OUTCOME_MODE=code`, required before `dcr`).
7. Amogh: follow-up eval re-run shows WRONG 0.

## 7. Rollout and rollback

### 7.1 Order

Each step leaves the tests green and the old graph (2014078) working.

| Step | Work | Tasks |
|---|---|---|
| 1 | Outcome function and tests; generator and parity tests. No runtime change | T1, T2 |
| 2 | Builder: split, table, DMN; regenerate both variants; validator and simulator. The graph is not imported yet | T3, T4 |
| 3 | Host: `outcome_runtime`, wiring, determinations move. Everything feature-detected, `OUTCOME_MODE=code` | T5, T6a/T6b, T7 |
| 4 | UI and docs | T8, T9 |
| 5 | Amogh imports the new graph as a new graph id, attaches `handicap-faq-v2` to `FAQ_Retrieve` and `Help_Retrieve` (check the quoted continuations), restarts `python app.py` | T10 |
| 6 | Portal checklist and fixtures (7.2, 7.3); then `OUTCOME_MODE=shadow` for some sessions, read the `mismatch` entries | T10 |
| 7 | After the checklist passes, no mismatch, and the latency budget (Q6) is met: `OUTCOME_MODE=dcr` | Amogh |

### 7.2 Portal import checklist

Build the graph for the Portal with `python tools/clean_graph/build_clean_graph.py --with-effect --outcome dmn`. Import as a new graph. Never overwrite 2014078.

| # | Action | Expected | If not |
|---|---|---|---|
| 1 | Validator and simulator pass locally (section 6, items 2 and 3) | 0 errors, FAILURES 0 | Fix before import |
| 2 | Import `SU_handicaptillaeg_FAQ_Retrieval_Clean.xml` as a new graph; note the id | Import succeeds with no warning about the DMN | Send the exact message to the implementer; use the `--outcome code` build to continue |
| 3 | Open event `OutcomeTable` and its decision table | 4 inputs `GateScope`, `GateSearch`, `GateRelevance`, `GateClarified`; 9 rules; hit policy FIRST; the nine outputs `1:out_of_scope` to `9:not_covered`; no red input markers | Screenshot; note which input fails to bind (ids are alphanumeric by design) |
| 4 | Open the expression `OutcomeTable-computation` | The compiled text equals the string in 4.7 | If the Portal rewrote it, send the new text; it is the Portal's own compile of the table |
| 5 | Attach effect `handicap-faq-v2` to `FAQ_Retrieve` (`q` = `FAQ_UserQuestion`) and `Help_Retrieve` (`q` = `Help_UserQuestion`); ContinueOn values quoted (`"FAQ_RetrievalOk"`, `"Help_RetrievalOk"` and so on); `header#X-API-Key` quoted | Both Robots show the parameters | Re-import the effect; re-check quotes (re-import can drop them) |
| 6 | Portal simulation, role Chatbot: execute `TurnStart`, then the four gates with the values of each row below, in the order `GateScope`, `GateSearch`, `GateRelevance`, `GateClarified` | `OutcomeTable` runs after the fourth gate and not before; `TurnResult` shows the expected string | Record the row and the value shown |
| 7 | Execute `TurnOutcome` with the outcome of the row | Exactly one event of the last column is pending | Record which are pending |
| 8 | Repeat steps 6 and 7 for a second turn in the same simulation (different row) | The table runs again | Record; this is fixture F4 |
| 9 | Execute `TurnOutcome` = `handover` | `Help_Handover` pending | |
| 10 | Chat check: new simulation; try to execute `FAQ_UserQuestion` after `FAQ_Triage = 1` without `Session_Chat`; then `FAQ_DeterminationSelector` without `Session_Panel` | Both refused, then allowed after the session events | Record |
| 11 | REST check of F1 | `value` of `TurnResult` visible | If not, `dcr` mode is blocked (Route B or stay in `shadow`) |

Rows for step 6 and 7:

| Row | GateScope | GateSearch | GateRelevance | GateClarified | `TurnResult` | Outcome event pending after `TurnOutcome` |
|---|---|---|---|---|---|---|
| 1 | out_of_scope | none | none | 0 | `result 1:out_of_scope` | `FAQ_OutOfScope` |
| 2 | unsure | none | none | 0 | `result 2:clarify` | `Outcome_Clarify` |
| 3 | in_scope | none | none | 0 | `result 3:not_covered` | `FAQ_NoMatch` |
| 4 | in_scope | single | one_answers | 0 | `result 4:answer` | `Outcome_Answer` |
| 5 | in_scope | list | related | 0 | `result 5:offer` | `Outcome_Offer` |
| 6 | in_scope | list | one_answers | 0 | `result 6:confirm` | `Outcome_Confirm` |
| 7 | in_scope | list | several | 0 | `result 7:clarify` | `Outcome_Clarify` |
| 8 | in_scope | list | several | 1 | `result 8:offer` | `Outcome_Offer` |
| 9 | in_scope | list | none | 0 | `result 9:not_covered` | `FAQ_NoMatch` |

### 7.3 Fixture requests for Amogh

Each is small and uses the existing `xml graphs/DMN chatbot - english.xml` (Portal graph 2005522, or an import of the file).

| Id | Question it answers | What to do | What to send back |
|---|---|---|---|
| F1 | Does the REST event list show the DMN result? | Import the DMN chatbot as a new graph. Create a REST simulation (`rest-simulation-api.md`). Execute `Country` = `Denmark` and `Age` = `20`, each with role `User`. GET the event list | The JSON entries of events `DMN` and `A4` (fields `value`, `executed`, `pending`, `included`, `enabled`). Expected `A4.value` = `Can you purchase alcohol? Yes` |
| F2 | Can a relation read a Robot DMN event's string output as a guard, and is a string like `1:yes` fine? | In a copy: add label event `B1` (role `User`); change the first rule's output from `"Yes"` to `"1:yes"`; add response `DMN` to `B1` with guard `DMN = "1:yes"`. Run `Denmark`, `20`; then a fresh simulation with `Denmark`, `10` | Whether `B1` is pending in each run, and the exported XML of the copy |
| F3 | Is a table with 4 inputs and 9 rules, an integer input `0`/`1` and dash rows accepted? | Import the generated Clean graph (checklist steps 2 to 4) | Screenshot of the decision table, or the import error text |
| F4 | Does the Robot DMN run again on a second turn when its inputs are made pending again? | In the F2 copy: add event `Start` (role `User`) with responses to `Country` and `Age`. Execute `Country`, `Age` (first result), then `Start`, `Country`, `Age` with other values | `A4.value` after each round, and whether `DMN` shows as executed twice |
| F5 | Do two Robots carry the same effect with different continuation ids? | In the imported Clean graph, attach `handicap-faq-v2` to both `FAQ_Retrieve` and `Help_Retrieve`; run one search through each (Portal simulation or `tools/probe_simulation_effect.py`) | `FAQ_RetrievalOk.value` and `Help_RetrievalOk.value` after their runs, or the error |

F1 and F4 block `dcr` mode. F2 blocks Route B only. F3 and F5 block the import of the default build.

### 7.4 Fallback if the DMN does not behave

| Level | Action | What stays |
|---|---|---|
| 1 | `OUTCOME_MODE=code` (the default) | Everything: split graph, `TurnOutcome` written by the host with DCR making the outcome event pending, DMN events inert |
| 2 | Re-import the build from `python tools/clean_graph/build_clean_graph.py --with-effect --outcome code` (no `OutcomeTable`, no gates, no `TurnStart`, no `TurnResult`) | The same, without the DMN machinery |
| 3 | Run on the old graph (2014078, or any graph without the new events) | Today's behaviour; `FOLLOWUP_SURFACE=chat` and `PANEL_TRIAGE=0` restore the old determination and triage behaviour |

Levels 1 and 2 are the "outcome table evaluated in code, DCR admitting the result" fallback: the function decides, the host executes `TurnOutcome`, and the guarded responses decide which outcome event is pending.

### 7.5 Rollback of code

Flags (`OUTCOME_MODE`, `FOLLOWUP_SURFACE`, `PANEL_TRIAGE`) in `.env`, then restart `python app.py`. The outcome function replaces spec 01's `interim_outcome` permanently; reverting it means reverting tasks T6a and T6b with git. The Handover in the chat is on by default; there is no flag for it (Q7).

## 8. Risks and open questions

| Id | Item | Owner | Blocks |
|---|---|---|---|
| Q1 | Fixtures F1 to F5 (section 7.3) | Amogh | `dcr` mode (F1, F4), import of the default build (F3, F5). Not `code` mode |
| Q2 | Wording for row 8 (Offer after a clarify). The default reuses the Clarify text, which is today's options text | Amogh | The text constant only |
| Q3 | Should the panel ask the scope question for `unsure` (needs a two-button card in the UI)? Default: ignore `unsure` in the panel | Amogh | Nothing; row 2 stays chat-only |
| Q4 | Should a topic switch clear `clarified`? Default: only a resolved question clears it | Amogh | Counter rules only |
| Q5 | The roadmap mentions a panel policy event and panel thresholds. This spec shares `FAQ_Triage` (values limited to 1 and 5 by the host) and uses one effect for both Robots. A panel-only policy text, or thresholds that differ, need spec 02's registry and a new effect (`handicap-faq-v3` with a `profile` parameter, set in Effect Administration, and an API change) | Amogh | Nothing |
| Q6 | Latency budget. `shadow` and `dcr` add seven DCR calls per turn (five executes for `TurnStart` and gates, one for `TurnOutcome`, one refresh to read the result, one to check pending). No number is set here | Amogh | Making `shadow` or `dcr` the default |
| Q7 | Handover in the chat (reasons 1 and 2) is new behaviour, on by default. Reasons 3 and 4 stay panel-only | Amogh | Nothing |
| Q8 | Trace field names (A7) | implementer, with spec 02 | Names in `log_outcome` only |
| Q9 | Whether the REST event list returns the label value (F1) decides if `dcr` can read the result | Amogh | `dcr` mode |
| Rk1 | The Portal may reject or reinterpret a construct marked Unverified in 4.7 (4 inputs, 9 rules, colon in output) | Amogh | Mitigated by 7.4 |
| Rk2 | Counters live in the session and are lost on restart, as `help_misses` is today | implementer | Moves with spec 02's context record |
| Rk3 | The panel triage adds one model call per unscoped message and may misjudge a legitimate field question as out of scope. `PANEL_TRIAGE=0` restores today | implementer | Eval group O (5.6) shows the effect |
| Rk4 | Concurrent edits of `build_clean_graph.py` and `simulate_clean_graph.py` (gitignored, no merge help) | implementer | Edit order in 9.1 |
| Rk5 | If the host forgets `Session_Panel` or `Session_Chat`, search and follow-ups are refused ("DCR did not admit the question", `application_runtime.py:694`). It fails closed and visibly; tests in 5.5 cover both |  | |
| Rk6 | Determinations in the panel put a `Det*_Ask` obligation next to `Form0`. The application view reads only `Form0:` and tagged application events (C17), so it is not disturbed; the code read is not a run | implementer | T7 test and a manual run |
| Rk7 | Shadow mismatches are bugs in either the function or the DMN; the log entry names both results so the cause is findable | Amogh | |

## 9. Implementation tasks

Each task fits one session, names the requirements it satisfies, and says how it is tested without a model. "Spec 01 Tn" and "spec 02 Tn" mean the task numbers in section 9 of `docs/specs/01-stop-wrong-answers.md` and `docs/specs/02-registry-and-trace-record.md`. Gitignored files (`tools/`, `xml graphs/`) are regenerated at the end of each task by running the builder, never edited by hand.

| # | Task | Requirements | Files | Tested by (no model call) | After |
|---|---|---|---|---|---|
| T1 | Write `outcome.py`: `ROWS`, `OUTCOME_EVENT`, `Decision`, `table`, `derive_inputs`, `decide`, `shown_for`, `next_clarified`, `next_misses`; move nothing yet | R1 to R5, R16 (map), R22 | `dcrai/chat/outcome.py`, `tests/test_outcome.py` | 5.1, all rows except the two static scans | none |
| T2 | Write `dmn_table.py`: `lit`, `test_expr`, `cond_expr`, `compile_table`, `definitions_xml`, `evaluate_compiled`; regression against the two observed exports; parity tests | R13, R14 | `tools/clean_graph/dmn_table.py`, `tests/test_outcome_table_graph.py` (generator and parity tests) | 5.2 rows R14 and `test_definitions_*` (export tests skip if `xml graphs/` is missing) | T1 |
| T3 | Capture the id baseline fixture from the current build, then split the graph: builder helpers (`strchoice`, `computation`, `milestone`, `update`), session events and conditions, `Help_*` search Robot and events, determinations gate, two-Robot effect strip, `--outcome` flag; simulator patches (lines 98-108, 118, 149-150, `run_robot`) | R8 to R12, R21 (flag) | `tools/clean_graph/build_clean_graph.py`, `tools/clean_graph/split_steps.py`, `tools/clean_graph/simulate_clean_graph.py`, `tests/fixtures/clean_graph_event_ids_2026-10-10.json`, `tests/test_outcome_table_graph.py` (id and shared-core tests), regenerated `xml graphs/` | validator 0 errors, simulator 0 failures with the new 5.3 session checks, `test_split_keeps_every_event_id`, `test_shared_core_is_single` | spec 02 T7, T1 |
| T4 | Outcome table in the graph: `TurnStart`, four gates, `OutcomeTable` with DMN, `TurnResult`, `TurnOutcome`, seven outcome events with guarded responses and co-responses, outcome and scope message events; simulator DMN branch and table checks | R13, R15, R16, R19 (graph side), R21 | `tools/clean_graph/build_clean_graph.py`, `tools/clean_graph/split_steps.py`, `tools/clean_graph/simulate_clean_graph.py`, regenerated `xml graphs/` (both `--outcome` variants) | 5.2 `test_built_graph_dmn_is_in_step`, `test_turnoutcome_dictionary_equals_outcomes`; 5.3 R15 and R16 checks; validator on both variants | T2, T3 |
| T5 | Write `outcome_runtime.py`: `settle`, `parse_result`, `outcome_text`, `acknowledge`, `handover`, `PERSON`, `URGENT`; modes `code`, `shadow`, `dcr` with fakes | R12, R17, R18, R19 | `dcrai/chat/outcome_runtime.py`, `tests/test_outcome_runtime.py` | 5.4 | T1 |
| T6a | Wire the chat: replace spec 01's `interim_outcome` and its branch in `ask`; scope input and unsure row 2; counters `clarified` and `misses`; Handover reasons 1 and 2; `Session_Chat` at `initialize`; texts from DCR events; out-of-scope acknowledgement; log fields | R3 to R7, R12, R17 to R19 | `dcrai/chat/retrieval_runtime.py`, `tests/test_retrieval_runtime.py` | 5.5 chat rows (R3, R4, R5, R6, R7, R12, R19) and 5.1 `test_no_candidate_count_branch_in_runtimes` for the chat file | T1, T4, T5, spec 01 T3, T4, T5, T7, spec 02 T2, T5 |
| T6b | Wire the panel: replace the `direct` branch in `ask`; `SEARCH_EVENTS['panel']`; panel triage (values 1 and 5, `PANEL_TRIAGE`); `faq_out_of_scope` status; `Session_Panel` at `start`; counters and `handover` helper (the panel's `escalate` calls it); texts from DCR events; log fields | R3 to R7, R8, R12, R17 to R19 | `dcrai/application/application_runtime.py`, `tests/test_application_faq.py` | 5.5 panel rows (R4, R7, R8, R12, R19) and the panel half of the static scan | T6a |
| T7 | Move determinations: chat stops calling the selector and `pick_followup` (`FOLLOWUP_SURFACE`); extract `rr.open_followup` from `show_answer`; panel `_show` calls it; `determination(state, data)` and `POST /application/determination` in `install` | R10 | `dcrai/chat/retrieval_runtime.py`, `dcrai/application/application_runtime.py`, both test files | 5.5 R10 rows (chat never fires; flag restores; panel fires; `_unchanged`) | T3, T6b |
| T8 | UI: chat Handover block, panel determination prompt, `faq_out_of_scope` status, preview mocks, rebuild the bundle | R20 | `demo-ui/src/SupportChat.jsx`, `demo-ui/src/ApplicationDemo.jsx`, `demo-ui/preview/preview.mjs`, `static/demo/` | 5.6 UI check by the implementer | T6b, T7, spec 01 T7 |
| T9 | Settings and docs: `.env.example` (three flags and `OUTCOME_MODE`), `CLAUDE.md` section, `evals/README.md` outcome mix note, docstring of the builder; one-line stub edit in `evals/eval_followups.py` so `Help_UserQuestion` is a known input | R17, R21 | `.env.example`, `CLAUDE.md`, `evals/README.md`, `tools/clean_graph/build_clean_graph.py` (docstring only), `evals/eval_followups.py` | existing suite; `python -m evals.eval_followups --help` runs | T6b, spec 01 T5, spec 02 T11 |
| T10 | Amogh: run the fixtures F1 to F5, the Portal import checklist, the shadow period, the decision on `dcr` mode | gate | none in the repo | section 7 | T4, T9 |

### 9.1 File ownership and edit order

Three implementers work on one tree: spec 01 (phase 1), spec 02 (phase 2), spec 03 (this spec). Spec 02 section 9 lists its expected spec 03 edits; this table agrees with it and adds the named places. "Edit" means this spec edits only the named functions or regions.

| File | Spec 03 | Spec 01 also | Spec 02 also | Merge rule |
|---|---|---|---|---|
| `dcrai/chat/outcome.py` | create (T1) | none | none | free |
| `dcrai/chat/outcome_runtime.py` | create (T5) | none | none | free |
| `tools/clean_graph/dmn_table.py`, `split_steps.py` | create (T2, T3, T4) | none | none | free; new code goes here so the builder diff stays small |
| `dcrai/chat/retrieval_runtime.py` | edit (T6a, T7): `ask`, `route`, `scope_check`, `follow_dcr`, `reply_to_prompt`, `initialize`, `search` (event-id lookup only), `show_answer` (extract `open_followup`) | heavy: `flag`, `search`, `ask`, `reply_to_prompt`, `log_outcome`, `log_reaction`, `handle` | line 41 (T2); decorators on `search`, `handle`, one line in `dcr_context` (T5); `flag` body (T11) | T6a and T7 after spec 01 T3, T4, T5, T7 and spec 02 T2, T5, so the decorators already sit on the final functions. Do not move or rename a decorated function; if one must be renamed, move the decorator with it |
| `dcrai/application/application_runtime.py` | edit (T6b, T7): `start`, `ask` (triage block, outcome branch), `_show`, `escalate` (calls the shared `handover`), `_miss`, `install` (one route), `PERSON` and `URGENT` (moved to `outcome_runtime`, re-imported under the same names) | heavy: `ask`, `confirm`, logging | lines 46, 512 (T2); line 792 (T3); decorators and `note` line (T5); `help_context` and one line after 718 (T8) | T6b and T7 after spec 01 T4, T7 and spec 02 T2, T5, T8. `help_context` and `Panel_Context` handling are not touched. `MISSES_BEFORE_HANDOVER` (line 512) stays defined where spec 02 T2 leaves it |
| `tools/clean_graph/build_clean_graph.py` | edit (T3, T4): the places in 4.6 | none | one `add_event` after line 326 and one tuple entry at lines 398-401 (T7); lines 311-317 (T10) | Gitignored: no git merge. Order: spec 02 T7, then spec 03 T3, then T4, then spec 02 T10 (it reads the triage policy and must keep `FAQ_Triage` ids). One person edits this file at a time; keep `Panel_Context` and `Help_Escalate` untouched |
| `tools/clean_graph/simulate_clean_graph.py` | edit (T3, T4): lines 98-108, 118, 149-150, `run_robot`, new checks | none | none (spec 02 T7 only runs it) | Gitignored. Sequential: T3 then T4. Run it before and after each edit |
| `xml graphs/*.xml` | regenerated by the builder at the end of T3 and T4 | none | regenerated by spec 02 T7 | The builder, not the XML, is the source. Whoever runs it last wins; so spec 02 T7, then T3, then T4 |
| `tests/test_retrieval_runtime.py`, `tests/test_application_faq.py` | add-only (T6a, T6b, T7): new test functions; `FakeDCR` gains `TurnOutcome` and session events only where a test needs them | edits fakes and existing tests (T2, T4, T5) | none | After spec 01 T5, which updates the fakes. Do not edit an existing test except `test_interim_outcome_rows` (deleted with `interim_outcome`) |
| `tests/test_outcome.py`, `test_outcome_table_graph.py`, `test_outcome_runtime.py`, `tests/fixtures/clean_graph_event_ids_2026-10-10.json` | create | none | none | free |
| `evals/eval_followups.py` | one-line stub edit (T9) so `Help_UserQuestion` is accepted | heavy (T1, T5) | one line in the report header (T11) | After spec 01 T5; add-only |
| `demo-ui/src/SupportChat.jsx`, `demo-ui/src/ApplicationDemo.jsx`, `demo-ui/preview/preview.mjs`, `static/demo/` | edit (T8): the blocks in 4.5 | T7 edits `ApplicationDemo.jsx`, `preview.mjs`, `static/demo/` | none | After spec 01 T7. Rebuild the bundle once, last |
| `.env.example`, `CLAUDE.md`, `evals/README.md` | add-only (T9): own rows and own section | T8 adds rows and a section | T2, T11 add rows and a section | Each spec under its own heading; no reflow |
| `app.py` | not edited (the new route is registered in `install`) | T3 adds the `ilog.start` call in `/init` | none | n/a |
| `dcrai/llm/retrieval_llm.py` | not edited (`triage_decisions` already takes a values list, line 231) | edits constants and adds functions | edits `decisions_enabled`, `_threshold`, `_decide`, `_structured` | n/a |
| `dcrai/observability/interaction_log.py`, `dcrai/registry.py`, `dcrai/paths.py` | not edited | T3 kinds block | T1 to T3 | n/a. The new log fields go through the existing `log_outcome` keyword arguments |

Order across the three specs: (1) spec 01 T1 to T5 and spec 02 T1 to T7 first, as their own sections say. (2) Spec 03 T1, T2, T5 are new files and can start at once. (3) T3 and T4 after spec 02 T7. (4) T6a, T6b, T7 after spec 01 T3, T4, T5, T7 and spec 02 T2, T5. (5) T8 after spec 01 T7. If an implementer finds a file edited out of order, stop and ask rather than resolve it.

## 10. Evidence table

Labels: Observed (read in the repo or run on the device, 2026-10-10), Documented (a file in the repo or the project says so; not re-checked), Unverified (not read or run; stated with the check that resolves it).

| Claim | Label | Source |
|---|---|---|
| One Robot, three System continuations, selector with no precondition, message events executed by the host | Observed (code read) | C2 to C9 in section 2.1 |
| `tools/clean_graph/simulate_clean_graph.py` on the NoEffect graph: 39 checks pass | Observed (run) | device, 2026-10-10 |
| `validate_dcr_xml.py` on the NoEffect graph and on `DMN chatbot - english.xml`: 0 errors | Observed (run) | device, 2026-10-10 |
| Host outcome branching by candidate count in two places; chat scope check; panel triage always 1; chat follow-up; panel no follow-up; panel-only handover | Observed (code read) | C10 to C19 in section 2.2 |
| The application view and `_unchanged` read only `Form0:` and tagged application events | Observed (code read; not run) | `dcrai/application/application_runtime.py:27-31,48-58,498-506` |
| DMN event shape (computation attribute, `<definitions>`, FIRST, labels equal event ids, last rule dashes) | Observed (Portal export) | `xml graphs/DMN chatbot - english.xml:90,176-192` |
| Robot DMN result copied into a label by an update relation with a string expression | Observed (Portal export) | `xml graphs/DMN chatbot - english.xml:319-336` |
| Guards on a DMN-computed event's string output | Observed (Portal export) | `xml graphs/Corona - ChatBot SOP.xml:1038-1041,1347-1352` |
| The compile generator reproduces both exported compiled values byte for byte | Observed (run, scratch prototype) | C22 |
| The nine-row table, the Python function and the compiled generator output agree on all 64 valid input combinations; every row is reachable | Observed (run, scratch prototype) | C23 |
| The compiled expression for the nine rows is 1,136 characters | Observed (run, scratch prototype) | 4.7 |
| The Portal accepts a table with four inputs, nine rules, an integer input and dash rows | Unverified (observed shapes have two to five inputs, string and integer, dashes) | F3 |
| Underscores in DMN input labels | Unverified | Avoided: the gate ids are alphanumeric |
| A colon and a digit in a DMN string output | Unverified | F2; the rows use `"<row>:<outcome>"` |
| A guard on a Robot DMN output (Route B) | Unverified | F2 |
| The REST event list returns the label value of `TurnResult` | Unverified | F1 |
| The Robot DMN runs again on a second turn when its inputs are made pending again | Unverified | F4; the local simulator is a model of the semantics, not the engine |
| Two Robots carry the same effect with different continuation ids | Unverified | F5 |
| Seven extra DCR calls per turn in `shadow` and `dcr` | Unverified (counted from the design, not measured) | Q6 |
| The follow-up eval stays at WRONG 0 after the split | Unverified | Needs the eval run (T10) |
| Unit test baseline 228 passed, 5 failed, 1 skipped, 493 subtests | Documented (brief, spec 01 C33); not re-run for this spec | `docs/specs/00-brief.md` section 4 |
| Spec 01 lists A4 and A5 and the `interim_outcome` rules | Observed (read) | `docs/specs/01-stop-wrong-answers.md` sections 4.3, 10 |
| Spec 02 lists its expected spec 03 edits, A6 to A9 about this spec, and the task order | Observed (read) | `docs/specs/02-registry-and-trace-record.md` sections 9, 10 |

### Assumptions about other specs

| Id | Assumption | Spec | If wrong |
|---|---|---|---|
| A4, A5 | Confirmed in 4.3 with the corrections listed there (rule 6 row 5; `same_faq` is a render flag) | 01 | Spec 01 edits: rule 6 expected row `5`; the same-FAQ branch logs the interim outcome plus `same_faq=True` |
| B1 | `state['last_search']` holds `{'decision', 'retrieved'}` and each kept candidate has a `tier` of `answers` or `related` (all `answers` until spec 01 T5) | 01 T4, T5 | `decide` gets no input; T6a/T6b blocked |
| B2 | `log_outcome` and `log_reaction` exist (spec 01 T3) and accept extra keyword fields | 01 T3 | Add the keywords in T6a |
| B3 | The chat Confirm prompt, Offer text and options turn built by spec 01 T4 are reused, not rebuilt | 01 T4 | T6a rebuilds the rendering per outcome |
| B4 | `rr.flag(name, default)` exists | 01 T2 | Use `os.environ` in T6a, T6b, T7 |
| B5 | Wording decisions WD1 to WD4 stay host constants; row 8 text reuses the Clarify text (Q2) | 01 | Text constants only |
| A6 | `outcome` and `outcome_row` fields of the trace record; spec 02 A6 accepts an optional `outcome_inputs` object, whose keys this spec defines as `scope`, `search`, `relevance`, `clarified`, `misses` | 02 | Rename in `log_outcome` only |
| A7 | Other field names (`outcome_source`, `outcome_dcr`, `outcome_row_dcr`, `handover_reason`, `clarify_kind`, `same_faq`, `mismatch`) are placeholders until spec 02 names them | 02 | T6a, T6b adapt keyword names |
| A8 | `interface` is `chat` or `panel`; read through `interface_of(state)` | 02 | Change the accessor body |
| A9 | The `Panel_Context` event, its group `PanelContext` and every pre-split event id stay (R11); this spec adds no relation to or from it | 02 T7 | `test_split_keeps_every_event_id` fails at the build |
| A10 | The search event id constants (`retrieval_runtime.py:36-37`) are not changed by spec 02 | 02 | Resolve at the edit-order step |
| A11 | The registry can later supply the outcome message texts to the builder; until then the constants of 4.6 are used | 02 | None needed |
| A12 | Spec 02's turn recorder wraps `handle`, `ask` and `confirm`, so the outcome log line is in the turn (spec 02 A9) | 02 T5 | The turn has no outcome fields; the `faq_outcome` line is still written |

### Open questions that block implementation

| Question | Blocks |
|---|---|
| Spec 02 T7 (`Panel_Context` in the builder) must land first | T3, T4 |
| Spec 01 T3, T4, T5 and spec 02 T2, T5 must land first | T6a, T6b, T7 |
| Q1 (fixtures F1 to F5) | `dcr` mode only; not implementation |
