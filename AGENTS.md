# DCR.AI agent guide

This is the shared guide for Codex and Claude. Read [README.md](README.md) for setup,
[the documentation index](docs/README.md) for deeper references, and the relevant spec before changing behaviour.
The current retrieval pilot lives on `experiment/faq-retrieval-determinations`; do not switch branches automatically.

## Architecture and boundaries

- `app.py` is the Flask entry point, served by Waitress on port 8080. `/` redirects to `/demo`;
  `/demo`, `/mitid` and `/application` serve the React build. The older browser client remains in `templates/` and `static/script.js`.
- DCR is the runtime authority for events, choices, pending state, answers and navigation. Use the live
  `/api/graphs/{id}/simulation` engine, including event roles. The old `/sims/` engine does not run Robots.
  Do not introduce an XML-derived FAQ routing map. XML hydration already present in the repository boundary
  fills metadata missing from API responses; it must not bypass DCR execution or enabled-state checks.
- `dcrai/chat/faq_runtime.py` handles Lean/Structured FAQ graphs; `retrieval_runtime.py` handles retrieval graphs.
  `outcome.py` defines the outcome table; `outcome_runtime.py` bridges code/shadow/DMN modes to DCR.
- `dcrai/application/application_runtime.py` handles the separate application simulation and its Help panel;
  `panel_context.py` stores Help context in DCR. Both browser surfaces use `X-Session-ID`.
  File uploads are simulated: only a filename is recorded. Do not add real uploads without a request.
- `dcrai/dcr/dcr_repository.py` owns DCR HTTP calls; `dcrai/llm/` owns model calls;
  `dcrai/legacy/` supports the older non-FAQ flow; the optional `external_scripts/graph_parser.py` is for review caches.
- `faq_search/api.py` is the separate retrieval service (default loopback port 8090) invoked by DCR effects.
  The FAQ catalogue and vectors live in `faq_search/data/`; rebuilding records requires the two sources in `docs/sources/`
  and `faq_search/answer_edits.json`. The embedding model is recorded in `faq_embeddings_meta.json`.

## DCR graph skill

For building, debugging, reviewing or explaining a DCR graph, load
[the bundled DCR XML Builder](.agents/skills/dcr-xml-builder/SKILL.md), then its relevant semantic/XML/REST references.
See [installation and agent examples](docs/guides/DCR_SKILL.md). Codex discovers the repository skill directly;
other agents can follow SKILL.md manually or install the full folder. Preserve source graphs and separate semantic
claims, structural validation and unverified Portal behaviour.

## Where changes belong

- Prompts: `prompts/<area>/<name>.txt`, loaded through `dcrai/prompts.py`. Policy governing DCR routing belongs
  in the graph builder. Changing model input requires an evaluation; never silently rewrite policy or answers.
- Settings: `dcrai/registry.py`, documented in `.env.example`. Secrets never enter registry snapshots.
  `dcrai/paths.py` owns runtime paths. Preserve registry and prompt versions on traces and evaluation output.
- Graph generation: `tools/clean_graph/`; source graph `xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml`.
  Build with `python tools/clean_graph/build_clean_graph.py` (`--outcome dmn` is the builder default;
  runtime `OUTCOME_MODE=code` remains the default). `--with-effect` adds effect declarations, never credentials.
  Validate with `.agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py` before importing a graph.
  Portal graph IDs are deployment-specific: pass `?graphid=<id>`, and start a new chat after graph changes.
- Tests: `tests/`; model/network evaluations: `evals/`, with synthetic inputs in `evals/cases/`.
  Keep reviewed baselines/reports in Git. Keep runtime interactions and personal applicant data out of Git.
- Documentation: `docs/architecture/`, `docs/guides/`, `docs/specs/`; dated handoffs in `docs/handoffs/`.
  [Historical notes](docs/handoffs/PROJECT_HISTORY_through_2026-10-12.md) are background, not current instructions.

## Verification

Install `requirements-dev.txt` in a fresh Python 3.12 environment. Run from the repository root:

```sh
python -m ruff check .
python -m unittest discover -s tests -t .
python scripts/check_repo.py
cd demo-ui
npm ci
npm run lint
npm test
npm run build
```

Ordinary tests must not call paid models or download weights. Embedding integration checks are opt-in:
`RUN_RETRIEVAL_EVAL=1 python -m unittest discover -s tests -t . -p test_faq_retriever.py`.
Run model/Portal evaluations explicitly using [evals/README.md](evals/README.md).
After frontend edits rebuild `static/demo/`; Vite removes obsolete bundles. Commit the build with its source.
The Python lint policy checks correctness (`E4`, `E9`, `F`); it does not enforce a wholesale style migration.

## Safety and release scope

- Preserve unrelated changes and existing staging. Do not commit or push unless asked.
- Never read `.env` to troubleshoot without explicit authorization. Do not print keys or write them into graphs,
  logs, examples, fixtures or documentation. `.env.example` contains placeholders only.
- Runtime JSONL and snapshots in `traces/` contain verbatim applicant text. They are ignored, including Markdown
  trace exports. Use fictional data for demos. See [traces/README.md](traces/README.md) for format and commands.
- This is a demo with simulated login and process-local sessions, not an authenticated production applicant service.
  Live DCR/DMN behaviour requires Portal checks in [spec 03](docs/specs/03-graph-split-outcome-table-dmn.md).
  Do not claim a live deployment was verified by unit tests.
