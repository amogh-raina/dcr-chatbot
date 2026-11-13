# Historical architecture notes

Superseded by [the current overview](../architecture/Overview.md). Deployment IDs and commands below are historical.

# DCR Chatbot Architecture & System Overview

## 1. System Summary & Access

`app.py` runs a Flask application served via Waitress on port 8080.
- **Root URL (`/`)**: Automatically redirects to `/demo` (preserving query strings such as `?graphid=...`).
- **Demo Showcase (`/demo`, `/mitid`, `/application`)**: Serves a public-sector compliant (Det Fælles Designsystem) React application with a dual 50/50 conversational split and live structured form overview.
- **FAQ Support Chat**: Accessible via floating support widget or direct `/init` and `/chat` contracts.
- **Authority Boundary**: DCR process graphs are authoritative for enabled/pending state, choice catalogues, transitions, input validation, and decision logic. Local XML or JSON is never parsed at runtime to infer next-step routing.

---

## 2. Graphs in Use

| Graph File | ID / Role | Description |
|---|---|---|
| `xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml` | **Retrieval pilot (Current)** | One Robot calls the retrieval API through a DCR effect; no pre-modelled FAQ answers; four small determinations and the `Form0` application subprocess. See section 3b. The effect is attached in the Portal. Rebuild with `tools/clean_graph/build_clean_graph.py` (`--with-effect` also writes a variant carrying the unverified effect element). |
| `xml graphs/SU_handicaptillaeg_FAQ_Application_Lean.xml` | **Previous prototype (still used by `app.py` and the demo)** | Lean decoupled architecture: preserves `Form0` application subprocess, removes the 17 static answer events, and models interactive legal determination clusters (`FAQ05`, `FAQ16`, `FAQ21`, `FAQ37`) directly in DCR. |
| `xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml` | **Structured Reference** | Full composite model with `Form0` subprocess and 17 static topic/answer events. |
| `xml graphs/SU_handicaptillaeg_FAQ_MVP.xml` | **Legacy MVP (2012661 / 2012701)** | Standalone FAQ question-answer presentation graph without application subprocess. |

*Override*: Specify `?graphid=<ID>` in the URL to test against specific DCR Portal simulation instances.

---

## 3. Decoupled Architecture: Epistemic Knowledge vs. Operational Logic

A key design milestone in this project is the **clean decoupling** between:
1. **Epistemic Knowledge (What the rules are)**:
   - Factual answers to 55 questions: 43 guideline questions based on *Vejledning nr 9577 af 25/06/2025* and *SU-bekendtgørelsen*, plus 12 practical questions (`FAQ_P01`–`FAQ_P12`: how to apply, case status, documentation age, representatives, scholarships and similar) taken from `docs/sources/SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md`.
   - Managed in the local knowledge base (`faq_search/data/faq_qa_records.json`).
   - Retrieved via fast vector similarity search using `Qwen/Qwen3-Embedding-0.6B`.
   - **Crucial Rule**: Follow-up legal determinations ("hvis" exception logic) are **excluded** from plain text answer blocks to avoid monolithic text walls and preserve DCR as the single operational truth.
2. **Operational & Decision Logic (How rules apply to the user)**:
   - Interactive determinations and conditional branch evaluations are modeled **strictly in DCR**.
   - Executed through user event selections in DCR, making subsequent decision events pending.
   - Shared between pre-application FAQ exploration and mid-application assistance.

### Modeled Determination Clusters in DCR (Lean graph):
- **FAQ 05 / 05b (EU Worker Status)**:
  - Event: `FAQ05_Clarify_EUWorker` (choice: `Yes (1)`, `No (0)`).
  - Outcome: `FAQ05_Ans_Restricted` (10–12 hr/week requirement conflicts with work limitation) vs. `FAQ05_Ans_General` (equal status under 5-year rule).
- **FAQ 16 (Work Hours Threshold)**:
  - Event: `FAQ16_Clarify_WorkHours` (choice: `Under 5 hrs (1)`, `5–6 hrs or more (2)`).
  - Outcome: `FAQ16_Ans_Compatible` (likely compatible) vs. `FAQ16_Ans_Incompatible` (strong legal presumption against entitlement).
