# Gated FAQ assistant: scope and roadmap

Oct 9, 2026 · @Amogh Raina

## Decisions taken

The host keeps calling the models, DCR decides what their answers are allowed to trigger, and the graph is split into a chat part and an application-help part that share policies.

- **Gate calls stay host-side.** The host calls the model, then executes the DCR event with the returned value. Relations in the graph decide what is admissible next, as FAQ_Triage already does for the search.
- **Two interfaces, two retrieval Robots.** The FAQ chat and the application Help panel each get their own search events and Robot, and share triage, scope and out-of-scope policies. Follow-up determinations are made in the application session only, not in the FAQ chat (changed on 2026-10-10).
- **Traces are verbatim.** User text, rewrites, model inputs and outputs, scores and policy versions are all stored. The demo uses fictional data; redaction and PII handling are downstream.
- **Human in the loop has two parts.** A call-support handover for the applicant, and a reviewer queue that turns flagged traces into labelled test cases.
- **Out of scope for this roadmap:** PII scrubbing, jailbreak and injection filtering, authentication.

## Where the system stands

The chat has real gates, but instructions, state and logs are spread over several places, and the follow-up eval of 2026-10-09 found 33 wrong answers in 147 runs (30 after correcting one label) against a target of zero.

| Area | Today | Gap |
| --- | --- | --- |
| Instructions | 8 prompt constants in two files, about 6 predicate wordings inline in functions, and the chat triage policy as a Python string in the graph builder | The panel has no policy event. Nothing records which text produced a result |
| Settings | About 20 environment settings read in several files | No versioned set, so a result cannot be tied to the values used |
| Session context | Chat: last answered FAQ and determinations live in DCR. Panel: last message and last FAQ live in a Flask in-memory dict | Two stores. The panel's is lost on restart |
| Metadata | Each FAQ has a topic (5 values), availability, status and gap note | Retrieval ignores all of it. 3 FAQs marked drafted_needs_review can be shown as official answers |
| Gates | Chat: 4-way triage, search thresholds, relevance check. Panel: search thresholds and relevance check only | No scope or answerability gate in the panel. A fallback rewrite turns unrelated messages into questions about the field on screen |
| Answer selection | A candidate list cut to one survivor by the relevance check is answered directly | All 33 wrong answers came this way. None of the 19 true single matches was wrong |
| Logs | One JSONL file per interaction: field answers, FAQ ids found, handovers | No model inputs or outputs, scores, rewrites or versions. Nothing reads the files. The join key to DCR is simulation_id |
| Evals | Three eval and calibration scripts and four label files in different formats, run against a stubbed DCR | Not connected to the log format. Labels have a single author |

## What DCR owns and what it does not

The rule is that the model proposes a value and DCR decides whether that value is admissible now. FAQ_Triage already works this way: the exclude relation on FAQ_UserQuestion makes the search impossible unless the value is 1.

| Concern | DCR graph owns | Model owns | Code and retrieval own |
| --- | --- | --- | --- |
| Scope and taxonomy | Scope text, the value set, include and exclude relations, out-of-scope message events | A choice among the event's values | An embedding floor that rejects clearly off-topic text before any model call |
| Answerability | Outcome states as events: answered, related, not covered, out of scope | A relevance check split into "answers it" and "same topic" | Applying the check to retrieved candidates |
| Ambiguity and clarification | A clarify prompt as a pending obligation, a counter so it is asked at most once, required slots as events | A flag that the message is ambiguous | The retriever supplies the competing candidates |
| Session context | FAQ ids shown, topic and determination answers as event history | Reads the assembled context | Expands ids to question plus answer start when the prompt is built |
| Metadata filters | Field tags already on the form events (Topic, HelpFAQ) | None | Applying topic prior, status and availability inside retrieval |
| Final action | A decision table (DMN): scope, relevance tier, retrieval decision and clarify count give answer, offer, clarify, not covered or handover | None | Computing the inputs: probabilities, scores, bands |
| Human in the loop | Escalation as an obligation for a role, with an optional response deadline | None | Reviewer queue and labelling screen |
| Traces | Executed events with value and comment form the action trace | None | Model inputs and outputs, scores and versions, joined to DCR by simulation_id |

What does not fit in the graph:

