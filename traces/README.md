# Runtime traces

The runtime writes structured JSONL for analysis and separate DCR snapshots for debugging.
Everything under this directory is ignored by Git except this README. Traces include verbatim applicant text
and model input/output: keep raw files and readable exports private. Use synthetic fixtures in `tests/fixtures/`.

| Directory | Writer | Contents / setting |
|---|---|---|
| `interactions/` | `dcrai/observability/interaction_log.py` | One append-only JSONL file per interaction; `INTERACTION_LOG=0` disables it; `INTERACTION_LOG_DIR` overrides the path |
| `registry/` | `dcrai/registry.py` | Settings, prompt text/digests and FAQ data digests, once per registry version; excludes secrets |
| `runtime/` | `app.py`, `dcrai/dcr/dcr_repository.py` | DCR event snapshots and choice diagnostics; `RUNTIME_TRACE_DIR` overrides the path |

Paths come from `dcrai/paths.py`. Relative path overrides are relative to the launch directory.
An interaction is one chat or application session. The application Help panel has its own simulation and context.

## Schema 2 JSONL

Each line has `interaction_id`, `seq`, `at` (ISO timestamp), `elapsed_s`, and `kind`.
`start` includes `schema`, `interface`, `graph_id`, `simulation_id`, `graph_revision` and `registry_version`.
`graph_revision` is the graph ID plus a digest of the session's XML; `@unknown` indicates unavailable XML.

A `turn` record is written once when each traced chat/Help request finishes, including failures:

- Entry/action, verbatim message or selected input, interface, turn number and latency.
- Context, query rewrite, each search (query, scores, relevance and retained FAQ IDs).
- Model calls and DCR executions, outcome/row, FAQ IDs, reply status, reaction links and handover reason.
- Registry version and graph revision, plus exception type when a request raises.

Other records (`question`, `answer`, `edit`, `rejected`, `faq_ask`, `faq_answer`, `faq_outcome`, `faq_reaction`,
`handover`, `finished`) preserve individual steps. A reaction's `turn` names the earlier prompt it answers;
the current turn's `reacts_to` links back to it. Do not count both a `faq_outcome` and its `turn` outcome twice.
The complete field contract is in [spec 02](../docs/specs/02-registry-and-trace-record.md).

Long strings are truncated. A very large detail field may be omitted to bound the turn record; `truncated: true`
and `omitted_fields` make that loss explicit. The bound applies to turn records, not all form-answer records.
Named authentication values are redacted from structured DCR snapshots; this is not applicant-data anonymisation.
Logging faults are swallowed so a trace write cannot change the response.

## Read, validate and export

Run from the repository root; replace the path with a particular interaction file:

```sh
python -m dcrai.observability.trace_reader traces/interactions/ID.jsonl --check --rates
python -m dcrai.observability.trace_reader traces/interactions/ID.jsonl --format markdown --check > traces/interaction.md
```

The Markdown export groups turns with their message, outcome, search results, FAQ IDs, reaction and timing.
It escapes raw HTML; JSONL remains the complete machine-readable record. To preview using synthetic data:

```sh
python -m dcrai.observability.trace_reader tests/fixtures/trace_interaction_sample.jsonl --format markdown
```

`--check` fails on empty/corrupt files, missing start records, mixed interaction IDs, missing turn versions and
backwards/duplicate turn numbers. It does not verify a live graph or the content of an answer.
Schema 1 files using `interaction` remain readable. A live trace need not have a `finished` record.
Confirm acceptance counts each prompt once; repeated/orphan reactions cannot inflate it. Re-explain rates use
the next outcome's route, as described in [spec 01](../docs/specs/01-stop-wrong-answers.md).
