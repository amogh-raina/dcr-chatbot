# Historical project notes through 2026-10-12

Archived from CLAUDE.md during the 2026-11-13 review. These notes include superseded instructions, graph IDs, commands and test counts. Use [AGENTS.md](../../AGENTS.md) and [README.md](../../README.md) for current guidance.

# Agent orientation

Read `README.md` for setup, "Repository layout" below for where everything lives, and `docs/architecture/Overview.md` for current architecture and endpoints. **Next task: run and act on the Help panel follow-up eval; read `docs/handoffs/HANDOFF_2026-10-09_followup_eval.md` first**, then "Session 2026-10-09 (summary)" and "Application help panel (2026-10-08, current state)" below. UI work: `docs/handoffs/UI_HANDOFF.md` (partly done on 2026-10-09). Live graph: **2014078** (tested 2026-10-08). The graph file was rebuilt on 2026-10-09 (`FAQ_Welcome`); re-import it for the new welcome text, see "FAQ chat changes (2026-10-09)".

- The primary chatbot is Flask (`app.py`), with FAQ presentation in `dcrai/chat/faq_runtime.py` and OpenAI ranking in `dcrai/llm/openchat.py`.
- DCR controls all runtime events, answers and navigation. Do not introduce an XML-derived runtime FAQ map.
- The main UI is `templates/index.html` + `static/script.js`; `demo-ui` is the React/Vite showcase using the same FAQ API flow (chat component: `demo-ui/src/SupportChat.jsx`). Rebuild it into `static/demo` after UI edits.
- The simulated login/application demo (`/mitid`, `/application` routes, `demo-ui/src/ApplicationDemo.jsx`) is driven by `dcrai/application/application_runtime.py` via `/application/init` and `/application/answer`. Same rule as FAQ: it reads only live DCR events (labels, types, choices, pending state, descriptions, tags) — no local XML. The form flow uses no LLM; the Help panel uses LLM classifiers only as described below. It runs its own DCR simulation, separate from the FAQ session, though both hang off the same `X-Session-ID`.
- File-upload fields in the application demo are simulated: a filename is recorded as text in DCR, never actually read or uploaded. Don't "fix" this into a real upload without being asked — see `docs/guides/APPLICATION_DEMO.md`.
- Only `external_scripts/graph_parser.py` and `__init__.py` are shared from that folder. The parser is review-only and uses standard-library dependencies; legacy LLM/explanation scripts remain excluded. The app also handles a missing parser.
- Never commit `.env`, logs, caches or excluded review material. Do not read `.env` to troubleshoot without explicit user authorization.
- Run `python -m unittest discover -s tests` for focused checks. Keep browser/live testing brief unless requested.

## Repository layout (restructured 2026-10-10)

Behaviour-preserving restructure so the pilot is easy to maintain and map. No model input, graph or API changed.
Specs and later work are written against this layout.

```
app.py                  Flask entry point (the only Python file at the root)
dcrai/                  application package
  paths.py              where every folder lives; change a location here, nowhere else
  prompts.py            loads prompts/*.txt; prompts.version() hashes all wording
  dcr/dcr_repository.py DCR REST calls
  llm/                  openchat.py (ranking, form interpretation), retrieval_llm.py (triage, relevance, follow-up, rewrite, Decisions API)
  chat/                 faq_runtime.py (Lean/Structured FAQ flow), retrieval_runtime.py (Clean graph FAQ chat)
  application/          application_runtime.py (application form flow and Help panel)
  observability/        interaction_log.py
  legacy/               chatnlp.py, questions.py, utility.py (older non-FAQ helpers, used by app.py and tests)
prompts/                every model instruction as a text file, by area (README.md lists them)
  base/ judges/         reserved: immutable base layer, LLM-judge instructions (empty)
evals/                  runners (python -m evals.<name>), cases/, runs/, reports/ (README.md)
traces/                 interactions/ (JSONL per interaction), runtime/ (DCR snapshots); gitignored
faq_search/             retriever.py, api.py, build_faq_data.py, embed_faq_data.py, data/ (records and embeddings only)
docs/                   architecture/, guides/, handoffs/, sources/, specs/, local/ (README.md)
scripts/                one-off diagnostics
tests/                  unit tests, never call a model
xml graphs/  tools/     DCR graph files and graph builders/probes (both gitignored, see flagged items)
demo-ui/ static/ templates/ external_scripts/ .agents/   unchanged
```

**Where new things go**
- A model instruction: `prompts/<area>/<name>.txt`, loaded by name with `prompts.get`. Never inline wording in Python. Policy text for a decision belongs in the graph (DCR event description), not here.
- A path to a folder or data file: `dcrai/paths.py`.
- An eval: runner in `evals/`, inputs in `evals/cases/`, outputs in `evals/runs/` and `evals/reports/`. Record `prompts.version()` with results.
- A doc: the matching `docs/` folder. A handoff: `docs/handoffs/HANDOFF_<date>_<topic>.md`. Specs: `docs/specs/`.
- Anything the running system records: `traces/`, through `paths`.
- A Python module: the matching `dcrai/` sub-package. Import as `from dcrai.chat import faq_runtime` or `import dcrai.llm.retrieval_llm as llm`.

**Old to new**

| Was | Now |
|---|---|
| `dcr_repository.py` | `dcrai/dcr/dcr_repository.py` |
| `openchat.py`, `retrieval_llm.py` | `dcrai/llm/` |
| `faq_runtime.py`, `retrieval_runtime.py` | `dcrai/chat/` |
| `application_runtime.py` | `dcrai/application/application_runtime.py` |
| `interaction_log.py` | `dcrai/observability/interaction_log.py` |
| `chatnlp.py`, `questions.py`, `utility.py` | `dcrai/legacy/` |
| `diagnose_application_entry.py` | `scripts/diagnose_application_entry.py` |
| `faq_search/eval_followups.py`, `eval_composed.py`, `calibrate_thresholds.py`, `diagnose_queries.py` | `evals/` (run with `python -m evals.<name>`) |
| `faq_search/data/eval_queries.json`, `eval_composed_queries.json`, `eval_followup_queries.json` | `evals/cases/` |
| `tools/decisions/triage_labels.json` | `evals/cases/triage_labels.json` |
| `faq_search/data/eval_scores.json`, `eval_scores_query.json`, `followup_results.json` | `evals/runs/` |
| `faq_search/data/calibration_report.md`, `composed_report.md`, `followup_report.md` | `evals/reports/` |
| `interaction_logs/` | `traces/interactions/` |
| `runtime_traces/` | `traces/runtime/` |
| `Overview.md`, `XHAIL.md`, `INTEGRATION_PLAN.md` | `docs/architecture/` |
| `DEPLOY.md`, `APPLICATION_DEMO.md` | `docs/guides/` |
| `UI_HANDOFF.md`, `NEXT_SESSION.md`, `HANDOFF_2026-10-09_followup_eval.md` | `docs/handoffs/` |
| `SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md`, `Question_upmapping_chatbot.docx` | `docs/sources/` |
| `FAQ_GRAPH_REVIEW.md`, `FAQ_SMOKE_RESULT.md`, `faq_inventory_v1.md`, `idea.md`, screenshots, `dcr-xml-builder.skill`, `external_scripts/SU-Handicap-report.md` and its png | `docs/local/` (gitignored) |
| Prompt constants in `retrieval_llm.py` and `openchat.py` (`ROUTE_PROMPT`, `RELEVANT_PROMPT`, `FOLLOWUP_PROMPT`, `TRIAGE_META`, `REWRITE_PROMPT`, `PANEL_REWRITE_PROMPT`, `SYSTEM_PROMPT`, `INTERPRET_PROMPT`) and the six inline Decisions API question instructions | `prompts/**/*.txt`. The constants still exist in the same modules and now load the files, so callers are unchanged |

The full move list is in `docs/local/restructure-2026-10-10-moves.tsv`; a tar of the tree before the change is `docs/local/backup-before-restructure-2026-10-10.tar.gz` (both gitignored). Nothing was committed; the working tree already held uncommitted work, so use `git add -A` to let git detect the renames.

