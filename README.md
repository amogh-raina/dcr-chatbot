# DCR FAQ and application demo

A Flask/React demo for SU disability supplement questions and a simulated application. DCR controls the
conversation and application events. The retrieval pilot searches a reviewed FAQ catalogue, uses model
classifiers to assess relevance and context, and asks the person to confirm uncertain matches.

## Install and run

Use **Python 3.12**. From this repository's root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows use `py -3.12 -m venv .venv`, then `.venv\Scripts\activate`.
Copy [`.env.example`](.env.example) to `.env` and fill in credentials privately.
You need DCR access (`ROOT_URL`, `API_KEY`, optionally `TOKEN`) and `OPENAI_API_KEY` for model classifiers.
Never commit `.env` or put credentials into graph exports.

```sh
python app.py
```

Open `http://localhost:8080/demo?graphid=<your-imported-graph-id>`. `/` redirects to `/demo`.
The application demo is at `/application?graphid=<id>`, with simulated login at `/mitid?graphid=<id>`.
The UI's fallback ID is `2012701`; it is a historical default, not a guarantee of graph access or the latest revision.
For the current retrieval pilot, import the credential-free
[`SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml`](xml%20graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml)
and use the ID assigned by your Portal. See [deployment and effect setup](docs/guides/DEPLOY.md).

### Retrieval service

Retrieval graphs call a **separate search service** through a DCR effect. Install its dependencies in the same
environment and start it in a second terminal:

```sh
python -m pip install -r faq_search/requirements.txt
python -m faq_search.api
```

Set `FAQ_API_KEY` in `.env`, and configure the same key on the graph's retrieval Robots in the Portal.
The service defaults to `127.0.0.1:8090`; expose it to DCR through your deployment or tunnel.
The first start downloads the embedding model named in
[`faq_embeddings_meta.json`](faq_search/data/faq_embeddings_meta.json) (currently Qwen3-Embedding-0.6B).
The main app's `USE_LOCAL_RETRIEVER=1` setting also needs these dependencies for local matching.
`FAQ_MATCH_MODEL` names an OpenAI classifier, not the embedding model.

The included demo is fictional: login does not authenticate and attachments only record filenames.
Sessions are process-local. See [application behaviour](docs/guides/APPLICATION_DEMO.md).

## Development checks

```sh
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m unittest discover -s tests -t .
python scripts/check_repo.py
```

Ordinary unit tests run without model calls or weight downloads. Embedding quality checks are opt-in:
`RUN_RETRIEVAL_EVAL=1 python -m unittest discover -s tests -t . -p test_faq_retriever.py`.
Model/Portal evaluations and their prerequisites are described in [evals/README.md](evals/README.md).

Editing the React UI requires **Node.js 22.13+**:

```sh
cd demo-ui
npm ci
npm run lint
npm test
npm run build
```

Commit `static/demo/` with frontend source changes; the clean build removes obsolete hashed bundles.
GitHub Actions runs Python checks and verifies that the committed demo matches the source.
Python lint enforces correctness (`E4`, `E9`, `F`), while ESLint also checks React hook dependencies.
Dependencies remain pip requirements for now; a uv project/lock migration can be done separately.

## Repository map

| Path | Purpose |
|---|---|
| `app.py`, `dcrai/` | Flask endpoints, DCR boundary, chat/application flows, model calls, configuration and observability |
| `demo-ui/`, `static/demo/` | React source and deployable build |
| `templates/`, `static/script.js` | Older browser client |
| `faq_search/` | Search API, retriever, data builder and checked-in catalogue/vectors |
| `tools/clean_graph/`, `xml graphs/` | Reproducible current graph builder and reference graphs |
| `prompts/`, `evals/`, `tests/` | Model instructions, evaluation material and automated checks |
| `docs/`, `AGENTS.md`, `CLAUDE.md` | Documentation, shared agent guide, Claude import |
| `traces/` | Private runtime JSONL, registry snapshots and DCR snapshots; ignored except its README |

Start with [the documentation index](docs/README.md), [architecture](docs/architecture/Overview.md),
[agent guide](AGENTS.md), [DCR skill setup](docs/guides/DCR_SKILL.md), [trace format and readable exports](traces/README.md), and
[the repository review](docs/guides/REPOSITORY_REVIEW.md).

Optional browser checks: from `demo-ui/`, run `npx playwright install chromium`, then `npm run test:ui`.
They use a local mock backend and save ignored screenshots; see [the application guide](docs/guides/APPLICATION_DEMO.md).
