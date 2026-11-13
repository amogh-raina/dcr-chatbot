# Run and deploy the demo

## Prerequisites

Follow [the root setup](../../README.md) with Python 3.12. The main application requires
[`requirements.txt`](../../requirements.txt); the retrieval service and local semantic matching additionally require
[`faq_search/requirements.txt`](../../faq_search/requirements.txt). Development checks use
[`requirements-dev.txt`](../../requirements-dev.txt). Node.js 22.13+ is needed only to edit/rebuild React.

Copy [`.env.example`](../../.env.example) to `.env` and fill credentials privately. `ROOT_URL` defaults in the
example to `https://repository.dcrgraphs.net/` and must include its trailing slash. `FAQ_MATCH_MODEL` is an
OpenAI classifier model. The embedding model comes from `faq_search/data/faq_embeddings_meta.json`.

## Current retrieval graph

From the repository root, rebuild and validate the credential-free graph:

```sh
python tools/clean_graph/build_clean_graph.py
python .agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py "xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"
python tools/clean_graph/simulate_clean_graph.py "xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"
```

The builder defaults to `--outcome dmn`, adding the DMN machinery. Runtime `OUTCOME_MODE=code` still uses the
Python table; `shadow` compares DMN and code, and `dcr` requires the Portal acceptance checks in
[spec 03](../specs/03-graph-split-outcome-table-dmn.md). Do not switch to `dcr` merely because local tests pass.

Import the generated graph as a new Portal revision and record its ID. The runtime uses live simulations,
not local graph files. Open `/demo?graphid=<id>` or `/application?graphid=<id>` and start a new session.
Older graph files are retained as reference/rollback examples; their IDs are not current deployment configuration.

## Retrieval effect and separate service

1. Set `FAQ_API_KEY`, install the retrieval dependencies, and start `python -m faq_search.api`.
   It binds to loopback port 8090. `/health` is liveness only; a search request verifies retrieval readiness.
2. Make this service reachable by DCR, for example with `cloudflared tunnel --url http://127.0.0.1:8090`.
   Quick-tunnel URLs change when restarted.
3. In Portal Effect Administration, register/use `handicap-faq-v2` as an `Http.Get` effect:
   URL `https://<host>/api/faq/search?q=$(q)`, text parameter `q`, and optional text continuation parameters
   `ContinueOnOk`, `ContinueOnFail`, `ContinueOnTimeout`. Route HTTP 200–208 to ok, 408/504 to timeout,
   and other statuses to fail; parse the whole JSON body.
4. Import/attach the effect to **both** `FAQ_Retrieve` and `Help_Retrieve`. The `--with-effect` builder variant
   can supply declarations, but credentials are always set privately in the Portal.
   On the chat Robot use `q = FAQ_UserQuestion`; on Help use `q = Help_UserQuestion` (plain event expressions).
   Set `header#X-API-Key` to a **quoted** key. Continuations are quoted event IDs:
   `"FAQ_RetrievalOk"`, `"FAQ_RetrievalFail"`, `"FAQ_RetrievalTimeout"`, or the corresponding `Help_...` IDs.
5. Test a fresh simulation. Use the new `/api/graphs/{id}/simulation` API and the event's role when executing.
   The old `/sims/` engine does not run Robots/effects.

The API accepts `X-API-Key`, `X-DCR-AuthToken`, Bearer or Basic credentials. If the Portal sends its encrypted
stored token rather than the original key, add that value privately to `FAQ_API_EXTRA_KEYS`; it can change on
effect save. Do not commit it. The API logs credential sources/lengths, not values.
`--no-auth` is for local tests only. Query-string keys require `--allow-query-key` and may enter access logs.

## Docker

`docker build -t dcr-ai .` builds the main application with the committed `static/demo` bundle.
`docker run --rm --env-file .env -p 8080:8080 dcr-ai` starts it. The image installs only the main requirements;
run retrieval separately in an environment with its requirements/model. Do not expect the main image to provide
local embedding matching. Set `USE_LOCAL_RETRIEVER=0` for the older flow, or build an appropriate image with
the retrieval dependencies if you need that mode. The retrieval graph still requires its external search effect.

`docker compose up --build` is a local development configuration: it mounts the checkout over `/app` and loads
`.env`. It is not a deployment with authentication, durable sessions or a bundled search service.

## Operational limits and verification

The app uses process-local sessions and a simulated login. Put a real access-control layer in front before
exposing private graph access; multiple workers do not share sessions. Runtime traces contain verbatim applicant
text and must have access/retention controls. See [trace documentation](../../traces/README.md).

Run [development checks](../../README.md#development-checks), then the explicit Portal/model checks in
[evals/README.md](../../evals/README.md). Offline tests do not prove that credentials, effects, a graph import or
DMN execution work on a live deployment. Do not use real applicant data for demos.