**Restructure log (2026-10-10)**
1. Backed up the tree and captured the exact text of every model instruction (13 items: 8 constants, 4 groups of Decisions API question instructions, and the graph's triage policy) before touching anything.
2. Moved markdown, eval files, traces and Python modules as in the table above. Added `dcrai/paths.py` and `dcrai/prompts.py`.
3. Rewrote imports (every `import x` and `from x import` of a moved module), path constants (`RECORDS_PATH`, trace folders, `build_faq_data.py` inputs, eval case and report locations), `.gitignore`, `.dockerignore`, `.env.example`, and the file references and run commands in `README.md`, this file and the moved docs.
4. Extracted 14 instructions to `prompts/` straight from the captured text (written by a script, not retyped).
5. Added READMEs: `docs/`, `prompts/`, `evals/`, `traces/`, `docs/specs/`.

**Verified**
- Tests: 228 passed, 5 failed, 1 skipped, 493 subtests passed, identical to the baseline before the change. The 5 failures are all in `tests/test_faq_retriever.py` and need `sentence_transformers`, which is not installed here (same before and after).
- Prompts: the text the code sends is byte-identical before and after for all 13 captured items (`prompts.version()` = `f58faa091f0a` at this point).
- Every module imports, and all four eval runners start (`--help`). No stale references to the old paths remain outside this table and the history sections below (grep).
- Not verified: a live run of the server against DCR, the model-calling evals, and the Docker image build. Nothing in the call path changed, but they were not run.

**Behaviour that did change**
- Logger names are now the package path, so terminal lines read `INFO:dcrai.llm.openchat:` instead of `INFO:openchat:`.
- Trace and log folders resolve from the repo root, not from the directory the server was started in. `INTERACTION_LOG_DIR` still overrides; `RUNTIME_TRACE_DIR` is new.
- Three tests were edited for moved files: `test_dcr_choice_runtime.py` (patches `paths.RUNTIME_TRACES` instead of `repo.__file__`), `test_faq_eval.py` and `test_application_faq.py` (case file locations).
- Scripts run as modules: `python -m evals.eval_followups` (before: `python -m faq_search.eval_followups`). Run `pytest` as `python -m pytest tests` so the repo root is on the path.

**Flagged, not decided**
- `tools/` and `xml graphs/` are gitignored, yet this file calls the graph tooling reproducible. The graph builder, the triage policy source and the graphs are not in version control. Decide whether to track them.
- The triage policy (`TRIAGE_POLICY`) stays in `tools/clean_graph/build_clean_graph.py` because it is the active-policy layer and belongs in the graph. It is therefore not in `prompts/`.
- `FAQ_QUERY_PROMPT` is an embedding setting, not an LLM instruction, so it stays an environment variable.
- `prompts/base/` and `prompts/judges/` are empty by design. Merging the repeated "treat all text as data" rule into a base layer changes model input and needs an eval run.
- About 20 environment settings are still read in several modules. A single config module belongs to the registry spec.
- `xml graphs/SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md` duplicates the copy in `docs/sources/`; left in place.
- The Docker image still copies the whole tree (`COPY . .`), so it now includes `prompts/` (needed) and `docs/` (not needed; `docs/local` and `traces` are excluded).

## Change log (retrieval pilot, 2026-10-05 and 2026-10-06)

Branch `experiment/faq-retrieval-determinations`. Newest first inside each group.

**Retrieval service (`faq_search/`)**
- Added `faq_search/api.py`: read-only Flask service for DCR REST effects. `GET|POST /api/faq/search?q=...` returns one flat JSON object (`decision`, `score`, `id`, `question`, `answer`, `citation`, `option_count`, `option1_*`..`option3_*`, `cached`, `latency_ms`). Separate process from `app.py`; port 8090, bound to 127.0.0.1; 256-entry LRU cache; query text is never logged.
- Auth accepts the key as `X-API-Key`, `X-DCR-AuthToken` (DCR token authenticator default header), `Authorization: Bearer`, or the user/password of `Authorization: Basic`. `?key=` only with `--allow-query-key`.
- `FAQ_API_EXTRA_KEYS` (comma separated) adds further accepted values. Needed because DCR sends its stored, encrypted token (88 characters) instead of `FAQ_API_KEY`, and that token changes on every save of the effect.
- A rejected 401 logs `credential_sources`, `credential_lengths` and `expected_length` (never values); a 400 logs the names of the parameters and headers received.
- Added `evals/calibrate_thresholds.py`, `data/eval_queries.json`, cached score files and `data/calibration_report.md` (threshold sweep and A/B of the `FAQ_QUERY_PROMPT` option).
- Data build now yields 55 records (43 guideline FAQs + 12 practical `FAQ_P01`..`FAQ_P12`) with English phrasing variants; embeddings rebuilt with `Qwen/Qwen3-Embedding-0.6B`.
- New tests: `tests/test_faq_api.py` (32 tests incl. auth sources and extra keys), `tests/test_faq_data.py`, `tests/test_faq_eval.py` (needs `RUN_RETRIEVAL_EVAL=1` and the model).

**DCR graph and effect**
- Graph in use: `xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml` (the Clean retrieval graph without the effect element; the effect is attached in the Portal). Built from `..._Application_Structured.xml`; `Form0` subprocess is unchanged. No menu, answer or explored events, no pre-modelled Q&A pairs. See `docs/architecture/Overview.md` section 3b.
  - `FAQ_UserQuestion` (input), `FAQ_Retrieve` (the only Robot, carries effect `handicap-faq`), System continuations `FAQ_RetrievalOk` / `FAQ_RetrievalFail` / `FAQ_RetrievalTimeout`, message `FAQ_RetrievalUnavailable`.
  - `FAQ_DeterminationSelector`: one choice event. Items 1 to 4 are the canonical questions of FAQ_05b, FAQ_09, FAQ_31, FAQ_42 and open `Det05b`/`Det09`/`Det31`/`Det42` (Ask yes/no, then Yes or No outcome). There is no application item (removed 2026-10-08).
  - Validated with `validate_dcr_xml.py` (0 errors, 0 warnings) and a local simulation of the relations.
- Deleted on 2026-10-06 as unused: `..._Retrieval_Pilot.xml`, `..._Retrieval_Pilot_NoEffect.xml` (first pilot with the old menus and answers) and the with-effect `..._Retrieval_Clean.xml`. The with-effect variant can be regenerated with `python tools/clean_graph/build_clean_graph.py --with-effect`; by default the script writes only the NoEffect file.
- Effect `handicap-faq` is registered in Portal **Effect Administration**: `Http.Get`, URL `https://<tunnel>/api/faq/search?q=$(q)`, token authenticator (header `X-DCR-AuthToken`), outputs 200-208 ok (json, whole body), 408/504 timeout, everything else fail. It must be ticked in the **Use** column, then imported under the graph's Effects. Test, Staging and Production "Configure parameters" forms are empty for this effect, nothing to fill in.
- Findings worth keeping:
  - On the Robot, parameters of type `text` take the event ID (`q` = `FAQ_UserQuestion`), not `$(...)`. Only the effect's own URL uses `$(q)`.
  - The Portal rewrites the token authenticator header to `X-DCR-AuthToken` on save, and re-encrypts the token.
  - `Http.Get` output is visible in Test Effect only when the ContinueOn fields are empty; in a graph it lands in the System event `FAQ_RetrievalOk`, which the simulator task list hides.
  - Quick-tunnel URLs change on every `cloudflared` restart; update the effect URL and save each time.
  - The XML serialization of an effect on an event is unverified. Ask for a Portal export of the attached graph before relying on the effect element of the `--with-effect` variant.

**Graph tooling (repo, reproducible)**: `tools/clean_graph/build_clean_graph.py` regenerates the Clean NoEffect graph (add `--with-effect` for the variant carrying the unverified effect element) from `xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml` (never edits it); `tools/clean_graph/determinations.json` holds the yes/no texts of FAQ_05b, FAQ_09, FAQ_31, FAQ_42; `tools/clean_graph/simulate_clean_graph.py "<graph.xml>"` runs the local relation checks. Run from the repo root: `python tools/clean_graph/build_clean_graph.py`, then validate and simulate. Edit the graph through the script, not by hand, so the two files stay in step.

**Docs**: `docs/guides/DEPLOY.md` (sections 3, 4, 5, 7), `docs/architecture/Overview.md` (sections 2, 3b, 5, 7), `docs/guides/APPLICATION_DEMO.md` (Run, retrieval pilot note) and this file were updated.

## Retrieval chat (2026-10-07)

`app.py` picks the flow per graph: if the live events contain `FAQ_UserQuestion`, `/init` and `/chat` use `dcrai/chat/retrieval_runtime.py`; otherwise the Lean/Structured flow (`dcrai/chat/faq_runtime.py`) is unchanged. UI: `demo-ui/src/SupportChat.jsx` (`RetrievalReply`), rebuilt into `static/demo`.

- **Graph** (`tools/clean_graph/build_clean_graph.py`): adds `FAQ_Scope` (scope text, read for the welcome and the LLM scope check), `FAQ_OutOfScope` and `FAQ_NoMatch` (message labels the host executes). Effect is now `handicap-faq-v2`. `--with-effect` writes `..._Retrieval_Clean.xml` with the effect attached in the Portal-export shape (quoted continuation IDs, no API key: set `header#X-API-Key` as `"<key>"` on the Robot after import). No `ApplicationStart:` tag and no entry event: the application is a separate session (see below).
- **Flow per typed message** (`retrieval_runtime.handle`): `retrieval_llm.route` classifies it against the scope text from DCR and the prompt on screen: `out_of_scope` (execute `FAQ_OutOfScope`, Robot not run), `new_question` (execute `FAQ_UserQuestion`; the Robot runs the effect), `reply` (value restricted to the prompt's options), `apply`, `end`. After retrieval, `retrieval_llm.relevant` drops FAQs that do not address the message (none left: execute `FAQ_NoMatch`). One fit: confirm first ("Is this what you are asking?"). Several: options plus "None of these". Answer text and source come verbatim from `FAQ_RetrievalOk`.
- **Follow-up**: after an answer, the selector item is chosen by exact label match, else `retrieval_llm.pick_followup` (items or none; the application item is excluded). The host executes the selector and shows the pending `FAQDetermination` question. Yes/no by button or interpreted text; pending outcomes are shown and acknowledged; a newly pending determination (chain) is asked next. A new question drops an open follow-up quietly. No follow-ups while an application is in progress.
- **Application** (superseded 2026-10-08): the chat no longer runs `Form0` inline; see "The application is never started from the FAQ chat" below. `retrieval_runtime.application_message` / `resume_application` remain from the inline version and are unused by the chat.
- **LLM failures**: router down -> treat as a question; relevance check down -> keep the API result; follow-up pick down -> no follow-up. All logged without message text.
- **Triage as a policy event (graph revision after 2014073):** `FAQ_Triage` (choice 1 question, 2 reply, 4 end, 5 out of scope; there is no 3) carries the routing, scope and rewrite policy in its description. The LLM gets that policy, the event's values, the prompt on screen and the context, picks a value (plus a reply value and, when needed, a standalone `search_query`), and the host executes `FAQ_Triage` with it (reason in the comment). `FAQ_UserQuestion` starts excluded and is only included by `FAQ_Triage = 1`, so DCR blocks a search on any other triage. Graphs without `FAQ_Triage` fall back to `retrieval_llm.route` (policy in code). The value-to-behaviour mapping (1, 2, 4, 5) is a contract in `retrieval_runtime.TRIAGE_INTENTS`.
- **Context lives in DCR:** the host executes `FAQ_Answered` with `"<FAQ id>: <question>"` when it shows an answer. Triage reads it and the last answered `Det*_Ask` (question and yes/no) from the event list. A context-dependent message is rewritten into a standalone question; that is what `FAQ_UserQuestion` gets (original wording in the comment), and the chat shows "Searching for: ...". The session holds only prompt ids and pending candidate answers.
- **Decisions API (`DECISIONS_ENABLED=1`):** the three classifiers use OpenAI `POST /v1/decisions` (`gpt-6-luna`, plain HTTP via `requests`, no SDK upgrade) with the Responses functions as fallback (`retrieval_runtime.classify`). Triage: a `choice` over FAQ_Triage's values with the graph policy as instructions, a `contextual` predicate, and a `reply` choice when a prompt is on screen. Relevance and follow-up pick: one predicate per candidate. Thresholds (env): `DECISIONS_TRIAGE_MIN` 0.6 (below it, with question vs out-of-scope as the top two, the chat asks "Is your question about handicaptillæg?" before executing FAQ_Triage), `DECISIONS_REPLY_MIN` 0.6 (below it the prompt is repeated as buttons), `DECISIONS_RELEVANT_MIN` 0.5, `DECISIONS_FOLLOWUP_MIN` 0.7, `DECISIONS_CONTEXT_MIN` 0.7 (rewrite only when triage=1, DCR holds context and the predicate is at least this; the rewrite itself is a Responses call). The FAQ_Triage comment records `decisions conf=... p=...`. Probe: `python tools/probe_decisions.py`, labelled cases in `evals/cases/triage_labels.json` (2026-10-08: triage 15/15, 110-340 ms warm; a double-negative yes/no reply came back at confidence 0.37).
- **Every triage value is acted on by DCR, not by the host:** 1 includes `FAQ_UserQuestion`; 4 makes `FAQ_Goodbye` pending; 5 makes `FAQ_OutOfScope` pending; 2 only blocks the search (the reply goes to the event already on screen). After executing `FAQ_Triage` the host runs `retrieval_runtime.follow_dcr`: show and acknowledge pending message events, search if `FAQ_UserQuestion` is enabled.
- **The application is never started from the FAQ chat (2026-10-08):** the Start button (and the "Start the application" action) navigates to `/mitid?graphid=...`; the application is a separate session (`/application/init`, its own simulation of the same graph). "I want to apply" is triaged as 1 and answered from the FAQ. The retrieval graph has no relation from the FAQ layer into Form0 and no entry event; Form0 keeps the Structured graph's initial marking (only `Form0:Email` included), and `application_runtime.start` goes straight to the first field when no entry event exists. Reason: the `/simulation/` event list reports `pending: False` for children of the `Form0` subprocess even when the engine holds them pending (probe 2026-10-08: `FAQ_Triage = 3` left Email `pending: False` while its milestone disabled `Form0:A10`), so the application host relies on one-field-at-a-time inclusion (`sole_enabled`). Converting Form0 to `type="form"` is untested (the skill notes form submission semantics must be verified in the host).
- Tests: `tests/test_retrieval_runtime.py` (fake DCR + fake LLM/HTTP, 40 tests).

**Run the retrieval chat test**
1. Import `xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean.xml` (effect attached) or the NoEffect file and attach `handicap-faq-v2` to `FAQ_Retrieve` (`q` = `FAQ_UserQuestion`, `header#X-API-Key` = `"<key>"`, ContinueOn* = `"FAQ_RetrievalOk"` etc.). Note the new graph ID.
2. `DCR_TEST_GRAPH_ID=<id> python tools/probe_simulation_effect.py --ask "what medical documents do i need"` must show `continuation executed: FAQ_RetrievalOk`. Caveat: `--ask` executes `FAQ_UserQuestion` without running `FAQ_Triage = 1` first, so on triage graphs (FAQ_UserQuestion starts excluded) it is blocked until the probe is updated.
3. API + tunnel running (effect URL current), `python app.py`, open `http://localhost:8080/demo?graphid=<id>`.
4. Script: off-topic message (out-of-scope text, no API log line); "refused without assessment" (confirm, answer, FAQ_31 follow-up, answer yes then ask again); "medical documents" (options); "I'm not Danish, can I get it?" then type "yes I work here under EU rules" (interpreted reply); a new question while a follow-up is open (dropped); "I want to apply" (answered as an FAQ question); the "Start the application" button (MitID page, then `/application` with the email field first); stop the tunnel and ask (unavailable message).

## FAQ chat changes (2026-10-09)

Requested by Amogh after live use of the FAQ chat (`/demo`, `dcrai/chat/retrieval_runtime.py`, `SupportChat.jsx`).

- **Welcome**: short onboarding text from a new graph event `FAQ_Welcome` (group `FAQWelcome`; topics, "type your question or pick an example", what it cannot do, "I am still learning"). No mention of follow-up questions. `FAQ_Scope` stays as the scope definition for the triage policy only. `initialize()` reads `FAQ_Welcome`, falls back to `FAQ_Scope` on older graphs (2014078 still shows the old long text until the new graph is imported). The UI no longer shows the "Let's find your answer" intro above it on retrieval graphs.
- **Example questions** are FAQ ids, not free text: `Example:FAQ_01`, `Example:FAQ_21`, `Example:FAQ_P01` tags on `FAQ_Welcome` (fallback `retrieval_runtime.DEFAULT_EXAMPLES`). Chips show the canonical titles (`faq_titles()`, now in `retrieval_runtime`, shared with the application). A click sends `{action: 'example', faq_id}`: the host executes `FAQ_Triage = 1` (comment "example question chosen by the applicant", no LLM triage) and searches the exact title through DCR; if that FAQ comes back it is answered directly, otherwise the normal options are shown. Before, examples were typed text such as "Who can get handicaptillæg?" and landed between FAQ_01 and FAQ_03.
- **Single match answered directly**: no "Is this what you are asking?" step any more (`confirm` prompt kind removed). The answer card shows the matched question, so the applicant sees what was answered. Several matches still give options plus "None of these". Determination follow-ups after an answer are unchanged. The application Help panel still confirms single matches (`faq_confirm`); not changed.
- **No "Do you have another question?"** and no "Start the application / That was all" buttons after answers or determination results (`NEXT_ACTIONS` removed). The green "Start the application" button under the chat is the only way to the application.
- **Idle end**: `SupportChat.jsx` `IDLE_SECONDS = 120`. The timer restarts on every turn; when it fires the UI posts `{action: 'end', reason: 'idle'}`. The host executes `FAQ_Triage = 4` (comment "idle timeout (no activity)"), which makes `FAQ_Goodbye` pending; `follow_dcr` shows and acknowledges it. The UI then shows "This chat ended after 2 minutes without activity." with "Start a new chat"; the composer is disabled, the Start button stays usable. A typed goodbye (triage 4) ends the chat the same way ("This chat has ended."). No reminder messages.
- **Paragraph spacing** in the chat answer box fixed (`.answer-card p + p`).
- Graph rebuilt (`build_clean_graph.py --with-effect`): validator 0 errors, simulator 0 failures (new checks: welcome text, three examples, no relations). Form0 untouched. **Re-import needed** for the new welcome; on import set `header#X-API-Key` on `FAQ_Retrieve` again (quoted) and note the new graph id.
- Tests: `tests/test_retrieval_runtime.py` updated (direct answers, no actions after answers) and new tests for welcome event, examples, example fallback, idle end. Full suite 199 run; only the two model-dependent modules fail as before.
- Preview: `demo-ui/preview/preview.mjs` mocks the new welcome shape and the idle end (fast-forwards the browser clock 121 s; screenshot `*-faq-3-idle-ended.png`).

## Application help panel (2026-10-08, current state)

Questions asked *during* the application (`/application`, after MitID) are answered in a Help side panel by the retrieval search, inside the application's own DCR simulation. No follow-up determinations here (they stay in the FAQ chat). Tested offline (fake DCR, mocked UI) and **live on graph 2014078 on 2026-10-08: works as intended** (Amogh).

**Graph** (`xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean.xml`, built by `tools/clean_graph/build_clean_graph.py --with-effect`; validator 0 errors, simulator 0 failures)
- Form0 fields: `eventDescription` = reviewed help text + what each option means (source `tools/clean_graph/field_help.json`, review page `claude/field_help_review.md` in the claude.ai project, approved by Amogh). Groups `Topic:<topic>` and `HelpFAQ:<FAQ id>` (live event list: `tags`). A2 option labels Physical/Neurological/Visual/Hearing/Mental/Other (were `item 1`..`item 6`; values unchanged).
- Form0 relations (63) and initial marking (only `Form0:Email`) are identical to the Structured graph (checked by script). No relation from the FAQ layer into Form0.
- New: `Help_Escalate` (choice 1 asked for a person, 2 no usable answer, 3 deadline/appeal, 4 frustrated/anxious) -> response -> `Help_Handover` (message pointing to SU.dk contact options; no stored contact details, per FAQ_P02).

**Backend flow** (`dcrai/application/application_runtime.py`, endpoints installed by `install()`; one lock per request; every FAQ step checks `application_marking` before/after and raises if Form0 changed)
- `/application/init`, `/answer`, `/interpret`, `/edit`: unchanged field flow. `describe()` now adds `field.help = {html, topic, related[{id, question}]}` from the live event (description + tags); related titles come from `faq_search/data/faq_qa_records.json` (titles only).
- `/application/ask {message | related, scope?}`:
  1. `related=<FAQ id>` (a related question clicked on the card): search its title.
  2. "talk to a person" wording -> `escalate(1)` and return `status: handover` (no search). Deadline/appeal words -> `escalate(3)` once per session, search continues.
  3. `scope='field'` (applicant clicked "Unsure about this question?"): search the typed words; if none of the field's `HelpFAQ` FAQs is shown, search again with `"<field label> <message>"` (DCR comments `field-typed` / `field-composed`).
  4. No scope and `DECISIONS_ENABLED=1`: one Decisions call `retrieval_llm.panel_signals_decisions` -> `distress` >= `DECISIONS_DISTRESS_MIN` (0.7) -> `escalate(4)`; `contextual` >= `DECISIONS_CONTEXT_MIN` (0.7) and context exists -> `retrieval_llm.rewrite(..., PANEL_REWRITE_PROMPT)` (context: field on screen, `FAQ_Answered`, last 6 answers). Without Decisions: plain search, no classifier.
  5. Search = host executes `FAQ_Triage = 1` (comment "explicit question during the application"; no LLM triage), then `retrieval_runtime.search`: `FAQ_UserQuestion` (value = query, comment = original wording) -> Robot `FAQ_Retrieve` runs effect `handicap-faq-v2` -> `FAQ_RetrievalOk` JSON (or `FAQ_RetrievalUnavailable`) -> relevance post-check (`classify('relevant')`, LLM classifier; keeps the result if the LLM is down).
  6. Returns `faq_confirm` / `faq_clarify` (`match_id`, `candidates[{candidate_key = FAQ id, question}]`), `faq_no_match` (text of `FAQ_NoMatch`), `faq_unavailable`; plus `searched_for` when the query differs from the message and `handover {reason, html}` when one fired. Two misses in a row (no match or "None of these") -> `escalate(2)` once.
- `/application/confirm {match_id, candidate_key}`: `candidate_key='none'` counts as a miss (`faq_none`). Otherwise the answer is shown verbatim from the retrieval candidate (`faq_response` HTML, `faq_citation`, `faq_id`), `FAQ_Answered` is executed with `"<id>: <question>"`, miss counter reset, application view returned with a new prompt ticket.
- `/application/handover {}` (button): `escalate(1)` always. `escalate()` executes `Help_Escalate` (value = reason, comment = signal), reads and acknowledges the pending `FAQHandover` event, returns its description. Older graphs without the events: no handover, normal behaviour.
- `/application/interpret`: an unreadable answer is never treated as a question any more; the same field unreadable twice -> `escalate(2)` once.
- Logs: decisions, ids, reasons; never question or answer text (tested).

**UI** (`demo-ui/src/ApplicationDemo.jsx`, `HelpPanel`; bundle `static/demo/assets/index-DI0BF8eK.js` + `index-C22Naud1.css`)
- Header "Help" button (unscoped) and "Unsure about this question? Ask about the rules" under the field (field scope) open the panel; it takes the sidebar column, drawer below 1180px, icon-only header buttons below 600px.
- Field scope shows the card at the top of the panel thread: help text, option meanings, related-question chips (click = `related`). Scope chip "About: this question" with x to clear.
- Typed in the panel = question. In the form composer only a message ending in `?`, text on a file field, or "Ask in Help" goes to the panel (unscoped).
- "Searching for: ..." under a question whose search text differed. "Talk to a person" button in the panel composer. Handover message in an amber card. Answer cards: question, verbatim answer, source. The field thread is not repeated after an answer (new ticket adopted silently).
- Removed: "Ask about this answer" and the answer-scope search (the search came back to the answer already shown in 7 of 8 eval cases), the "may already be covered" note.

**Evaluation** (`evals/eval_composed.py --report evals/reports/composed_report.md`, needs the model; data `evals/cases/eval_composed_queries.json`, 36 field cases written and labelled by one person, so indicative only; thresholds single 0.8, min 0.5, margin 0.12)
- typed only 30/36 offered, 25/36 first; label always in front 29 / 25; app rule 34 / 28 (composed used in 7). No wrong single match in any column. Composition helps vague messages ("what is this?"), hurts specific ones ("can I black out parts of it?"); the app rule keeps the typed search unless it misses the field's FAQs.
- Remaining misses: c01 "what do I put here?" on planned work, c28 "I stopped working because of my illness".

**Tests**: `tests/test_application_faq.py` (32: application ask/confirm, field card, field rule, gated rewrite, every handover trigger, marking checks, logs, eval data and scoring). Full suite: see the 2026-10-09 fixes section.

**Run and test the application panel**
1. Re-import `xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean.xml` as a new graph. On `FAQ_Retrieve` set `header#X-API-Key` = `"<key>"` (quoted) and check the quoted ContinueOn* values survived; check `FAQ_UserQuestion` starts excluded. Note the graph id.
2. FAQ API + tunnel (Run everything, steps 4-6; effect URL current). `.env`: `OPENAI_API_KEY`, `DECISIONS_ENABLED=1` for the rewrite and distress check (optional: `DECISIONS_DISTRESS_MIN`, `DECISIONS_CONTEXT_MIN`). Restart `python app.py`.
3. `/demo?graphid=<id>` -> "Start the application" -> MitID -> `/application`: first field is the email.
4. Script: (a) "Unsure about this question?" on any field: card with help text and option meanings; click a related question -> confirm -> answer with source; email field unchanged. (b) On "Is your impairment per definition permanent...": type "I'm not sure, what should I pick?" -> "Searching for: ..." line, FAQ_08 offered. (c) On the medical-records field: "can I black out parts of it?" -> FAQ_P06, no "Searching for". (d) Two nonsense questions -> handover card on the second. (e) "I missed the appeal deadline" -> handover card plus results. (f) "Talk to a person" button -> handover card. (g) Form composer: "what does this mean?" opens the panel; a non-number on the hours field twice -> notice, then handover. (h) Answer every field to the end: the panel never changed the form. (i) Stop the tunnel and ask: "temporarily unavailable", no retry.
5. In the Portal simulation log, check the trail: `FAQ_Triage` 1, `FAQ_UserQuestion` (comment with the original wording), `FAQ_Retrieve`, `FAQ_RetrievalOk`, `FAQ_Answered`, `Help_Escalate` with reason.

**UI work (next session)**: `docs/handoffs/UI_HANDOFF.md` lists the files and components, the Help panel behaviour to keep, the backend contracts the UI depends on, the build/delivery steps, 15 observations from screenshots and the questions to settle first. Preview without DCR: `cd demo-ui && npm run build && node preview/preview.mjs` (mocked endpoints, 21 screenshots of the FAQ chat and the Help panel at 1440/1024/390 px; needs Playwright; screenshots go to `demo-ui/preview/shots/`, git-ignored).

**Open**
- Eval labels need a second labeller; segments, ambiguity rules and per-field short search hints (`Hint:` tags, needs a graph change) are deferred.
- The sidebar hard-codes an SU phone number (`ApplicationDemo.jsx`, contact card), which FAQ_P02 says the chatbot should not store.
- `static/demo/assets/` must keep `index.html`'s current bundle (`index-DI0BF8eK.js`, `index-C22Naud1.css`) and `icons8-bot-K3HB9ED8.gif`. On 2026-10-08 the whole folder was removed while cleaning stale bundles, and every asset returned 404 (log: `ERROR:root:404 Error`); restored from the build. Delete only files that `static/demo/index.html` does not reference.

**Not done yet**
- The main widget (`static/script.js`) does not render the retrieval turn shapes; use `/demo`.
- Confirm DCR URL-encodes special characters (test `is it A & B? it's 100% fine #1`; the API log should show the full length).
- Replace the quick tunnel with a fixed hostname; rotate `FAQ_API_KEY` (it has appeared in the Portal effect form).

## UI redesign (2026-10-09)

Neutral Geist look, three themes, split layout. Design system: the DCR.AI Design System artifact (v2). Backend contracts unchanged.
- `demo-ui/src/theme.css`: shared tokens (light, warm, dark via `data-theme` on `<html>`, saved in localStorage `su-theme`) and the smooth theme toggle; `ThemeToggle.jsx` is used in the chat header (compact) and the application header.
- ~~`demo-ui/src/chat.css` + `SupportChat.jsx`: FAQ widget restyled~~ Reverted the same day at Amogh's request (see next section): the FAQ widget is back to its earlier look; `chat.css` is no longer imported.
- `demo-ui/src/application.css` (section 2) + `ApplicationDemo.jsx`: one question at a time (`QuestionControl`) on the left, **Ask SU-support** (`HelpPanel`) docked on the right (open by default at 861px and wider, bottom sheet with a floating pill below). The sidebar, the form overview (`FormPanel`), the chat thread of the application, "Ask in Help" and the hard-coded phone number are removed. Answers are reviewed and changed in the collapsed "Your answers" list; changing one resets later answers (unchanged server behaviour).
- Progress is "Part n of 5" from the existing `getStageIndex` heuristic, because DCR does not know the question count in advance.
- Browse the built UI without DCR: `node demo-ui/preview/serve.mjs`, then open `http://localhost:4173/demo` or `/application?graphid=1` (set `sessionStorage['application-demo-continue']='yes'` first).

## Fixes after the UI redesign (2026-10-09, Amogh's review on graph 2014078)

**FAQ chat** (`/demo`): back to the earlier look (bot GIF, boxed answers, "Start the application" always in the bar above the message box), with the **Geist** font only. No theme toggle and no "Hello there!" greeting in the chat. `SupportChat.jsx` = the 2026-10-09 morning version (welcome from DCR, direct answers for examples and single matches, idle end after 120 s); chat styles are back in `styles.css`. `main.jsx` applies the saved theme only on `/application` and `/mitid`; the FAQ page always gets `data-theme="light"`. `demo-ui/src/chat.css` is unused (left in place; can be deleted).

**Application page**
- Question title smaller (24-30 px, weight 600), lead 17 px, panel greeting 22 px.
- "Describe it in your own words / Find the best match" is now "None of these fit? Describe your situation", a one-line explanation, and "Suggest an option"; the suggestion says "Based on what you wrote, this option fits best".
- **Ask SU-support follows the question on screen.** Each new question adds an "About this question" card to the panel thread (label, help text from DCR, "Common questions" = the field's `HelpFAQ` FAQs not yet asked); earlier questions become a one-line "Earlier question" divider. The question context is on by default (chip "About this question" with x; "Ask about this question" turns it back on) and is switched on again at every new question. The "Ask SU-support about this question" link is hidden while the panel is open with the context on. "Hello there!" + general examples only when no question is on screen (review).
- A field-scoped question with no match adds: "If that was your answer to the question, give it in the form instead. Here you can ask about the rules."

**Backend** (`application_runtime.ask`, `confirm`, new `_show`; `retrieval_llm.PANEL_REWRITE_PROMPT`, `panel_signals_decisions`)
- One FAQ found -> answered directly (`answered: true` + view + `faq_*`), no "Is this what you are asking?". A clicked suggested question is answered directly when its FAQ comes back. Several -> options as before (`/application/confirm` unchanged).
- (Search order superseded later the same day, see "Follow-up gating" below.) Search order, stopping at the first usable result: (1) contextual rewrite first if the classifier says the message depends on context (Decisions on); (2) the typed words; (3) field scope and none of the field's linked FAQs came back (or nothing came back): `"<label> <message>"`, whose result replaces an unlinked typed result only if it finds something; (4) nothing found and Decisions on: a rewrite using the field on screen + its help text + the last answered FAQ. Each search re-checks that DCR admits `FAQ_UserQuestion` (re-executes `FAQ_Triage = 1` if needed).
- "Understood as" (`searched_for`) is returned **only for an LLM rewrite**. The composed `"<label> <message>"` query is an internal search aid and is no longer shown (it was shown as "Understood as: <field question> <your words>").
- Rewrite/classifier context is now `current_question`, `about_question` (field help text, plain, 1200 chars) and `last_answered_faq`. Earlier application answers were removed: on 2026-10-09 they turned "I am not sure, how does that decision affect the application?" (on "Do you plan to work...") into a question about the time-limited award. The prompt now reads the message as being about the question on screen unless it clearly refers to the last FAQ.
- Interaction log `faq_ask` has `tried` (the steps run); `faq_answer` has `via` (related/typed/field-composed/rewritten/chosen).
- Tests: `tests/test_application_faq.py` 35 (new: direct answers, related answered directly, unlinked typed result kept when composed finds nothing, rewrite as last resort, no rewrite after a typed hit). Full suite without the two model tests: 200 OK (run on the Linux VM after `pip install -r requirements.txt`).

**Second review (2026-10-09, evening)**
- The Flask server had not been restarted after the backend change (interaction log `faq_ask` had no `tried` field), so suggested questions still asked "Is this what you are asking?" and "Understood as: <field question> <your words>" still showed. Restart `python app.py` after every backend change.
- Progress: "Part n of 5" now comes from the field id (`STAGE_OF_FIELD` in `ApplicationDemo.jsx`: About you / Your impairment / Work / Documentation / Check and send) instead of a Danish keyword guess that stayed on part 1. A field not in the map keeps the last part; a new graph field needs an entry there.
- "Previous question" above the title: shows the previous answer in place of the current question ("Your answer: ...", controls, "Keep this answer"); pressing it again goes further back. "Change" in "Your answers" uses the same view. Saving goes through `/application/edit` (rewinds, later questions asked again). File answers can be re-attached (`record()` now keeps `extensions` / `max_files`).
- The "If that was your answer..." note shows only for statements, not for questions that found nothing.
- Search misses ("if I won't work, would it be an issue?", "what do we talk about in the personal statement?", "what if I have prior work experience?"): run `python -m evals.diagnose_queries --relevance` on the Mac (needs the model). It prints the top-3 scores for typed / composed / a hand-written rewrite, the API decision and what the relevance post-check keeps, to tell a low embedding score from the relevance check dropping the FAQ.

**Relevance check fix (2026-10-09, late)**: `evals/diagnose_queries.py --relevance` showed the cause of the panel misses. The search found the right FAQ (FAQ_17 0.79 typed; FAQ_P05 0.91 for a clean rewrite), but the **Decisions** relevance check (used when `DECISIONS_ENABLED=1`) scored them near 0 (0.06, 0.11) and dropped them; the Responses check kept them. Changed in `dcrai/llm/retrieval_llm.py`: both checks now see each FAQ's question plus the first 300 characters of its answer (`_faq_for_check`), and the wording asks whether the FAQ would help (answers it, or covers the topic; a broader FAQ counts) instead of "same information need, similar wording is not enough". Affects the FAQ chat too (shared `retrieval_runtime.search`). Re-run the diagnostic to confirm; if wrong FAQs start getting through, raise `DECISIONS_RELEVANT_MIN` (default 0.5).

**Follow-up gating (2026-10-09, late)**: "okay, but would the number of hours matter here?" after FAQ_17 on Prev_work was answered with FAQ_16. Trace: the contextual rewrite ran first and found nothing relevant; then the raw words were searched and the relevance check judged them *out of context* (FAQ_16 0.7, "hours" sounds like the 5-6 hours FAQ); the composed search was rejected; the kept typed result was a single match, so it was answered. Changes:
- A message the classifier calls context-dependent is searched **only** as its rewrite (no raw or composed search). If the rewrite finds nothing, the panel says so.
- The relevance check judges against what the applicant means (the rewrite, or their own words), never the composed `"<label> <message>"` string (`retrieval_runtime.search(..., judge=)`; the FAQ chat is unchanged, judge defaults to the query).
- Rewrite and classifier context now also hold the applicant's previous panel question (`help_last_message`) and the last FAQ shown with the start of its answer (`help_last_faq`); prompt has a follow-up example.
- A follow-up whose only match is the FAQ just shown gets "The answer above is the closest the FAQ has. It does not say more about this." (log decision `same_faq`).
- "Understood as" is returned whenever a rewrite was made, also on no match.
- Tests 39 in `test_application_faq.py`; suite 204 OK.

**Still open from this review**
- ~~"what if I have prior work experience?" found nothing~~ Explained: the Decisions relevance check dropped FAQ_17 (0.06) although the search found it (0.79). Fixed in "Relevance check fix"; to be confirmed by the follow-up eval.
- The "same FAQ" text ("It does not say more about this.") is wrong when the FAQ just shown does answer the follow-up (eval group S, e.g. "so they won't contact my old employers?" after FAQ_17). Decide the wording after the eval.
- No "related, but not an answer" middle tier yet (options are shown as "may fit"); see the handoff.
- `zz_delete_probe` (empty file in the repo root) was created by the agent while checking the delete block; delete it.
- Bundle: `static/demo/assets/index-BMLDYZF-.js` + `index-BabljOgH.css` + `icons8-bot-K3HB9ED8.gif`. Stale (delete only these): `index-CE8JIrr0.js`, `index-Btw1vNpb.css`, `index-C98xnsyZ.js`, `index-BYgjQHef.css`.
- The design system artifact still says 46 px questions, a big greeting and themes in the chat; update it if this review is the new standard.

## Session 2026-10-09 (summary)

All on graph **2014078** (the rebuilt Clean graph with `FAQ_Welcome` is not imported yet; Amogh will import the final version at the end). Details are in the sections above; this is the index.
1. **FAQ chat**: short welcome from DCR, examples and single matches answered directly, no "another question" prompt, 120 s idle end (morning); Amogh's redesign of the widget reverted to the earlier look with the Geist font (evening).
2. **Application page** (Amogh's one-question-at-a-time redesign kept): smaller titles, clearer "describe your situation" copy, progress from field ids (`STAGE_OF_FIELD`), "Previous question" back link, themes only on the application pages.
3. **Help panel**: follows the question on screen (About card + common questions per question, earlier ones as dividers), field context on by default, answers single matches and clicked suggestions directly, "Understood as" only for real rewrites.
4. **Retrieval in the panel**: rewrite context = field + help text + previous panel question + last FAQ with answer start (no earlier form answers); a context-dependent message is searched only as its rewrite; relevance judged against what the applicant means, never the composed string; same-FAQ follow-ups point back; relevance checks see the answer start and a broader "would this help" wording (fixes the Decisions check dropping clear matches).
5. **Tools**: `evals/diagnose_queries.py` (scores + both relevance checks for a few queries), **`evals/eval_followups.py` + `evals/cases/eval_followup_queries.json`** (49 cases, the real `application_runtime.ask` with DCR stubbed; see the handoff), `.env.example` (every setting the code reads; `ROOT_URL` must end with `/`; `FAQ_MATCH_MODEL` is the OpenAI model, `docs/guides/DEPLOY.md` is wrong to set it to the embedding model).
6. **Environment incident**: `.env` went missing on the Mac during the session (cause unknown; the agent cannot delete files there and never read it). Recreated by Amogh from `.env.example`.
7. Tests: 204 OK without the two model tests (`tests/test_application_faq.py` 39).

## Help panel follow-up eval (2026-10-09)

`python -m evals.eval_followups` (needs the model, `OPENAI_API_KEY`, `DECISIONS_ENABLED=1`). 49 cases in 9 groups (F follow-up answered by another FAQ, N follow-up no FAQ answers, S covered by the FAQ just shown, C self-contained controls, T topic switch, V vague field-context, A statements typed into Help, O out of scope, M second-step follow-ups). Each case seeds the panel state (field, previous question, previous FAQ) and runs the real `application_runtime.ask`; only DCR is replaced (local retriever + the API's decision rule, real relevance check). Output: `evals/reports/followup_report.md` (verdicts, per group, threshold sweeps for `DECISIONS_CONTEXT_MIN` and `DECISIONS_RELEVANT_MIN`, a line per case) and `followup_results.json` (rewrites, every search with scores and relevance probabilities). **The target metric is WRONG = 0** (an FAQ answered that does not answer the question), then as many correct answers as possible. Labels are a first pass by the agent; correct them where they are wrong. Not run yet. How to read it and what to tune: `docs/handoffs/HANDOFF_2026-10-09_followup_eval.md`.

## Phase 1: stop wrong answers (spec 01, 2026-10-10)

Spec: `docs/specs/01-stop-wrong-answers.md` (read section 11, the amendments, with it). Gate: zero WRONG when the follow-up eval is re-run (Amogh runs it, spec task T9). Nothing here was run against a model.

- **Confirm (row 6).** `rr.search()` now sets `state['last_search'] = {'decision', 'retrieved'}` (the API decision before pruning) and a `tier` on each kept candidate (`answers` or `related`). `rr.interim_outcome(decision, candidates)` (pure) returns `(outcome, row, shown)`; the chat `ask()` and the panel `ask()` branch on it. A list pruned to one FAQ that answers it gives a Confirm: chat status `confirm` with a `confirm` prompt, panel status `faq_confirm`. Nothing is shown and `FAQ_Answered` is not executed until yes. No gives a rephrase request (panel: a miss is counted). A true single match that answers it is still answered directly. Spec 03 replaces `interim_outcome` and the branching.
- **Relevance in two judgements.** `rr.check_relevance(message, found)` (used by `search()` and by the eval stub) calls `relevance_tiers` / `relevance_tiers_decisions` (new prompts `relevance/tiers`, `relevance/answers`, `relevance/same_topic`). A single match that is only on the same topic is offered as related (chat: status `options` with `related: true`; panel: status `faq_related`), never answered. When the check is unavailable every candidate is `related`, on both paths (fail closed).
- **Panel fallback rewrite removed** (`PANEL_FALLBACK_REWRITE=0`). A message the classifier does not call context dependent is searched as typed and, in field scope, composed; never rewritten. `prompts/rewrite/panel.txt` no longer holds eval case n01.
- **Wording.** WD1 (same-FAQ reply by tier), WD2 (related offer), WD3 (statement note in the panel UI, shown after any non-answer reply). WD4 was not identified (Q1) and is not implemented.
- **Logging.** `faq_outcome` (per question turn) and `faq_reaction` (per click on a Confirm, Offer or options prompt) through `rr.log_outcome` / `rr.log_reaction`; no message or FAQ text. The chat `/init` now starts an interaction log (`ilog.start(..., interface='chat')`). `state['turn']` is incremented once per request, in `turn_trace.turn` (chat `handle`, panel `ask`, panel `confirm`); `rr.next_turn` is gone (spec 02).
- **Flags** (defaults apply the change; `.env.example` has them): `CONFIRM_LONE_SURVIVOR=1`, `RELEVANCE_TIERS=1`, `PANEL_FALLBACK_REWRITE=0`, plus `DECISIONS_ANSWERS_MIN` and `DECISIONS_TOPIC_MIN` (0.5, not calibrated). To roll back a part, set the opposite value and restart `python app.py`.
- **Eval.** f08 now accepts FAQ_41 and FAQ_32. `python -m evals.eval_followups --regrade evals/runs/followup_results.json --report evals/reports/followup_baseline_regraded.md` regrades the stored baseline without a model (expect WRONG 30, correct 51). New verdicts `confirm_right`, `confirm_wrong`, `confirm_unneeded`; the report header records `prompts.version()` and the flags. See `evals/README.md`.
- **Tests.** New `tests/test_eval_followups.py`; additions in `tests/test_retrieval_runtime.py` and `tests/test_application_faq.py`. Old fakes that patch `llm.relevant` now also patch `relevance_tiers` through `patch_tiers()`.
- **UI.** The panel shows a "Yes, show the answer" button under a Confirm card and the statement note after any non-answer reply (`demo-ui/src/ApplicationDemo.jsx`); preview mocks have the new turn shapes. The bundle in `static/demo/` was built from these sources, but not with the repo's own `node_modules` (installed on macOS, no Linux rolldown binding): the build ran in a scratch copy with `npm ci` and the output was copied in. Older hashed files in `static/demo/assets/` are stale and can be deleted by hand (the device mount does not allow deletes); `index.html` references only `index-CzGnpKpc.js` and `index-BabljOgH.css`.
- **Open for Amogh:** T9 (baseline regrade, the eval run, the tolerance for the drop in correct answers, Q2 to Q5 in the spec) and T10 (remove the flag-off paths and `relevance/fits`, `relevance/relevant`, or hand them to spec 02).

## Phase 2: registry and trace record (spec 02, 2026-10-10)

Spec: `docs/specs/02-registry-and-trace-record.md`. Nothing here was run against a model.

- **Registry.** `dcrai/registry.py` is the one table of settings (thresholds, flags, models, retrieval, constants, ops, secrets). Read with `registry.get(NAME)` / `registry.flag(NAME)` at call time; an unparsable value falls back to the default; a secret is refused by `get()`. `registry.version()` is a 12-hex hash of the prompt digests, the versioned setting values and the FAQ data files. `ilog.start` records it and writes `traces/registry/<version>.json` once. `rr.flag(name, default)` delegates to the registry for registered names. Registered for spec 03: `OUTCOME_MODE` (`code`), `FOLLOWUP_SURFACE` (`panel`), `PANEL_TRIAGE` (on); `outcome_runtime.mode()` reads through `registry.get`. Names that carry `env=False` (`PROMPT_TTL`, `MISSES_BEFORE_HANDOVER`, `ANSWER_PREVIEW_CHARS`) are constants, not environment settings.
- **Base layer.** `prompts/base/decisions.txt`, applied to the Decisions API request when `BASE_LAYER_DECISIONS=1` (default 0; the request body is byte for byte the old one when off).
- **Trace record.** One `turn` line per request in the existing per-interaction JSONL, written by `@turn_trace.turn('chat'|'panel')` on chat `handle` and panel `ask` / `confirm` (also when the request raises, with `error`). It holds the entry, the message, `searches` (from `@turn_trace.traced_search` on `rr.search`: query, judge, how, decision, scores, retrieved, relevance probabilities, kept, tiers, latency), `calls` (every model call: prompt digest, model, outcome, latency, attempts), `dcr_events` (every event executed), `context`, `faq_outcome`, `reacts_to`, `handover`, `context_write`. The `start` line has `schema=2`, `interface`, `graph_revision` and `registry_version`. The `record` key `interaction_id` replaced `interaction`. Faults in the recorder are swallowed; strings over 20,000 characters are cut and flagged `truncated`.
- **Reader.** `python -m dcrai.observability.trace_reader PATH [--check] [--rates]` loads old and new files, derives the confirm accept rate and the re-explain rate, and checks a file (exit 1 on a problem). Fixture: `tests/fixtures/trace_interaction_sample.jsonl`.
- **Panel context in DCR.** The graph has a text event `Panel_Context` (builder: `tools/clean_graph/build_clean_graph.py`, added last so no sequence moves). `dcrai/application/panel_context.py` writes a JSON v1 record (the last two FAQs shown, newest first, the field on screen, the previous message; no answer text; at most 1500 characters) once per panel request through `@panel_context.persist`, and `help_context` reads it back from the event list it already fetched. Flask session fields stay the fallback (older graphs, unreadable value, `PANEL_CONTEXT_IN_DCR=0`). The Flask session is still lost on restart; the event gives audit and rebuildability, not a restart-proof session. A failed write never changes the reply.
- **Decorators other work edits around.** `turn_trace.turn` sits outside `panel_context.persist` on panel `ask` and `confirm`. Do not rename them.
- **Tests.** `tests/test_registry.py`, `test_turn_trace.py`, `test_trace_hooks.py`, `test_trace_reader.py`, `test_panel_context.py`. Fakes in `tests/test_retrieval_runtime.py` are reused. Tests that patch `repo.execute_raw_event` bypass the DCR-event hook; hook tests patch `repo._session.post`.

## Phase 3: graph split, outcome table, DMN (spec 03, 2026-10-11)

Spec: `docs/specs/03-graph-split-outcome-table-dmn.md`. Nothing here was run against a model, and the new graph has not been imported into the Portal yet (Amogh, task T10).

- **Outcome function.** `dcrai/chat/outcome.py` (pure, no imports from the repo) holds the nine-row table `ROWS` (scope x search x relevance x clarified, first match wins), `derive_inputs`, `decide`, `from_table`, `shown_for`, `next_clarified`, `next_misses`. Seven outcomes: answer, confirm, offer, clarify, not_covered, out_of_scope, handover. Handover: reason 1 (the applicant asked for a person) and reason 2 (second miss in a row, once per session). The runtimes never count candidates; `tests/test_outcome.py::test_no_candidate_count_branch_in_runtimes` scans both for it. `rr.interim_outcome` (spec 01) is gone.
- **Writing the outcome into DCR.** `dcrai/chat/outcome_runtime.py`: `settle(state, payload, decision, interface)` executes `TurnOutcome` and checks that exactly the outcome's event is pending (otherwise it fails closed to not_covered). Modes (`OUTCOME_MODE`): `code` (default; the function decides), `shadow` (the DMN in DCR is run too and a difference is logged as `outcome_mismatch`), `dcr` (the DMN decides). A graph without `TurnOutcome` is untouched. `handover(state, reason, signal)` executes `Help_Escalate` and acknowledges `Help_Handover`; `PERSON` and `URGENT` live here and are re-exported by `application_runtime`.
- **The graph, one file, two sessions.** `tools/clean_graph/split_steps.py` (called by the builder): `Session_Chat` gates `FAQ_UserQuestion` and the chat; `Session_Panel` gates `Help_UserQuestion` and the determination selector; the help panel has its own search Robot (`Help_Retrieve`, `Help_RetrievalOk`, `Help_RetrievalUnavailable`). Triage, scope, no-match, out-of-scope and handover are shared. `TurnOutcome` has guarded responses and co-responses, so exactly one outcome event is pending after it. The DMN chain is `TurnStart`, four `Gate*` inputs, the `OutcomeTable` Robot (a DMN generated from `outcome.ROWS` by `tools/clean_graph/dmn_table.py`) and `TurnResult`. Build: `python tools/clean_graph/build_clean_graph.py --with-effect --outcome dmn` (default) or `--outcome code` (no DMN machinery; files `*_OutcomeCode.xml`). Validator 0 errors and simulator FAILURES 0 on all four files. Old graphs (2014078) still work: every new step is feature-detected.
- **Chat** (`dcrai/chat/retrieval_runtime.py`). `initialize` executes `Session_Chat` once; `ask` calls `decide_turn` then `settle_turn` and renders by outcome; counters live in `state['outcome']` (`clarified`, `misses`, `handover_shown`) and move by `advance(state, signal)`. A second clarify gives row 8 (the best offer); the second miss in a row adds a `handover` block to the reply; a message that matches `PERSON` returns status `handover`. `scope_check` is row 2 (text from `FAQ_Msg_ScopeQuestion`). Outcome texts come from the DCR events (`outcome_message`), host strings are the fallback. The chat no longer opens determinations (`show_answer` skips `open_followup` unless `FOLLOWUP_SURFACE=chat`).
- **Panel** (`dcrai/application/application_runtime.py`). `start` sets `state['panel_search']` (the graph has `Help_UserQuestion`), the outcome counters, and executes `Session_Panel`. An unscoped typed message goes through `panel_triage` (values 1 and 5 only; unsure, a model error or a missing dictionary give 1); a 5 returns status `faq_out_of_scope` with the `FAQ_OutOfScope` text and no search. A related click and a field-scoped question skip the triage; a related click that brings its own FAQ back skips the table. `_miss(state, signal)` and `state['outcome']` replace `state['help_misses']`. `_show` opens the follow-up determination (`rr.open_followup`) and the result carries `prompt` (kind `determination`) and `follow_up`; the reply goes to `determination(state, data)` (`POST /application/determination`, body `{retrieval_prompt_id, value}`), which leaves the application untouched (`_unchanged`).
- **Settings** (registry, read at call time; `.env.example` has them): `OUTCOME_MODE=code`, `FOLLOWUP_SURFACE=panel` (`chat` restores the old behaviour), `PANEL_TRIAGE=1` (0 restores the unconditional `FAQ_Triage = 1`), plus the phase 1 `CONFIRM_LONE_SURVIVOR`.
- **Log.** `faq_outcome` lines carry `outcome_inputs`, `outcome_source`, `outcome_dcr`, `outcome_row_dcr`, `outcome_mismatch`, `clarify_kind`, `label`, `handover_reason` (ids and codes only, never text). The turn line copies `outcome`, `outcome_row`, `faq_ids`, `via`, `outcome_inputs`.
- **UI** (`demo-ui/src/SupportChat.jsx`, `ApplicationDemo.jsx`, `styles.css`, `application.css`, `preview/preview.mjs`). Chat: an amber "Talk to a person" block under a reply that carries `handover`. Panel: `faq_out_of_scope` shows like `faq_no_match`; a determination prompt with a Skip link, and the outcome under "Your answer". Bundle: `static/demo/assets/index-WvnmRTxy.js` + `index-ByrP4b3R.css` + `icons8-bot-K3HB9ED8.gif` (built in a scratch copy, as in phase 1). Stale (delete by hand, the device mount does not allow deletes): every other `index-*.js` and `index-*.css` in that folder, including the two intermediate builds `index-Cu7QvYPl.js`, `index-BZc1soGQ.css`, `index-C7QSshiZ.js`, `index-CGsexf72.css`. `preview.mjs` now prints page and console errors and has mocks for the handover, the out-of-scope notice and the determination.
- **Tests.** `tests/test_outcome.py`, `test_outcome_table_graph.py` (skipped without `xml graphs/` and `tools/`), `test_outcome_runtime.py`; additions in `tests/test_retrieval_runtime.py` (`TurnFake`, `OutcomeTableChatTests`) and `tests/test_application_faq.py` (`PanelFake`, `PanelOutcomeTests`). The older chat determination tests run with `FOLLOWUP_SURFACE=chat`.
- **Eval.** `evals/eval_followups.py` accepts `Help_UserQuestion` in its stub. After a re-run report the outcome mix by row and how many group O turns end in row 1 (`evals/README.md`).
- **Open for Amogh (T10).** Import the `--outcome dmn` build as a new graph, attach `handicap-faq-v2` to `FAQ_Retrieve` and `Help_Retrieve` (quoted continuation ids), run the Portal checklist and fixtures F1 to F5 (spec 7.2, 7.3), run `OUTCOME_MODE=shadow` for a while, then decide on `dcr`. Re-run the follow-up eval (WRONG 0).

- **Live eval (2026-10-12).** `evals/eval_live.py` (tests in `tests/test_eval_live.py`): `table` runs the nine rows through the Portal graph (F1, F4, F3 in effect), `panel` drives the running app over HTTP and reads `traces/interactions` back. See `evals/README.md`. Nothing in it has been run against the Portal or a model yet.

## Run everything (commands)

Run from the repo root. Never print or commit keys; never read `.env` without being asked.

```bash
# 0. Environment (once)
conda activate dcr
pip install -r requirements.txt
pip install -r faq_search/requirements.txt          # sentence-transformers, numpy
brew install cloudflared                            # tunnel client, once

# 1. Knowledge base and embeddings (only when records or the docx change)
python faq_search/build_faq_data.py                 # reads docs/sources/, writes faq_search/data/faq_qa_records.json
python faq_search/embed_faq_data.py                 # -> faq_embeddings.npy, faq_embeddings_meta.json

# 2. Tests (must pass before commit)
python -m unittest discover -s tests
python -m unittest tests.test_faq_api               # API only, no model needed
RUN_RETRIEVAL_EVAL=1 python -m unittest tests.test_faq_eval   # optional, real model

# 3. Validate a graph before importing it into the Portal
python .agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py "xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"

# 4. Retrieval API (terminal A)
export FAQ_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"   # or reuse your existing key
export FAQ_API_EXTRA_KEYS='<token shown in the Portal effect editor>'                  # see docs/guides/DEPLOY.md section 7
python -m faq_search.api                            # 127.0.0.1:8090, loads the model first

# 5. Tunnel (terminal B) - prints https://<random>.trycloudflare.com
cloudflared tunnel --url http://127.0.0.1:8090

# 6. Check it
curl -s http://127.0.0.1:8090/health
curl -s -H "X-API-Key: $FAQ_API_KEY" "https://<tunnel>/api/faq/search?q=part-time%20student" | python -m json.tool

# 7. Main chatbot and demo (terminal C)
python app.py                                       # http://localhost:8080/ -> /demo ; ?graphid=<ID>

# 8. Demo UI (only after editing demo-ui/)
cd demo-ui && npm ci && npm run build && cd ..      # output goes to static/demo

# 9. Threshold calibration (after changing records, embeddings or model)
python -m evals.calibrate_thresholds --report evals/reports/calibration_report.md
python -m evals.calibrate_thresholds --from-scores
python -m evals.calibrate_thresholds --ab
```

DCR Portal steps, in order, for the retrieval pilot:
1. Effect Administration: tick **Use** on `handicap-faq`. If the tunnel URL changed, edit the effect (Edit Custom Effects), set the URL, check the token, **Save to organization**.
2. Import `xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml` as a new graph.
3. In the graph, Effects, **Import**, choose `handicap-faq`, and attach it to `FAQ_Retrieve`.
4. Set parameters: `q` = `FAQ_UserQuestion`, `ContinueOnOk` = `FAQ_RetrievalOk`, `ContinueOnFail` = `FAQ_RetrievalFail`, `ContinueOnTimeout` = `FAQ_RetrievalTimeout`.
5. Simulate: execute `FAQ_UserQuestion` with a question. The API terminal should log a request and no 401; `FAQ_RetrievalOk` then holds the JSON.
6. If the effect is saved again, the stored token changes: copy it, update `FAQ_API_EXTRA_KEYS`, restart the API.

Troubleshooting by log line (API terminal):
- `rejected 401 credential_sources=none` means DCR sent no credential. `credential_lengths` differing from `expected_length` means DCR sent its stored token: add it to `FAQ_API_EXTRA_KEYS`.
- `rejected 400 missing q` means the effect sent no `q`; check the effect URL and the Robot parameter `q`.
- Simulator error "Parameters of type 'text' cannot use '$(...)' syntax" means `q` must be the plain event ID.

## Known issues and fixes (retrieval pilot)

Symptom, cause, fix. Check the API terminal log first: it prints which credential sources and parameter names arrived, never values or query text. Never paste a key into chat, a commit or a doc.

### Authentication (effect to API)
| Symptom | Cause | Fix |
|---|---|---|
| Effect returns `{"error":"unauthorized"}`; log: `rejected 401 credential_sources=none` | DCR sent no credential the API reads. The Portal token authenticator sends header `X-DCR-AuthToken`; older API versions only read `X-API-Key`, `Bearer` and `Basic`. Or the effect has no auth set. | Run the current `faq_search/api.py` (it reads `X-DCR-AuthToken`). In the effect editor check Authentication Type and that a token or password is saved. |
| Log: `credential_sources=['x-dcr-authtoken'] credential_lengths={...: [88]} expected_length=43` | The Portal sends its stored, encrypted token (88 characters), not `FAQ_API_KEY`. | Copy the token from the effect editor and restart the API with `FAQ_API_EXTRA_KEYS='<token>'` next to `FAQ_API_KEY`. |
| Token or header changes after **Save to organization**; auth works, then breaks again | The Portal resets the header to `X-DCR-AuthToken` and re-encrypts the token on every save, so the stored token changes. You cannot keep `X-API-Key` there. | After every save, copy the new token into `FAQ_API_EXTRA_KEYS` and restart the API. Save the effect only once per test. Alternative: `HttpBasicAuthenticator` (user `amogh`, real key as password) and check whether `credential_lengths` then equals `expected_length`. |
| Right length but still 401 | Mistyped key, or trailing whitespace or a newline from pasting. | Copy with `printf '%s' "$FAQ_API_KEY" \| pbcopy`, paste once, save. Confirm the shell key works: `curl -s -H "X-API-Key: $FAQ_API_KEY" "https://<tunnel>/api/faq/search?q=test"`. |
| curl works, effect does not | The key is fine; the effect sends something else. | Read the log line above; it states which source arrived and its length. |

### Effect configuration (Portal)
| Symptom | Cause | Fix |
|---|---|---|
| Log: `rejected 400 missing q`, or the API answers `missing query parameter 'q'` | The URL has no `?q=$(q)` (or has a stale `?q=q`), or the effect is `Http.Post`. The API reads the query string before the body. | Use `Http.Get` with URL `https://<tunnel>/api/faq/search?q=$(q)`. Parameter `q` is a mandatory text parameter. |
| Test Effect shows nothing for a POST effect | `Http.Post` is an after-effect; its output only reaches continuations. | Use `Http.Get` (a before-effect) for lookups. |
| Test Effect shows nothing although the call succeeded | The ContinueOn fields were filled; the output went to those events. | Clear ContinueOnOk/Fail/Timeout in the test panel to see the raw result. |
| Error: `No value for mandatory parameter 'ContinueOnTimeout'` (or Ok/Fail) | The ContinueOn* parameters are marked mandatory. | Make all three non-mandatory with empty defaults. |
| JSON Selector says "No output found. Try running the effect" | The effect has not been run, or only a continuation received the output. | Run the effect with empty ContinueOn fields first. |
| Request goes out but the response is wrong or empty | Output rows: 200-208 must be `ok` with json, scope ALL, empty expression (whole body); 408/504 `timeout`; `*` `fail` (preserve). | Compare with the effect in `CLAUDE.md` change log and fix the output rows. |
| Cannot add the effect to the graph | Effects are organization-level since Portal 7.3: "Adding effects directly to graphs is not supported anymore". | In Effect Administration tick **Use** on `handicap-faq`; then in the graph open Effects, **Import**, and attach it to `FAQ_Retrieve`. The Test/Staging/Production forms are empty for this effect; nothing to fill in. |
| Simulator will not start: `Parameters of type 'text' cannot use '$(...)' syntax. (Likely you want just 'FAQ_UserQuestion'.)` | On the Robot, `q` was set to `$(FAQ_UserQuestion)`. | Set `q` to the plain event ID `FAQ_UserQuestion`. Only the effect's own URL uses `$(q)`. |
| Effect runs in the simulator but no output is visible | The result is the value of `FAQ_RetrievalOk`, a System event that the task list hides. | Look at the event's value in the graph or data view. For debugging only, give `FAQ_RetrievalOk` a visible role temporarily and switch it back to `System`. |
| Works, then fails after the tunnel was restarted | Quick-tunnel URLs change on every `cloudflared` start. | Copy the new URL into the effect (Edit Custom Effects), check the token, **Save to organization**. The API key does not change. |
| Connection error from DCR | API not running, bound to 127.0.0.1 only, or the tunnel is down. | Start the API (`python -m faq_search.api`), start `cloudflared tunnel --url http://127.0.0.1:8090`, check `/health`. |

### Graph XML
| Symptom | Cause | Fix |
|---|---|---|
| Effect element in the XML is rejected or ignored on import | The serialization of an effect on an event is unverified. | Import `..._Retrieval_Clean_NoEffect.xml`, attach the effect in the Portal, export the graph, and compare. |
| Script cannot find an event's `custom` block | Looking up `<event>` with `iter("event")` also matches `runtime/marking` entries. | Restrict lookups to `specification/resources/events`. |
| Duplicate label warning or odd label mappings | Label IDs equal the visible label text, so each label must be unique. | Keep every label string unique across the whole graph (the Multi graph has one pre-existing duplicate). |
| Determination question executable too early, or stale outcome stays open | Missing include/exclude or co-response pairs. | Keep the `Det*_Ask` events excluded at start, include on the selector value, exclude when another value is chosen, and keep the stale-branch co-responses. |
| Robot never runs, or runs forever | A Robot runs only when included and pending, and needs a termination. | `FAQ_UserQuestion` responds to `FAQ_Retrieve`; the Robot itself has no response back, so it runs once. |

### REST simulations and Robots (test graph: next import of the Clean graph)
Test on the latest import of `xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean.xml` (2026-10-08 revision: triage without value 3, no FAQ-to-Form0 relations). 2014076 is the previous revision (still has triage 3); 2014073 and 2013928 are older. The findings below were made on 2013928 and 2014073. Stale traces, interaction logs and probe fixtures were removed on 2026-10-08; probes rewrite their fixtures when run. `tools/probe_apply.py` shows what DCR reports for Form0 after each triage value.
- Use the new engine only: `POST /api/graphs/{id}/simulation` (201, `X-DCR-simulation-ID`), then `GET|POST /api/graphs/{id}/simulation/{simid}/event` with `{"eventId", "eventValue", "comment", "isNull"}`. Do not use `/sims/` routes for testing; `/sims/` is the old engine and never runs Robots or effects.
- **App code (2026-10-07):** `dcrai/dcr/dcr_repository.py` uses only the new engine. `create_simulation`, `get_raw_events`, `get_events`, `get_simulation_events`, `execute_raw_event` and `execute_event` all call `/api/graphs/{id}/simulation...`; no `/sims/` route remains (activity-backed choice menus included). Each event read caches every event's first role in `state['event_roles']`, and `execute_raw_event` sends it (or an explicit `role=`); events without a role are sent without one. `create_simulation` clears the cache. Runtime traces in `app.py` save only the event list (no payload or log read exists on this engine). Tests: `tests/test_dcr_simulation_api.py`.
- Skill: `.agents/skills/dcr-xml-builder/references/rest-simulation-api.md` documents routes, role, parameter quoting, continuations and error messages.
- The `/simulation/` engine runs Robots: on a copy of this graph without an effect, `FAQ_UserQuestion` (204) executes `FAQ_Retrieve` in the same request.
- The same effect runs in Portal simulations and in Test Effect.
- `Location: /api/Simulation/{simid}` from create returns 404 on GET.
- `GET /api/graphs/{id}` has the effect parameters of the Robot in `custom/eventTypeData/parameter`; the live event list repeats them in `eventType.Parameters`. Values of `header#...` parameters are stored in clear there, so probes redact them.
- **Working over REST since 2026-10-07 (sims 2104370-2104376 on 2013928).** Two things were needed:
  1. **`role` in the execute body.** Without it, any event whose execution runs the Robot returns 500 `Value cannot be null. (Parameter 'input')`. Send the event's own role (`"role": "Chatbot"` for `FAQ_UserQuestion`). The Portal always sends one, which is why it worked there.
  2. **ContinueOn parameters declared on the effect and set as quoted event IDs on the Robot.** `handicap-faq-v2` declares `ContinueOnOk/Fail/Timeout` (text, not mandatory, empty default). On `FAQ_Retrieve` in the graph: `q` = `FAQ_UserQuestion` (unquoted: the event's value), `header#X-API-Key` = `"<key>"`, `ContinueOnOk` = `"FAQ_RetrievalOk"`, `ContinueOnFail` = `"FAQ_RetrievalFail"`, `ContinueOnTimeout` = `"FAQ_RetrievalTimeout"`.
     - Unquoted text parameters are evaluated as expressions. Unquoted ContinueOn values give `[0905] Unknown continuation 'ContinueOnFail=undefined'` (the label event's value). An unquoted key gives 409 on create: `[0605] Unknown activity id '<key>'`. Re-importing the effect into the graph can drop the quotes.
     - Without ContinueOn parameters the result stays on `FAQ_Retrieve` and `FAQ_RetrievalOk` never runs.
  - Result: `FAQ_UserQuestion` + role, 204 in about 520 ms; `FAQ_Retrieve` and `FAQ_RetrievalOk` executed in the same request; `FAQ_RetrievalOk` holds the full API JSON (`decision`, options). Failure path: `FAQ_Retrieve` with role `Robot` and empty `q` gets 400 from the API and executes `FAQ_RetrievalFail` (value is the error body).
- Probes: `python tools/probe_simulation_effect.py` (control matrix, writes `tests/fixtures/simulation_probe_<graph id>.json`); `python tools/probe_retrieval_events.py [--selector]` (Phase 0 event dump, for when the effect works). Both default to 2014073; always set `DCR_TEST_GRAPH_ID` to the current graph and use `/simulation/` only. The bridge shell cannot reach `repository.dcrgraphs.net` (proxy 403), so the user runs them.

### Environment and tooling
| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'sentence_transformers'` in tests | Wrong Python environment. | `conda activate dcr` and `pip install -r faq_search/requirements.txt`. |
| `unable to unlink .git/index.lock: Operation not permitted` | Git run through a restricted bridge shell. | Run git commands in your own terminal. |
| Embeddings or answers out of date | Records changed without rebuilding. | `python faq_search/build_faq_data.py` then `python faq_search/embed_faq_data.py`. |
| Decision looks too eager or too cautious | Thresholds are tuned per query-prompt setting. | `python -m evals.calibrate_thresholds --ab` and set `FAQ_SINGLE_THRESHOLD`, `FAQ_MIN_THRESHOLD`, `FAQ_MARGIN_THRESHOLD`; keep `FAQ_QUERY_PROMPT` identical everywhere. |
| Special characters in the question arrive cut off | Unverified whether DCR URL-encodes the text. | Test `is it A & B? it's 100% fine #1`; the log should show the full length (30). If shorter, fix the encoding before going on. |

### Agent working notes (Claude Code with the device bridge)
- Files pushed to the device can show old content for a few seconds. Re-commit, wait about 5 seconds, then verify with `grep` or file size.
- The Portal pages render scaled in Chrome automation: click at the screenshot coordinate divided by the scale (for 0.6, divide by 0.6). "Edit Custom Effects" opens the editor in the same tab.
- Closing the only tab an agent created dissolves its tab group; reopen with a new tab context.
- Do not read `.env`, print keys, or commit logs, caches, `.env` files or review material.

## Application as a thread (2026-10-12, Amogh's review)

The application column is a chat thread again (reverses "one question at a time" of 2026-10-09). Backend contracts unchanged; Ask SU-support (`HelpPanel`) untouched.
- Questions are left-aligned lines, the person's answers are right-aligned bubbles with a **Change** link (opens the existing `EditAnswer`; later answers reset as before). The "Your answers" list is gone: the thread is the review.
- `InlineChoices` under the current question: a single choice or Yes/No is answered by one click (no Continue); several choices are ticked and confirmed with Continue.
- `Composer` (always visible, bottom of the column, not shown for file, Yes/No or review): on a choice question it replaces the hidden "None of these fit?" section (placeholder "None of these fit? Describe your situation"); on number, date and text questions it is the answer box.
- **A typed plain number is answered directly** (`PLAIN_NUMBER` in `send()`): no `/application/interpret` call and no "Use this answer" step. Words ("about six hours") are still interpreted and confirmed. The server still validates the range.
- A rejected answer (range, unreadable words) shows in the thread (`formError`, separate from the Help panel's `error`), the reply bubble is removed and the typed text goes back into the box. "Not this" on a suggestion also restores the words.
- Phone: the floating "Ask SU-support" pill is removed (the message box sits at the bottom); the header button opens Help at all widths.
- Check without DCR: `node demo-ui/preview/thread.mjs [outDir]` (stateful mock, 26 checks, screenshots at 1440 and 390 px; needs Playwright). Bundle: `index-DFVk7Fp3.js` + `index-D6oZJEFY.css` (older bundles left in place).
- Frame (same day, second review): the page does not scroll. Top bar (Back, Start again, theme, Ask SU-support) and the part progress line are fixed at the top, the message box is fixed at the bottom, and only the thread between them scrolls; it scrolls to the newest item by itself and sits at the bottom when short. Every question is a left bubble in normal text size (no heading look). `Start again` moved from the bottom to the top bar. Phone: Back and Start again on one row, Ask SU-support and the theme toggle below.
- Third review: with Ask SU-support open, the application column now fills its space (no centred 640 px column with a gap to the panel; the gap is 40 px, options and the suggestion card stay 560 px wide). A text "Change" link under each answer is replaced by a pencil icon left of the answer bubble, shown on hover or keyboard focus (always visible, slightly dimmed, on touch screens).