- **FAQ 21 (Medical Documentation Type)**:
  - Event: `FAQ21_Clarify_DocType` (choice: `Specialist hospital records (1)`, `GP notes only (2)`).
  - Outcome: `FAQ21_Ans_Specialist` (meets § 37 minimum) vs. `FAQ21_Ans_GPOk` (requires comprehensive clinical details; notes alone cause refusal to process).
- **FAQ 37 (Time-Limited Award Extension Window)**:
  - Event: `FAQ37_Clarify_Extension` (choice: `Within 3 months (1)`, `Expired or > 3 months (0)`).
  - Outcome: `FAQ37_Ans_ExtensionReady` (apply in minSU) vs. `FAQ37_Ans_ExtensionWait` (wait or file fresh un-backdated application).

---

## 3b. Retrieval Pilot Graph (`SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml`)

Everything a user can read comes from the retrieval API, so the graph holds no FAQ answers. It models only what must stay in DCR: the retrieval call, the follow-up determinations and the application form.

| Event | Role | Purpose |
|---|---|---|
| `FAQ_UserQuestion` | Chatbot | Input: the typed question. Executing it makes the Robot pending. |
| `FAQ_Retrieve` | Robot | The only Robot. Carries effect `handicap-faq` with `q` = `FAQ_UserQuestion`. Runs once, then is no longer pending. |
| `FAQ_RetrievalOk` | System | Effect continuation. Its value is the API's JSON (`decision`, `id`, `question`, `answer`, `option1_*` ...). |
| `FAQ_RetrievalFail`, `FAQ_RetrievalTimeout` | System | Continuations on failure and timeout; both make `FAQ_RetrievalUnavailable` pending. |
| `FAQ_DeterminationSelector` | Chatbot | One choice event the host executes. Items 1 to 4 are the canonical questions of FAQ_05b, FAQ_09, FAQ_31, FAQ_42; item 5 starts the application. |
| `Det05b_*`, `Det09_*`, `Det31_*`, `Det42_*` | Chatbot | Per FAQ: `_Ask` (yes/no, excluded until the selector opens it), `_Yes` and `_No` outcome labels. |
| `Form0` | subprocess | The application form, unchanged from the Structured graph. Selector item 5 includes and answers `Form0:Email`. |

Selector semantics: picking item *n* includes `Det_Ask` *n* and makes it pending; picking another item excludes the previous question; changing a yes/no answer closes the stale outcome. The Ask events start excluded so they cannot be executed on their own.

How the pieces are used: DCR stores the JSON but cannot parse it in a guard, so the host reads the value of `FAQ_RetrievalOk` from the live event API, shows `answer` (single match) or the options (clarify match), and executes `FAQ_DeterminationSelector` when the matched or asked question has a modelled determination. **This host side is not implemented yet** (`dcrai/chat/faq_runtime.py` and `app.py` still target the Lean/Structured graphs).

Effect binding in the Portal: `q` = `FAQ_UserQuestion` (the plain event ID, because parameters of type `text` reject `$(...)`), `ContinueOnOk` / `ContinueOnFail` / `ContinueOnTimeout` = the three System events above.

---

## 4. Modules and Responsibilities

