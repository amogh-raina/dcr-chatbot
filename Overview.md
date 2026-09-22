# DCR chatbot architecture

## Current application

`app.py` runs a Flask application through Waitress on port 8080. The main UI at `/` uses `templates/index.html` and `static/script.js`. The React/Vite showcase at `/demo`, `/mitid`, and `/application` is served from `static/demo`; source and npm dependencies are in `demo-ui`. 

- **FAQ Support**: Served via the `/init` and `/chat` contract. `demo-ui/src/SupportChat.jsx` renders API choices, confirmations, verbatim answers, and navigation; `Icon.jsx` shares presentation icons.
- **Conversational Application Demo**: Served via `/mitid` and `/application`, driven by `application_runtime.py` through `/application/init`, `/application/ask`, `/application/confirm`, and `/application/interpret`. Rendered by `demo-ui/src/ApplicationDemo.jsx`. It simulates an authenticated SU disability supplement application flow with a dual 50/50 conversational split and live structured form overview.
- **DCR Graph Authority**: DCR is authoritative for enabled/pending events, choice catalogues, execution transitions, navigation, field validation, and verbatim answer descriptions. The application does not read local XML or cached JSON to decide routing.
- **Graphs in Use**:
  - **2012661**: Standalone FAQ MVP source (`xml graphs/SU_handicaptillaeg_FAQ_MVP.xml`).
  - **Composite Graphs**: Combined FAQ + application models (e.g. `xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml`), where the application logic lives inside a `Form0` subprocess container. Graphs can be overridden in the UI via `?graphid=...`.

## Modules and boundaries

| File | Responsibility |
|---|---|
| `app.py` | HTTP routes, in-memory tab sessions, provider routing, error handlers |
| `dcr_repository.py` | DCR graph/simulation API access; raw simulation event polling and execution |
| `faq_runtime.py` | FAQ API catalogue extraction, confirmations, choice validation, answer acknowledgement, navigation presentation |
| `application_runtime.py` | Conversational application lifecycle, sequential step rendering from DCR marking, field validation, mid-application FAQ handovers |
| `openchat.py` | OpenAI SDK Structured Outputs: (1) FAQ candidate ranking, and (2) form field free-text value interpretation |
| `interaction_log.py` | Turn-by-turn audit logging for conversational steps, interpretation attempts, and completion to `interaction_logs/` |
| `chatnlp.py`, `questions.py`, `utility.py` | Legacy interpretation and presentation for non-FAQ graphs via DCR's remote ChatNLP service |

API-visible `tags` or `groups` identify `GlobalInterpreter`, `FAQHome`, `FAQTopicMenu`, `FAQAnswer`, `FallbackContact`, `ApplicationField`, `ApplicationSubmit`, and `ApplicationDemoFile`.

`external_scripts/graph_parser.py` and its package initializer are included as review tooling. Asynchronous parsing creates a human-readable cache using standard-library Python. Without it, normal chat works and `/api/parsed-graph/<id>` returns a controlled unavailable response.

## Interpretation and AI pipelines

The system uses three distinct interpretation mechanisms:

### 1. FAQ Intent Interpretation and Ranking (`openchat.rank` + `faq_runtime.py`)
- **Catalogue Projection**: `faq_runtime.catalogue` extracts all canonical questions from the currently enabled `GlobalInterpreter` event (e.g. `FAQ_GlobalQuestion`). The LLM never sees answer descriptions or XML relations.
- **Structured Outputs Ranking**: OpenAI receives the user's free text, the last confirmed question (to resolve elliptical context like *"What about that?"*), and the list of candidate keys. The model outputs `in_scope: bool`, `scope_reason: str`, and an ordered list of candidate scores (0.00–1.00).
- **Thresholds & Decision**:
  - `single_match`: Top score $\ge 0.80$ with margin over second place $\ge 0.12$.
  - `ambiguous`: Top score $\ge 0.50$ (returns top 2–3 matches).
  - `no_match`: Top score $< 0.50$ or out of scope.
- **Human-in-the-loop Confirmation**: The chatbot asks the user to confirm the match (*"Is this the question you mean?"*). Upon user confirmation, `faq_runtime.execute` executes that specific candidate on DCR.
- **Verbatim Delivery**: Executing the question makes exactly one `FAQAnswer` event pending in DCR. The server retrieves its description verbatim, executes the answer event to acknowledge it, and presents subsequent navigation.

### 2. Conversational Application Field Interpretation (`openchat.interpret` + `application_runtime.py`)
- **Prose-to-Data Parsing**: When an applicant types free-text instead of clicking buttons (e.g. *"I work about 4 hours on Tuesdays and 4 on Thursdays"*), `openchat.interpret` converts it to the exact data type DCR expects (`number`, `integer`, `choice`, or `choices`).
- **Context-Aware Extraction**: Uses `INTERPRET_PROMPT` to perform arithmetic (e.g. 4 + 4 = 8) and references earlier answers from the session.
- **Strict Verification**: Output is validated against DCR's permitted choice keys or numeric bounds (e.g. 0–168 hours) before submission.
- **Execution**: Validated values are executed on the active DCR field event to advance the application sequence.

### 3. Legacy Graph Interpretation (`chatnlp.py`)
- For non-FAQ graphs, `app.py` passes enabled events to DCR's remote `/api/chat` service. This proprietary server-side endpoint infers answers without local JSON schema validation or explicit score thresholds.

## Session and browser contract

`X-Session-ID` identifies an in-memory tab session. Sessions hold DCR credentials, graph/simulation IDs, recent events, execution history, last confirmed question, and active prompt tickets. Operations are serialized per session using threading locks.

- `POST /init` with `{graph_id}` initializes a simulation.
- `POST /chat` accepts `{message}` (free text), `{event_id, value}` (button click), or `{action: "confirm"|"reject", match_id, candidate_key}`.
- `POST /application/init` initializes a dedicated application session.
- `POST /application/ask`, `/application/confirm`, `/application/interpret` drive the conversational form steps.
- **Shared Simulation Context**: When FAQ and Application run in the same graph, an applicant can ask an FAQ question mid-form. `faq_runtime.py` answers the FAQ inquiry, acknowledges the answer, and hands control back to the waiting application question without resetting the applicant's progress.
- File-upload fields are simulated for demonstration: browser-selected or typed filenames are recorded as text in DCR; file contents are not read or uploaded.

## DCR calls

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/graphs/{id}` | Graph title, language, and XML specification |
| POST | `/api/graphs/{id}/sims` | Create a new DCR simulation instance |
| GET | `/api/graphs/{id}/simulation/{simid}/event` | Fetch current runtime events, markings (included, enabled, pending, executed), and choice catalogues |
| POST | `/api/graphs/{id}/simulation/{simid}/event` | Execute event with `{eventId, eventValue, comment, isNull}` |
| POST | `/api/chat`, `/api/chat/{chatid}` | Legacy remote non-FAQ NLP interpretation |

Authentication uses configured DCR token headers (`X-DCR-AuthToken`, `Bearer {token}`). Credentials and OpenAI keys are loaded locally from `.env`.

## Setup and diagnostics

See [README.md](README.md) for installation and environment configuration (`.env.faq.example`). Developer checks can be executed via:
```bash
python -m unittest discover -s tests
```
Audit logs and runtime diagnostics:
- `INFO:openchat:` includes message, context, model, rankings, decision, latency, and token usage.
- `INFO:faq_runtime:` logs confirmations and DCR marking transitions.
- `INFO:application_runtime:` logs step sequencing, field types, and validation decisions.
- `interaction_logs/*.jsonl` stores structured, turn-by-turn user session transcripts.