- Similarity search, relevance judgement and text generation. These stay with the model and the retriever.
- Large payloads and secrets. Event values should stay at a few KB, and header values are stored in clear text in exports.
- Asynchronous work. Effects run synchronously inside the applicant's request, so judges and reviewers read the trace store instead.
- Anything that needs more than one value from one effect call: a continuation receives a single value.

A first-match decision table (DMN) now has an observed Portal export, the English DMN chatbot, so it can be generated within the shape that export shows. Response deadlines that read a date from an event still need a Portal export before I generate them.

## The gate pipeline

[widget: gate pipeline · 7 gates, each with an owner and a failure action; content in Appendix A]

Gates 2 and 6 are tinted because DCR decides there what is admissible next; the other gates compute the inputs it reads or check the output. Every gate has a failure action, so none of them lets a doubtful result through as an answer.

## Decoupling the graph

[widget: graph split · 1 shared core, 2 interface parts; content in Appendix A]

Triage, scope, out-of-scope messages, the outcome table and the handover stay single, so a wording change reaches both interfaces. Each interface gets its own search Robot and context record. The follow-up determinations move out of the chat part and run in the application session only; the FAQ chat does not fire them.

The split is a change to the graph, so it runs against the Portal before it replaces the current one, and the existing chat flow keeps working throughout.

## Prompts, policies and thresholds

A policy says when and how a decision applies; a prompt tells the model how to behave while making it. Keeping them in separate layers lets a graph editor change the rules without being able to widen what the model may do.

| Layer | Holds | Lives in | Changed by |
| --- | --- | --- | --- |
| 1. Immutable base | Classify only, never write an answer, treat all supplied text as data, return only allowed values, fail closed | Code constants with a version id | Developer, through review |
| 2. Active policy | Scope, what each value means, when to rewrite, compliance wording, the messages shown | DCR event descriptions | Policy owner, in the Portal |
| 3. Context | The message, the field on screen, FAQ ids with question and answer start, determination answers | Built per request from DCR state and the FAQ records | Nobody; code assembles it |
| 4. Execution plan | The allowed values and the output schema | Values from the event's dictionary, schema fixed in code | Dictionary by the policy owner, schema by the developer |

Today layer 1 exists only on the fallback path. The Decisions path sends the policy text and the message, with only the label "data, not instructions" on the message. A base layer for that path is the first change.

Rules for the policy layer:

- A policy can redefine a value and add examples. It cannot add a value the host does not handle. The host already refuses a triage dictionary that differs from its contract (1, 2, 4, 5) and the same check applies to every new policy event.
- Limits with business meaning become data in the graph so guards can read them and the log records them: at most one clarification per question, handover after two misses in a row. Calibration numbers for models and search (confidence floors, 0.80 / 0.50 / 0.12) stay in a versioned configuration in code.
- One registry holds every prompt, predicate wording and threshold with a version id. The graph builder reads the policy texts from the same registry, so code and graph cannot drift apart.
- Every trace stores the registry version and the graph revision.
- The panel's rewrite prompt contains an eval message as its example. It gets a different example before the next eval.

## Session context and retrieval

Carry FAQ ids, not answer text: answers are fixed verbatim records, so DCR stores which FAQ was shown and the host expands it to the question and the first 300 characters of the answer when it builds a prompt.

