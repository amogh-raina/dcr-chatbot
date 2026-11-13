# Architecture

## Runtime flow

The React client (`demo-ui/src/`) talks to Flask (`app.py`) with an `X-Session-ID`. Flask stores chat and
application state in memory. Application operations are serialized per session, so another session
can continue while one session waits for a model or DCR request. `/` redirects to `/demo`; `/demo`, `/mitid`, `/application` serve the same built
React application. The old `templates/index.html` / `static/script.js` client is retained for reference.

`/init` creates a DCR simulation. Graphs with `FAQ_UserQuestion` use `dcrai/chat/retrieval_runtime.py`;
other supported FAQ graphs use `faq_runtime.py`. DCR controls enabled events and pending navigation.
The repository adapter uses `/api/graphs/{id}/simulation` and event roles; it does not use `/sims/`.

In the retrieval flow the host executes triage and question events. DCR runs a retrieval Robot, which calls
the separate `faq_search.api` service. This service embeds the query with the model named in the checked-in
metadata, searches the FAQ vectors, and returns a flat payload for the effect continuation. Model classifiers
judge relevance, context and follow-ups; the host returns reviewed answer text rather than generating policy.

## Application and Help

`dcrai/application/application_runtime.py` creates an independent simulation for the application, driven by
live form events. The form thread supports typed/chosen answers, interpretation with confirmation, editing
and review. Login and document upload are simulated; filenames are stored, files are not uploaded.

The Help panel shares the application simulation while using its own search events (`Help_UserQuestion`,
`Help_Retrieve`, `Help_Retrieval*`). `panel_context.py` reads/writes `Panel_Context` when available. The
graph's `Session_Chat` / `Session_Panel` gates separate the two surfaces. Follow-up determinations default
to the panel (`FOLLOWUP_SURFACE=panel`).

## Outcomes, configuration and traces

`dcrai/chat/outcome.py` defines the outcome table. `outcome_runtime.py` executes its outcome in DCR;
`OUTCOME_MODE=code` is the default, `shadow` compares the DMN, and `dcr` requires live acceptance checks.
The graph builder defaults to including DMN machinery, which does not itself enable DCR decision mode.
See [spec 03](../specs/03-graph-split-outcome-table-dmn.md).

`dcrai/registry.py` owns typed settings and versions prompts/configuration/data digests. `dcrai/prompts.py`
loads text from `prompts/`; routing policy also lives in the graph builder. `dcrai/paths.py` defines folders.
Structured interaction records and per-request turn records are documented in
[traces/README.md](../../traces/README.md). Registry snapshots contain no secrets.

## Endpoint groups

| Endpoint | Purpose |
|---|---|
| `POST /init`, `POST /chat` | Initialize and continue a FAQ/chat simulation |
| `POST /application/init`, `/application/answer`, `/application/edit` | Start, answer and revise the simulated form |
| `POST /application/interpret` | Interpret a typed form answer before confirmation |
| `POST /application/ask`, `/application/confirm` | Ask Help, then select/confirm a FAQ |
| `POST /application/determination`, `/application/handover` | Determination reply and human handover |
| `GET /api/validate-graph/<id>`, `/api/parsed-graph/<id>` | Graph access check and optional cached review output |
| Separate service: `GET/POST /api/faq/search`, `GET /health` | Authenticated retrieval and unauthenticated liveness |

Request/response shape and implementation details are covered by the endpoint tests in `tests/`.
The service is a pilot with no real login and no shared/durable sessions. It is not a production applicant backend.
See [deployment](../guides/DEPLOY.md) and [the repository review](../guides/REPOSITORY_REVIEW.md) for limits.

## Reproducible inputs

Graph generation uses `tools/clean_graph/` and the Structured source graph. FAQ generation reads the DOCX and
practical FAQ markdown under `docs/sources/`, then applies `faq_search/answer_edits.json`. Records and vectors
are versioned together. Historical graph exports remain reference material, not deployment selection.

See [the root setup](../../README.md), [shared guide](../../AGENTS.md), [spec index](../specs/README.md), and
[historical architecture](../handoffs/ARCHITECTURE_before_2026-11-13.md).
