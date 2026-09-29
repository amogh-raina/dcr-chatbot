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
| `xml graphs/SU_handicaptillaeg_FAQ_Application_Lean.xml` | **Prototype (Current)** | Lean decoupled architecture: preserves `Form0` application subprocess, removes the 17 static answer events, and models interactive legal determination clusters (`FAQ05`, `FAQ16`, `FAQ21`, `FAQ37`) directly in DCR. |
| `xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml` | **Structured Reference** | Full composite model with `Form0` subprocess and 17 static topic/answer events. |
| `xml graphs/SU_handicaptillaeg_FAQ_MVP.xml` | **Legacy MVP (2012661 / 2012701)** | Standalone FAQ question-answer presentation graph without application subprocess. |

*Override*: Specify `?graphid=<ID>` in the URL to test against specific DCR Portal simulation instances.

---

## 3. Decoupled Architecture: Epistemic Knowledge vs. Operational Logic

A key design milestone in this project is the **clean decoupling** between:
1. **Epistemic Knowledge (What the rules are)**:
   - Factual answers to 43 authoritative questions based on *Vejledning nr 9577 af 25/06/2025* and *SU-bekendtgørelsen*.
   - Managed in the local knowledge base (`faq_search/data/faq_qa_records.json`).
   - Retrieved via fast vector similarity search using `Qwen/Qwen3-Embedding-0.6B`.
   - **Crucial Rule**: Follow-up legal determinations ("hvis" exception logic) are **excluded** from plain text answer blocks to avoid monolithic text walls and preserve DCR as the single operational truth.
2. **Operational & Decision Logic (How rules apply to the user)**:
   - Interactive determinations and conditional branch evaluations are modeled **strictly in DCR**.
   - Executed through user event selections in DCR, making subsequent decision events pending.
   - Shared between pre-application FAQ exploration and mid-application assistance.

### Modeled Determination Clusters in DCR:
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

## 4. Modules and Responsibilities

| File / Component | Responsibility |
|---|---|
| `app.py` | Flask HTTP routes (`/`, `/demo`, `/chat`, `/application/*`), in-memory tab session management, request serialization locks. |
| `faq_search/build_faq_data.py` | Builds `faq_qa_records.json` from `Question_upmapping_chatbot.docx` (Vejledning nr 9577), stripping determinations and attaching multilingual variants. |
| `faq_search/embed_faq_data.py` | Generates 1024-dim L2-normalized sentence embeddings using `Qwen/Qwen3-Embedding-0.6B` into `faq_embeddings.npy` and `faq_embeddings_meta.json`. |
| `faq_search/retriever.py` | Runtime semantic retrieval engine: fast vector dot products, max-variant scoring per FAQ record, confidence routing. |
| `openchat.py` | Intent ranking and form prose interpretation. Uses local `FAQRetriever` for fast, zero-API-cost semantic matching with optional OpenAI fallback. |
| `faq_runtime.py` | FAQ state machine: choice catalogue extraction, user confirmation management (`confirm_match` / `clarify_match`), answer acknowledgement, and mid-application handovers. |
| `application_runtime.py` | Conversational form lifecycle (`Form0`), sequential field evaluation, data-type validation, and state persistence. |
| `dcr_repository.py` | Raw HTTP communication with DCR REST simulation API (`/api/graphs/...`). |
| `.agents/skills/dcr-xml-builder/` | Official DCR skill reference, XML validator (`validate_dcr_xml.py`), and documentation for robots, dynamic effects, and DMN. |

---

## 5. Interpretation & Retrieval Pipelines

### Pipeline A: Local Semantic Search & Ranking (`faq_search/retriever.py` + `openchat.rank`)
1. **Query Processing**: User message is embedded with `Qwen/Qwen3-Embedding-0.6B` and L2-normalized.
2. **Vector Matching**: Cosine similarity is computed via dot product against `faq_embeddings.npy` (215 rows covering all canonical questions and phrasing variants).
3. **Record Aggregation**: The highest similarity among a record's variants determines the record's final score.
4. **Decision Thresholds**:
   - `single_match`: Top score $\ge 0.82$ and margin over runner-up $\ge 0.10$.
   - `clarify_match` (`ambiguous`): Top score $\ge 0.50$ (returns top 2–3 options as interactive chips).
   - `no_match`: Top score $< 0.50$ (triggers polite fallback / topic navigation).
5. **Execution**: If confirmed by user, `faq_runtime.py` executes the chosen event on DCR and presents the verbatim legal guidance and any follow-up determination chips.

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
- **Inside DCR XML**: Declare events, roles (`User`, `Chatbot`, `System`, `LocalRobot`), groups/tags, custom effect bindings (`<effect name="...">`), parameter expressions (`$(EventId)`), and continuation targets.
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
All 82 tests must pass before deploying or committing changes:
```bash
python -m unittest discover -s tests
```
*Current status*: **82 tests passed (`OK`) in ~10 seconds**.

### Regenerating Knowledge Base & Embeddings
If `Question_upmapping_chatbot.docx` is modified:
```bash
# 1. Rebuild records JSON
python faq_search/build_faq_data.py

# 2. Recompute embeddings
python faq_search/embed_faq_data.py
```

### Validating DCR XML
To ensure graph structural invariants before importing to Portal:
```bash
python .agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py "xml graphs/SU_handicaptillaeg_FAQ_Application_Lean.xml"
```
Output must report: `OK: 0 errors`.

### Starting the Server
```bash
python app.py
```
Open `http://localhost:8080/` (automatically redirects to `/demo`).