| File / Component | Responsibility |
|---|---|
| `app.py` | Flask HTTP routes (`/`, `/demo`, `/chat`, `/application/*`), in-memory tab session management, request serialization locks. |
| `faq_search/build_faq_data.py` | Builds `faq_qa_records.json` from `docs/sources/Question_upmapping_chatbot.docx` (Vejledning nr 9577) and the 12 practical FAQs in the Expanded Q/A file. Strips determinations and authoring notes, attaches English phrasing variants, and validates the result before writing. |
| `faq_search/embed_faq_data.py` | Generates 1024-dim L2-normalized sentence embeddings using `Qwen/Qwen3-Embedding-0.6B` into `faq_embeddings.npy` and `faq_embeddings_meta.json`. |
| `faq_search/retriever.py` | Runtime semantic retrieval engine: fast vector dot products, max-variant scoring per FAQ record, confidence routing. |
| `faq_search/api.py` | Read-only search API for DCR dynamic effects: `GET`/`POST /api/faq/search` returns a flat JSON decision plus answer text. Separate process from `app.py`, API-key protected, never logs query text. |
| `dcrai/llm/openchat.py` | Intent ranking and form prose interpretation. Uses local `FAQRetriever` for fast, zero-API-cost semantic matching with optional OpenAI fallback. |
| `dcrai/chat/faq_runtime.py` | FAQ state machine: choice catalogue extraction, user confirmation management (`confirm_match` / `clarify_match`), answer acknowledgement, and mid-application handovers. |
| `dcrai/application/application_runtime.py` | Conversational form lifecycle (`Form0`), sequential field evaluation, data-type validation, and state persistence. |
| `dcrai/dcr/dcr_repository.py` | Raw HTTP communication with DCR REST simulation API (`/api/graphs/...`). |
| `dcrai/paths.py`, `dcrai/prompts.py` | Where every folder lives; loader for the model instructions in `prompts/`. |
| `prompts/` | Every model instruction as a text file, grouped by area (see `prompts/README.md`). |
| `evals/` | Evaluation runners (`python -m evals.<name>`), labelled cases, cached runs and reports (see `evals/README.md`). |
| `traces/` | Interaction logs and runtime snapshots written by the running system; gitignored (see `traces/README.md`). |
| `.agents/skills/dcr-xml-builder/` | Official DCR skill reference, XML validator (`validate_dcr_xml.py`), and documentation for robots, dynamic effects, and DMN. |

---

## 5. Interpretation & Retrieval Pipelines

### Pipeline A: Local Semantic Search & Ranking (`faq_search/retriever.py` + `openchat.rank`)
1. **Query Processing**: User message is embedded with `Qwen/Qwen3-Embedding-0.6B` and L2-normalized.
2. **Vector Matching**: Cosine similarity is computed via dot product against `faq_embeddings.npy` (one row per canonical question and phrasing variant; rebuilt by `embed_faq_data.py` whenever the records change).
3. **Record Aggregation**: The highest similarity among a record's variants determines the record's final score.
4. **Decision Thresholds**:
   - `single_match`: Top score $\ge 0.82$ and margin over runner-up $\ge 0.10$.
   - `clarify_match` (`ambiguous`): Top score $\ge 0.50$ (returns top 2–3 options as interactive chips).
   - `no_match`: Top score $< 0.50$ (triggers polite fallback / topic navigation).
5. **Execution**: If confirmed by user, `dcrai/chat/faq_runtime.py` executes the chosen event on DCR and presents the verbatim legal guidance and any follow-up determination chips.

### Pipeline A2: Search API for DCR Effects (`faq_search/api.py`)
- Exposes the same retriever to a DCR REST effect so query-to-question matching can run outside the graph. One call returns the decision and the answer text, with the thresholds taken from the same `FAQ_*` settings as Pipeline A.
- The graph still owns what happens next: the effect response is stored in `FAQ_RetrievalOk` and `ContinueOnOk` / `ContinueOnFail` / `ContinueOnTimeout` route the conversation (section 3b). Setup and tunnel steps are in `docs/guides/DEPLOY.md` section 7.
- Response: one flat JSON object. `decision` is `single_match` (id, question, answer, citation filled), `clarify_match` (up to three `option*` entries, answer empty) or `no_match`. Every key is always present.
- Auth: `X-API-Key`, `X-DCR-AuthToken`, `Bearer` or `Basic`; `FAQ_API_EXTRA_KEYS` accepts the encrypted token that DCR's token authenticator sends. A failed request logs which credential sources arrived and their lengths, never values or query text.

### Pipeline B: Conversational Form Interpretation (`openchat.interpret`)
- When free text is typed into application form fields (e.g. *"I work 4 hours on Tuesdays"*), `openchat.interpret` extracts the exact data type (`integer`, `number`, `choice`, `choices`).
- Context-aware arithmetic and cross-turn resolution are applied before validating against DCR bounds.

---

## 6. DCR Engine Invariants & Boundary Rules

Based on verified DCR engine documentation (`/dcr-xml-builder` skill):

### 1. Robot Execution Cycle (4 Phases)
When an activity executes, the DCR engine evaluates automated tasks in strict order:
1. **`Robot:Prime`**: Any enabled activity with role `Robot:Prime` runs first.
2. **User Activity**: The requested user action executes.
3. **`Robot` & `LocalRobot`**: Enabled pending automated events execute. `LocalRobot` runs within its local process instance without cross-process broadcasts.
4. **`Robot:Terminator`**: Any enabled activity with role `Robot:Terminator` runs last to clean up or finalize the cycle.
*Limit*: Max 256 robots per execution cycle (`MaxRobots`).

