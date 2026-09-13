# DCR chatbot architecture

## Current application

`app.py` runs a Flask application through Waitress on port 8080. The main UI at `/` uses `templates/index.html` and `static/script.js`. The React/Vite showcase at `/demo` is served from `static/demo`; source and npm dependencies are in `demo-ui`. That showcase still targets an older graph and needs future integration work.

The current FAQ graph is **2012636**. Its source is `xml graphs/SU_handicaptillaeg_FAQ_MVP.xml`. DCR is authoritative for enabled/pending events, choice catalogues, execution, navigation, and answer descriptions. The application does not read XML or cached JSON to decide FAQ routing.

## Modules and boundaries

| File | Responsibility |
|---|---|
| `app.py` | HTTP routes, in-memory tab sessions, provider routing |
| `dcr_repository.py` | DCR graph/simulation API access; raw FAQ events bypass legacy XML compatibility |
| `faq_runtime.py` | API catalogue extraction, issued confirmations, choice validation, answer acknowledgement, navigation presentation |
| `openchat.py` | Official OpenAI SDK Structured Outputs ranking; configurable model/thresholds; validation and one malformed-output retry |
| `chatnlp.py`, `questions.py`, `utility.py` | Existing interpretation and presentation for non-FAQ graphs |

API-visible `tags` or `groups` identify `GlobalInterpreter`, `FAQHome`, `FAQTopicMenu`, `FAQAnswer`, and `FallbackContact`. The single enabled global selector supplies every canonical question, even after earlier execution. OpenAI sees only candidate keys/questions, the current message, and the last confirmed canonical question. Answers are never sent to or rewritten by the matcher. Scores are ranking heuristics, not probabilities.

`external_scripts/graph_parser.py` and its package initializer are included as review tooling. Asynchronous parsing creates a human-readable cache and uses only Python’s standard library. The other legacy scripts remain excluded. Without it, normal chat works and `/api/parsed-graph/<id>` returns a controlled unavailable response. Generated `parsed_graphs/` and `runtime_traces/` are also excluded.

## Session and browser contract

`X-Session-ID` identifies an in-memory tab session. Sessions hold DCR credentials, graph/simulation IDs, recent events, last confirmed question, and one issued match. FAQ operations are serialized per session. Restarting the server loses sessions; refresh/reload the graph afterward. This local testing app is not configured for a public multi-user deployment.

- `POST /init` with `{graph_id}` creates a DCR simulation and retrieves its events. API-marked FAQ graphs use OpenAI and never create a DCR ChatNLP session; other graphs retain the legacy path.
- `POST /chat` accepts `{message}` for free text, `{event_id, value}` for an explicit button, or `{action: "confirm", match_id, candidate_key}` for confirmation. Reject with `{action: "reject", match_id}`. Fallback actions are `topics`, `rephrase`, and `contact`.
- FAQ response `status`: `navigation`, `confirm_match`, `clarify_match`, `no_match`, or `answer`. Controlled state failures use `graph_state_error`.
- Suggestions expire after ten minutes or a new request/state change. Before execution, the server validates the issued candidate against fresh enabled events and the choice catalogue.
- A selected question must produce exactly one pending answer. Its description is returned verbatim; the server acknowledges that answer through DCR and retrieves the resulting navigation.
- The UI shows only the current menu's questions. Back/application controls sit above the input; their event/value comes from API choices. Free text still searches all topics.
- Legacy `/continue` and `/edit` do not bypass FAQ controls. `/api/validate-graph/<id>` checks access to a graph.

## DCR calls

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/graphs/{id}` | Graph title/language and optional review data |
| POST | `/api/graphs/{id}/sims` | Create simulation |
| GET | `/api/graphs/{id}/simulation/{simid}/event` | Current events and static choices |
| POST | `/api/graphs/{id}/simulation/{simid}/event` | Execute `{eventId, eventValue, comment, isNull}` |
| POST | `/api/chat`, `/api/chat/{chatid}` | Legacy non-FAQ interpretation only |

Authentication uses the configured DCR token headers. Credentials are supplied locally through environment variables or `.env`; `.env.faq.example` contains placeholders. OpenAI failure returns topic/contact fallback without invoking legacy ChatNLP. No live-agent transfer is implemented; the application-form option is still a placeholder.

## Setup and diagnostics

See [README.md](README.md) for installation. Python packages are in `requirements.txt`; optional demo development dependencies are in `demo-ui/package.json` and `package-lock.json`. The prebuilt demo needs only the Python server.

Logs go to the terminal. `INFO:openchat:` includes message/context, model, rankings, decision, latency, and usage. `INFO:faq_runtime:` shows confirmation and DCR transitions. SDK HTTP debug logs are disabled. Logs may include user-entered questions and should not be shared indiscriminately.

Developer checks: `python -m unittest discover -s tests`. Tests use mocked services; real DCR access and an OpenAI key are needed for a live chatbot session. Keep XML changes separate from application presentation changes; preserve canonical answers and validate changed graphs before importing.


## Topic exploration (local graph update)

The current XML adds `FAQ_Explored_1` through `FAQ_Explored_5`. DCR guards direct answer acknowledgement and Home re-entry to either the existing menu or the explored-topic choice. Conditions prevent executing that choice before every answer in its topic has executed. It offers Review questions and Back to topics; Review preserves history and responds to the original menu. Global questions cancel stale explored-topic obligations. Reading a repeated answer returns to the explored-topic prompt.

`FAQTopic:N` API tags associate menus, answers and explored events. `FAQHideRead` menus omit suggestions whose uniquely matching API answer label has executed; the original menu is shown in full after the graph-issued Review choice. This is presentation over API history, not an application completion counter. Only a pending `FAQTopicExplored` event produces the completion message. Existing untagged graphs keep their previous behavior.

The updated XML must be imported as a new graph before testing this behavior; graph 2012636 is the previously imported version. See `TOPIC_EXPLORATION.md` for the event/state table and relation effects.
