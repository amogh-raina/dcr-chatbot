# Spec brief: gated FAQ assistant

Read this first. It applies to every spec in `docs/specs/`. The scope and roadmap are in `docs/specs/00-scope-and-roadmap.md` (read all of it, including Appendix A).

## 1. What we are doing

Spec-driven development. Specs are written first, reviewed, and then implemented by separate runs that work only from the spec. A spec is therefore the whole contract: an implementer who has not seen this conversation must be able to build it, and a reviewer must be able to test it.

Project: SU handicaptillæg FAQ and application-help assistant (Amogh's XHAILE/CHAI neuro-symbolic eGovernment work). DCR graphs are the agent harness: the model proposes a value, DCR decides whether that value is admissible. The use case is the test bed for the split between what DCR owns, what the model owns, and what code owns.

Repo: `/Users/lzp112/Projects/DCR.AI`, reached on the linked computer at `$HOME/mnt/DCR.AI` through `mcp__remote-devices__device_bash` (load the tool with ToolSearch if it is deferred). Read `CLAUDE.md` ("Repository layout" first), `prompts/README.md`, `evals/README.md`, `docs/handoffs/HANDOFF_2026-10-09_followup_eval.md` and `evals/reports/followup_report.md`. The layout was restructured on 2026-10-10; use the new paths. `tools/` and `xml graphs/` are gitignored but present and you may read them (graph builder: `tools/clean_graph/build_clean_graph.py`; graphs: `xml graphs/`).

## 2. The spec set and who writes what

| Spec | File | Roadmap phase | Writer |
|---|---|---|---|
| 01 Stop wrong answers | `docs/specs/01-stop-wrong-answers.md` | 1 | Opus agent A |
| 02 Registry and trace record | `docs/specs/02-registry-and-trace-record.md` | 2 | Sonnet agent |
| 03 Graph split, outcome table, DMN | `docs/specs/03-graph-split-outcome-table-dmn.md` | 3, and the graph part of 5 | Opus agent B |
| 04 Judges, review, regression gate | not written in this round | 4 | later |
| 00 index | `docs/specs/README.md` | | the orchestrator, after the three specs exist |

The three agents cannot talk to each other. These contracts keep the specs consistent; follow them and do not redefine another spec's items.

- **Trace and registry fields belong to spec 02.** Names: `interaction_id`, `simulation_id`, `turn`, `interface` (`chat` or `panel`), `registry_version`, `graph_revision`, `outcome`, `outcome_row`, plus the model-call, search and relevance records listed in the roadmap section "Traces, evaluation and human review". Specs 01 and 03 say which of these they need populated and do not define the schema.
- **The outcome function belongs to spec 03.** Spec 03 defines its signature, its inputs and the nine rows. Spec 01 changes the existing code path so that row 6 (lone survivor of a pruned list gives Confirm) holds today, in the smallest change that is compatible with spec 03's function, and says what spec 03 replaces.
- **Prompt files belong to spec 02 for storage and loading, to the spec that changes the wording for the text.** Prompts are text files under `prompts/` loaded by `dcrai/prompts.py`. Spec 01 edits or adds files there; spec 02 extends the loader into the registry with thresholds and settings.
- **The panel context record in DCR is specified by spec 02** as an additive change to the current graph (event ids, types, when written, how read), so phase 2 can ship before phase 3. Spec 03 must keep it when it splits the graph.
- **Graph XML is generated with the dcr-xml-builder skill.** Spec 03 owns the split and the DMN. Specs 01 and 02 list graph changes only where they need them and mark them as handed to spec 03 when they depend on the split.

## 3. Decisions already taken (do not reopen)

- Gate calls stay host-side: the host calls the model, then executes the DCR event with the returned value; relations decide what is admissible next.
- Two retrieval Robots (FAQ chat and application Help panel), each with its own search events, sharing triage, scope, out-of-scope messages, the outcome table and the handover.
- Follow-up determinations are made in the application session only, never in the FAQ chat (changed 2026-10-10).
- The confirm step "Is this what you are asking?" is acceptable in both interfaces. Track the confirm accept rate and the re-explain rate.
- Traces are verbatim (user text, rewrites, model inputs and outputs, scores, versions). The demo uses fictional data. PII scrubbing, jailbreak and injection filtering and authentication are out of scope.
- Human in the loop has two parts: a call-support handover for the applicant, and a reviewer queue that turns flagged turns into labelled test cases.
- Amogh is the policy owner and the only reviewer of flagged turns for now, reviewing later in the log.
- The decision table (DMN) is built in the graph XML through the dcr-xml-builder skill. Amogh imports it into the Portal and debugs it, so the spec must give a Portal import checklist and a fallback.
- The regression tolerance for correct answers is undecided. The hard gate stays zero wrong answers. A spec states how the drop is measured and lists the tolerance as an open decision; it does not invent a number.
- Wording decisions (the four from the eval review) are written from what the eval runs observed. Review and revise loops come later. Find the four in the handoff, the eval report and `CLAUDE.md`; if you cannot identify them with certainty, list them as an open question instead of guessing.
- Model API: Decisions API for choice and predicate questions, Responses API for rewrite and fallback triage. Triage values are 1, 2, 4, 5.

## 4. Facts you can rely on

Labelled by evidence. Cite the file when you use them, and re-verify any line you build on.

**Observed in the repository or the eval**
- Follow-up eval 2026-10-09: 33 wrong answers in 147 runs (30 after the f08 label correction) against a target of zero. All came through the lone-survivor path. None of the 19 true single matches was wrong. 31 of 102 answerable runs lacked the right FAQ in the top three.
- Tests: 228 passed, 5 failed (all in `tests/test_faq_retriever.py`, `sentence_transformers` missing), 1 skipped, 493 subtests passed. Run with `python -m pytest tests` from the repo root using `$HOME/venv/bin/python` on the device.
- Thresholds (env): `DECISIONS_TRIAGE_MIN` 0.6, `DECISIONS_REPLY_MIN` 0.6, `DECISIONS_CONTEXT_MIN` 0.7, `DECISIONS_RELEVANT_MIN` 0.5, `DECISIONS_FOLLOWUP_MIN` 0.7; retrieval 0.80 / 0.50 / 0.12.
- Instructions are text files under `prompts/` (14 files, `prompts.version()`), policy text for triage is the `FAQ_Triage` event description produced by `tools/clean_graph/build_clean_graph.py`.

**Observed in an exported graph (`xml graphs/DMN chatbot - english.xml`)**
- Embedded DMN: `<expression type="DMN" value="compiled">` with a `<definitions>` child, hit policy FIRST, a Robot event that runs it, and an update relation writing a string output to a label.
- Compile rule seen in the export: nested `If( cond ) THEN ( out ) ELSE ( ... )` in row order; `>=18` compiles to `((Age = 18) OR (Age > 18))`; `-` compiles to `true`; a row of dashes only compiles to `(true AND true)`; the chain ends with `ELSE ( null )`.

**Documented, not observed** (https://documentation.dcr.design/documentation/decision-model-and-notation/)
- Results written as integers to a choice field; hit policy ALL (Portal 7.3.0, returns an array); a Robot decision re-executes whenever it becomes pending; Portal 7.6.5 returns a FEEL context.

**Unverified, do not generate XML that depends on it without a fixture request to Amogh**
- Hit policy ALL; comparison operators other than equality and greater-or-equal; ranges; several outputs; an integer-output table on a choice event used in a guard; the FEEL-context result; response deadlines that read a date from an event; Robot:Prime and Robot:Terminator roles; effect continuation serialization beyond what the existing graph uses; spawned subgraphs.

Where a design needs an unverified construct, give two routes: the route inside the observed shape, and the route that needs a Portal fixture, with the exact fixture request for Amogh.

## 5. Required structure of every spec

Use these headings in this order. Tables over prose. Concise bullets, direct language.

1. **Status and scope**: one paragraph, plus in-scope and out-of-scope bullets.
2. **Current state (observed)**: what the code and graph do today, each claim with `path:line`.
3. **Requirements**: numbered `R1..Rn`, each one testable, each with MUST or SHOULD.
4. **Design**:
   - **Code changes**: per file, the function or constant, old behavior, new behavior, signatures. Name every file path in the new layout.
   - **Graph XML changes**: per event and relation: id, type, role, description, marking, guard; and which builder step produces it. Label each construct Observed, Documented or Unverified.
   - **Data and schema**: any new record, field or file, with an example.
5. **Test plan**: for each requirement, the test that proves it (file, name, input, expected). Unit tests never call a model. Eval gates state the case set, the number of repeats, the metric and the pass threshold.
6. **Acceptance gate**: the roadmap gate restated as a check an implementer can run.
7. **Rollout and rollback**: order of changes, flags, how to go back.
8. **Risks and open questions**: each with owner (Amogh or implementer) and what it blocks.
9. **Implementation tasks**: ordered list, each task small enough for one session, naming the requirements it satisfies and the files it touches.
10. **Evidence table**: every non-obvious claim, its label (Observed, Documented, Unverified) and its source.

Length: as long as needed to be complete and no longer. A typical spec is 250 to 600 lines.

## 6. Rules

- Do not overclaim. If you did not read it or run it, say so. Do not state that a design "will work" in DCR unless the construct is Observed.
- Verify every path, function name and line number you cite by reading the file. Do not invent names.
- No em-dashes. Natural, direct language. Do not name functions or scripts inside running prose where a table or code span works better; code spans are fine.
- The repo is read-only for you except your own spec file in `docs/specs/`. Do not edit code, graphs, prompts, tests or other specs. Do not run git commands. Do not read `.env`. Do not run anything that calls a model (the eval runners, the probe scripts). Reading existing eval outputs in `evals/` and `traces/` is fine, and running the unit tests is fine.
- Graph XML: you may write draft XML snippets inside the spec, but do not create or modify graph files.
- Write your spec with a single `device_bash` call using a Python heredoc to `$HOME/mnt/DCR.AI/docs/specs/<file>.md`, then read it back and check it for the structure above, broken tables and em-dashes.
- Final message to the orchestrator (under 200 words): the file path, line count, the three most important decisions you made, every assumption you had to make about another spec's contract, and open questions that block implementation.

## 7. Skills

Invoke these with the Skill tool before you write, and follow them:
- `engineering:system-design` for the design and requirement structure (and `engineering:architecture` for any trade-off that deserves a decision record inside the spec).
- `anthropic-skills:dcr-xml-builder` for every graph construct. It is mandatory for spec 03 and for any graph change in specs 01 and 02.
- `engineering:testing-strategy` for the test plan section.

There is no skill named spec-driven-development in this environment; the structure in section 5 is the spec-driven discipline for this project.