### 2. Dynamic Effect Continuations
- Dynamic effects carry completion paths: `ContinueOnOk`, `ContinueOnFail`, and `ContinueOnTimeout`.
- Target continuation events MUST use `<role>System</role>` so they remain hidden from end-user UIs.
- *Limit*: Maximum 64 consecutive continuations to prevent infinite cascade loops.

### 3. XML vs. Portal Configuration Boundary
- **Inside DCR XML**: Declare events, roles (`User`, `Chatbot`, `System`, `Robot`), groups/tags, and the effect binding with continuation targets. The exact serialization of an effect on an event is unverified: Portal 7.3 imports effects from the organization, and parameters of type `text` take a plain event ID, not `$(...)`. Export a graph with the effect attached in the Portal to confirm the real shape.
- **Inside DCR Portal (Effect Admin / Organization Registry)**: Define external REST endpoints, HTTP methods, headers, authentication secrets, and JSON payload mappings. Secrets and endpoint URLs are NOT hardcoded in raw graph XML.

---

## 7. Development, Testing, and Verification

### Environment Setup
All dependencies are installed in the `dcr` conda environment:
```bash
conda activate dcr
pip install sentence-transformers numpy torch transformers
```

### Running the Test Suite
All tests must pass before deploying or committing changes (the number grew with the retrieval work, so no fixed count is quoted here):
```bash
python -m unittest discover -s tests
python -m unittest tests.test_faq_api    # API only, fake retriever, no model needed
```
The model-based tests need `sentence-transformers` from `faq_search/requirements.txt`, so run them in the `dcr` environment.

### Regenerating Knowledge Base & Embeddings
If `docs/sources/Question_upmapping_chatbot.docx` is modified:
```bash
# 1. Rebuild records JSON
python faq_search/build_faq_data.py

# 2. Recompute embeddings
python faq_search/embed_faq_data.py
```

### Calibrating the Retrieval Thresholds
`evals/cases/eval_queries.json` holds labelled queries (in scope, on topic but unanswerable, off topic). `calibrate_thresholds.py` scores them with the real retriever, sweeps the single / minimum / margin thresholds, and prints a report with a recommended `FAQ_SINGLE_THRESHOLD`, `FAQ_MIN_THRESHOLD` and `FAQ_MARGIN_THRESHOLD`:
```bash
python -m evals.calibrate_thresholds --report evals/reports/calibration_report.md
python -m evals.calibrate_thresholds --from-scores   # re-sweep from cached scores, no model needed
RUN_RETRIEVAL_EVAL=1 python -m unittest tests.test_faq_eval   # optional quality gate with the real model
python -m evals.calibrate_thresholds --ab   # no query prompt vs the model's "query" prompt, side by side
```
`FAQ_QUERY_PROMPT` (default empty) makes the retriever prepend a prompt to the user query only; the stored questions are always embedded without one, so no re-embedding is needed. The value is a prompt name the model defines (Qwen3-Embedding has `query`) or literal text. Each prompt setting has its own score cache and its own best thresholds.
Re-run it after changing the records, the embeddings or the model, and add real user queries to the eval file as they arrive.

### Validating DCR XML
To ensure graph structural invariants before importing to Portal:
```bash
python .agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py "xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"
```
Output must report: `OK: 0 errors`.

### Running the Retrieval API and tunnel
```bash
export FAQ_API_KEY=...            # your key; never commit it
export FAQ_API_EXTRA_KEYS=...     # the token shown in the Portal effect editor (see docs/guides/DEPLOY.md section 7)
python -m faq_search.api          # terminal A, 127.0.0.1:8090
cloudflared tunnel --url http://127.0.0.1:8090   # terminal B, prints the public URL
```
Put the printed URL into the effect in Portal Effect Administration and save. The full runbook with every command is in `CLAUDE.md` ("Run everything").

### Starting the Server
```bash
python app.py
```
Open `http://localhost:8080/` (automatically redirects to `/demo`).