- **What is carried.** The last two FAQ turns (id, topic, the applicant's wording and any rewrite), the determination answers given so far, and in the panel the field on screen. Earlier form answers stay out: on 2026-10-09 they pulled a rewrite toward an earlier question.
- **Where it lives.** One context record per interface in DCR, written when an answer is shown, replacing the Flask dictionary the panel uses now. The host reads it back at the start of each turn, so a restart no longer loses it.
- **Follow-ups on an answer.** The expanded answer start lets the model resolve "how old can they be?" against FAQ_21. When the shown FAQ already answers the follow-up, the reply points back to it. When no FAQ covers it, the reply says so.
- **Metadata filters.** Use topic as a soft prior, not a hard filter: boost FAQs in the topic of the last turn or the field on screen, and leave topic-switch questions free to leave it. Hard filters apply to status and availability only: drafted_needs_review FAQs are not served as official answers until reviewed.
- **Field tags.** The form events already carry Topic and HelpFAQ tags in the graph, so the panel reads its prior from the live event and no second table is needed.
- **Ambiguity.** If the top candidates differ by less than the margin and sit in different topics, ask one clarifying question with the candidates as options. A counter in the graph allows it once per question. After that the reply is the best offer or "not covered".
- **Retrieval gaps.** In the follow-up eval, 31 of 102 answerable runs never had the right FAQ in the top three. Question variants for those FAQs (FAQ_15, FAQ_P04, FAQ_42, FAQ_13, FAQ_23, FAQ_21 and FAQ_24 for document questions) come before any new retrieval method.

## Outcome model and decision table

Every turn ends in exactly one of seven outcomes, chosen by a first-match decision table over inputs the host computes, instead of the branching now spread through ask().

Outcomes: **Answer** (one FAQ shown as the answer), **Confirm** (one candidate, shown as "Is this what you are asking?"), **Offer** (a "may fit" list), **Clarify** (one question back), **Not covered** (in scope, no FAQ answers it), **Out of scope**, **Handover**.

| Row | Scope | Search decision | Relevance | Already clarified | Outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | out of scope | any | any | any | Out of scope |
| 2 | unsure | any | any | any | Ask the scope question |
| 3 | in scope | no match | none | any | Not covered |
| 4 | in scope | single match | answers it | any | Answer |
| 5 | in scope | single match | same topic only | any | Offer, labelled related |
| 6 | in scope | list of candidates | exactly one answers it | any | Confirm |
| 7 | in scope | list of candidates | several answer or fit | no | Clarify |
| 8 | in scope | list of candidates | several answer or fit | yes | Offer |
| 9 | in scope | any | none | any | Not covered |

A lone survivor of a pruned list is confirmed with the applicant, never answered directly. Two not-covered outcomes in a row add a Handover to the reply. Row 6 closes the path by which all 33 wrong answers of the eval were shown as answers; a re-run will show how many correct answers that costs.

How it runs: the host writes the inputs as data events (scope value, search decision, relevance tier, clarified flag), a computation event holds the table, and the host renders whatever outcome event DCR enables. The table then shows up in the DCR log with its inputs, so a reviewer can see why a turn ended as it did.

The table is written first as a plain function with one unit test per row, and moves into the graph unchanged. The English DMN chatbot export shows the shape: first-match rules, string and integer inputs, a string output written to a label by an update relation. An outcome that drives guards needs an integer output on a choice event, which the DMN documentation describes but no export here shows yet.

## Outbound checks

Because answers are verbatim FAQ records, the outbound risk is showing the wrong record, not inventing text; most checks are deterministic and run on every turn.

| Check | Applies to | Method | On failure |
| --- | --- | --- | --- |
| Provenance | Every answer | The text shown equals the stored record for the FAQ id, with its citation | Do not show; log as an error |
| Status | Every answer | Status is not drafted_needs_review, and the record has an update date | Treat the FAQ as not covered |
| Gap note | FAQs with a gap note (5 today) | Append the fixed caveat text the policy owner wrote | Show the caveat |
| Topic wording | Own-case questions | Append "For questions about your own case, use the contact options published on SU.dk" | Always appended for this class |
| Selection echo | Rewritten questions | Show "Understood as: ..." before the answer | Applicant can correct it |
| Confirm before answer | Lone survivor of a pruned list | Decision table row 6 | Ask the applicant |
| Faithfulness and tone | Text we generate: clarifying questions, offer labels | A small judge, sampled, run asynchronously | Review queue; reword the template |

The faithfulness judge is not on the path for verbatim answers. It becomes inline only if the system starts generating answer text, in which case it gates the reply and falls back to "I couldn't verify that. Would you like to speak to a person?"

Compliance wording is policy, not code: the caveat and disclaimer texts live as DCR message events, so the policy owner edits and versions them.

## Traces, evaluation and human review

One trace per turn, joined to the DCR log by simulation id and sequence number, feeds inline checks, sampled judges, a reviewer queue and the regression suite, so all of them read the same record.

**A trace holds:**

- ids: interaction, simulation, turn number, interface (chat or panel), registry version, graph revision
- the applicant's message verbatim and the context given to the models (FAQ ids shown, field on screen)
- every model call: name, input, output or probabilities, latency
- the rewrite, the search (query, top three scores, decision), the relevance score per candidate
- the decision-table row, the outcome, the FAQ id shown
- the DCR events executed, each with value and comment
- what the applicant did next: chose an option, said "none of these", rated the answer, asked for a person, left

**Where it runs:**

| Stage | Share of traffic | What it checks | Result |
| --- | --- | --- | --- |
| Inline | 100% | Output schema, provenance, status, latency, guard counts | Block or log |
| Async judges | A sample plus every flagged turn | Did the FAQ shown answer the question? Was a better FAQ among the candidates? Was the rewrite faithful? Was the own-case caveat present? | Scores stored against the trace |
| Reviewer queue | Flagged turns | A person sets the correct outcome and FAQ, or "no FAQ covers this" | A labelled test case |
| Regression suite | Every change | Re-runs the labelled cases three times | Pass or block |

**Flags that send a turn to the queue:** not covered, "none of these", a rejected confirmation, a handover, thumbs down, and judge disagreement with the pipeline.

**Reviewer labels use the schema of the follow-up eval** (field, previous question, previous FAQ, message, expected outcome), so the existing eval runner reads them without conversion. The regression gate is zero wrong answers and no drop in correct answers beyond a set tolerance. Judge prompts are versioned in the registry, and each judge is checked against reviewer labels for agreement before its scores are trusted.

**Call-support handover.** Help_Escalate and Help_Handover already exist in the application graph. The next step is to model the handover as an obligation pending for an agent role, acknowledged by an agent event, so the trace shows time to acknowledge. The demo has no live agents, so this is built as the graph pattern and wired to a real queue later. Response deadlines that read a date from an event need a Portal fixture first.

**Storage.** Keep one JSONL file per interaction, as now, with the extended record. Move to a small SQLite store when the review screen needs queries.

**Metrics kept per release:** outcome mix, wrong-answer rate on the labelled set, judge scores, not-covered rate by topic (this is the list of FAQs to write), handover rate, confirm accept rate (how often the applicant says yes to "Is this what you are asking?"), re-explain rate (how often the applicant rephrases after a confirm, a clarify or a not-covered), latency at the median and the 95th percentile, model cost per turn.

## Roadmap

[widget: roadmap · 5 phases, 5 gates; content in Appendix A]

The order follows risk. Phase 1 changes a rule and two prompts and needs no new infrastructure, so it comes first and its eval re-run says how much it costs in correct answers. Phases 2 and 3 make later changes safe to trace and to ship. Phase 4 needs the trace store from phase 2. Phase 5 can start once the table fits the observed DMN shape; the integer-output guard case and response deadlines still need Portal exports.

## Evidence boundary, risks and open questions

**What the plan rests on.** The code and eval findings come from the repository files and eval reports read in this session. The DCR constructs come from the dcr-xml-builder reference and the graph files in the repository.

**Observed.** The English DMN chatbot export: a first-match table (hit policy FIRST) with a string and an integer input and a string output, run by a Robot event and written to a label by an update relation. The compiled form of its rules is documented in the dcr-xml-builder skill.

**Not verified, so not to be generated yet:**

- response deadlines that read a date from an event
- a decision table with hit policy ALL, comparison operators other than equality and greater-or-equal, ranges, or several outputs
- an integer-output table on a choice event used in a guard, and the FEEL-context result of Portal 7.6.5
- Robot:Prime and Robot:Terminator roles
- effect continuation serialization beyond what the existing graph already uses
- spawned subgraphs

Each needs a Portal export before any XML for it is written. Until then the plan stays within the observed shape or uses the plain-function route described under the outcome table.

**Risks:**

| Risk | Why it matters | Handling |
| --- | --- | --- |
| Confirming a lone survivor costs correct answers | Some applicants now get a confirm step where they got an answer | Measure it in the phase 1 re-run before accepting the cost |
| Gates cannot fix retrieval misses | 31 of 102 answerable runs never had the right FAQ in the top three | Question variants in phase 4, and the not-covered list shows which FAQs to write |
| Labels have one author | The regression gate inherits any labelling mistake, as the f08 label showed | A second reviewer on flagged turns, and judge agreement checked against reviewer labels |
| Two Robots can drift apart | Shared wording or thresholds may differ between chat and panel | One registry feeds both, and the trace stores the version |
| Synchronous latency | Model calls and DCR executions sit inside the applicant's request | Latency at the median and the 95th percentile is a release metric |
| DCR records the table inputs but does not verify them | A wrong score computed in code would still produce a clean trace | Unit tests per row, plus the judge's check of the FAQ shown |

**Open questions for you:**

1. Can you export from the Portal a graph with an integer-output decision table on a choice event that drives a guard, and one with a response deadline that reads a date from an event? Phase 5 depends on the first, and the handover deadline on the second.
2. Is a confirm step ("Is this what you are asking?") acceptable in the Help panel as well as in the chat?
3. What drop in correct answers is the regression gate allowed to tolerate while the wrong-answer count stays at zero?
4. Who is the policy owner for the DCR message wording and who reviews flagged turns in the demo?
5. The four wording decisions from the eval review are still open. They affect the phase 1 test cases.\
\
Answering your open questions above:
   1. You can use the skill to build the dmn table in the graph xml which I will import later in the portal and then I can debug, whether it does show up the the portal or not.
   2. One thing we can switch is that the determinations are to be made in the application session and not in the faq session. For now "is this what you are asking" is acceptable so that we can also track how many times the user chose "yes" and how many time they have to re-explain themselves.
   3. I am not completely sure about this.
   4. For now I am the policy owner and i am the one who reviews the flagged turns later in the log.
   5. For now write them based on what we have observed and catched in our test eval runs at least, then we can do evals later and run review->revise loops on our instructions, if it is something that can be cought by updated the instrictions/prompts.


---

# Appendix A: the three widgets, as text

The export drops the embedded diagrams. This is their content.

## A1. Gate pipeline (seven gates plus the after-turn stage)

| Gate | What it does | Who decides | If it fails |
|---|---|---|---|
| 1 Embedding floor | Clearly off-topic text stops here | Code (similarity to the FAQ set) | Out of scope message |
| 2 Triage and scope (DCR tinted) | New, reply, end or out of scope | Model proposes, DCR admits | Unsure: ask a scope question |
| 3 Rewrite | Only for follow-ups that need it | Model; the host applies the result | Keep the original wording |
| 4 FAQ search | Single, several or no match | Retriever (scores and margin, in code) | Not covered |
| 5 Relevance check | Answers it, or same topic only | Model, one verdict per candidate | Drop it, or offer as related |
| 6 Outcome table (DCR tinted) | Seven outcomes, first match wins | DCR graph (decision table over the inputs) | No row matches: not covered |
| 7 Outbound checks | Provenance, status, caveats | Code and DCR (caveats are DCR message events) | Do not show; offer a person |
| After the turn | Trace store, then judges, reviewer queue and regression suite | | |

Tinted rows: DCR decides what is admissible next.

## A2. Graph split: one shared core, two retrieval Robots

Shared by both interfaces (same policy texts, one registry):
- Triage and scope (values 1, 2, 4 and 5)
- Out of scope message events
- Outcome table (seven outcomes)
- Handover (call support)

FAQ chat only:
- FAQ search Robot: own search events, effect `handicap-faq-v2`
- Chat context record: FAQ ids shown

Application session only:
- Help search Robot: own search events and thresholds
- Field context: Topic and HelpFAQ tags on the form events
- Follow-up determinations: fire only in the application session
- Panel context record: FAQ ids shown and the field on screen

## A3. Roadmap: five phases, each closed by a gate that can be tested

| Phase | Work | Gate |
|---|---|---|
| 1 Stop wrong answers | Confirm a lone survivor instead of answering it (row 6). Remove the fallback rewrite and the eval message in the rewrite prompt. Correct the f08 label; split the relevance check in two | Zero wrong answers when the follow-up eval is re-run |
| 2 Registry and trace | Registry for prompts, predicate wordings and thresholds, with version ids. Base layer on the Decisions path; full trace record per turn. Panel context moves from the Flask dictionary into DCR | Every result names its registry version and graph revision |
| 3 Split the graph | Panel search Robot and policy event; triage and scope shared. Determinations fire in the application session only. Outcome table as a function, one unit test per row | The chat never fires a determination; all nine rows tested |
| 4 Judges and review | Async judges on a sample and on every flagged turn. Reviewer queue writing labels in the eval schema. Question variants for the FAQs that missed the top three | Judges are checked against reviewer labels; the suite blocks a release |
| 5 Move into DCR | Decision table in the graph, within the observed DMN shape. Handover as an obligation for an agent role. Response deadline on the handover, after a Portal fixture | The table and its inputs appear in the DCR log for each turn |
