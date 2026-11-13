# Repository review — 2026-11-13

Reviewed `/Users/lzp112/Projects/DCR.AI`, branch `experiment/faq-retrieval-determinations`,
remote `amogh-raina/dcr-chatbot`. The checkout already contained substantial staged and unstaged work.
That work and the index were preserved; no commit or push was made.

## Readiness

The prepared working tree is intended for review and commit as a coherent set. **The existing staged snapshot
is stale**: several required Python modules, prompts, tests and docs were untracked at the start, and the index
still names old demo bundles removed by the clean build. Do not commit only the previous staging.
After reviewing the changes, from the root run:

```sh
git status --short
python scripts/check_repo.py
git add -A
git diff --cached --check
git diff --cached --stat
```

Then commit and push the intended branch normally. These commands are instructions, not actions performed
by this review. The [file inventory](FILE_INVENTORY.md) distinguishes the existing index from current candidates.
Runtime traces, secrets, local notes/probes and caches remain ignored.

## Findings fixed

| Finding | Change |
|---|---|
| Main setup referenced deleted `.env.faq.example`, an obsolete graph and the wrong entry-page behaviour | Rewrote root setup, deployment, application guide and architecture from current code; linked the canonical `.env.example` and deployment-specific graph IDs |
| CLAUDE.md mixed current rules with 82 KB of dated/superseded session notes | Added concise shared AGENTS.md; CLAUDE.md imports it; preserved history under docs/handoffs/ |
| Reproduction inputs were ignored | Allowed the canonical source DOCX, current credential-free graph and tools/clean_graph; preserved reviewed source content |
| Evaluation helpers depended on an ignored with-effect graph | Pointed their metadata reads to the shared NoEffect graph, which carries the same form labels/tags |
| Required new runtime modules, registry/trace code, answer edits, prompts and tests were untracked | Identified them as commit candidates; they must be included when restaging |
| Multiple stale hashed frontend bundles accumulated | Clean Vite build leaves only the referenced JS/CSS and bot asset; automated checks detect stale/missing assets |
| No repository-owned lint or CI policy; an ancestor Ruff config influenced results | Added pyproject.toml correctness rules, explicit narrow import-order exceptions, ESLint/React hook checks, npm test commands and GitHub Actions |
| Missing hook dependencies and unused imports/locals | Corrected hook dependencies, removed unused imports and unused locals while retaining calls with side effects |
| Existing preview targeted older form controls, and Playwright was not declared | Declared the dependency, updated preview controls, added npm run test:ui, ignored its screenshot outputs |
| Test discovery could download an embedding model; fresh-install tests could attempt unmocked fallback HTTP calls | Gated embedding integration checks and added offline/credential-free test bootstrap; documented package discovery with -t . |
| Python dependency audit found 39 advisories in eight pinned packages | Updated certifi, Flask, idna, Jinja2, python-dotenv, requests, urllib3 and Werkzeug; updated Flask's blinker requirement; verified a fresh Python 3.12 installation |
| npm audit reported two high-severity affected packages | Updated Vite to 8.3.8 and source-map-js resolution; moved build tools to devDependencies; audits now report zero known vulnerabilities |
| Importing helper modules enabled global DEBUG; dotenv was loaded after modules captured settings | Moved logging ownership to the entry point, loaded environment before runtime imports, and reduced question/context logging |
| Generic server errors could return exception details | Replaced the generic exception response with a stable public error message |
| Runtime DCR diagnostics could contain named auth parameter values | Redacted named auth fields/parameters before snapshot persistence without mutating runtime state |
| Empty/corrupt trace files could pass checks; duplicate reactions could inflate rates; outcomes could be double-counted depending on record order | Added integrity checks, deduplicated outcomes/reactions and bounded oversized turn details |
| JSONL was difficult to read | Added Markdown turn export with message, outcome, searches, FAQ IDs, reaction and latency; documented the schema and commands |
| No portable guide for the bundled DCR graph skill | Added DCR_SKILL.md and an installer for Codex, Claude or a custom skill directory; copies the full bundle and refuses overwrite |

Advisory references for the frontend fixes: [source-map-js](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)
and [Vite/launch-editor](https://github.com/advisories/GHSA-587h-7wmj-h5pm). Audits are a point-in-time check,
not a guarantee against unknown vulnerabilities.

## What belongs in Git

- Application code, prompts, synthetic tests/fixtures, configuration examples, dependency manifests/lockfile,
  current docs, the DCR skill and graph-generation source.
- FAQ records, embedding metadata/vectors and answer edits. The ~1.1 MB vector file is a required runtime
  artifact, not an accidental cache; model weights are downloaded separately and are not committed.
- The current credential-free graph and existing reference graphs. Several historical variants remain because
  tests, DMN examples, specs or rollback references use them; do not bulk-delete them as generated junk.
  The blanket ignore rule still prevents new ad-hoc/credential-bearing exports from appearing automatically.
- Synthetic evaluation runs/reports are retained as reviewable baselines; they are distinct from real interaction
  logs. Historical handoffs are labelled as historical and do not override the current guide.
- The deployable React build is intentionally committed so running Flask does not require Node.js.
  Obsolete hashed bundles are irrelevant and were removed by rebuilding.

Excluded: `.env` and other local env files, virtual environments, node_modules, Python/test/lint caches,
`.jj`, local `.claude` settings, AI/, docs/local, parsed_graphs, runtime traces and readable trace exports,
screenshots, nonshared legacy scripts, ad-hoc Portal probes and nonapproved graph exports.
`.gitignore` does not retroactively untrack files: existing reference graphs stay tracked deliberately.

The scanner checks current candidate text for common token/private-key patterns without printing values.
It is not a full historical-secret or personal-data audit. No `.env` was inspected for troubleshooting.

## Verification

| Check | Result |
|---|---|
| Original baseline in existing dcr environment | 575 tests, 1 skipped, passed (included embedding integration checks) |
| Fresh Python 3.12 with patched requirements-dev.txt | 583 tests, 7 intentionally skipped, passed; ordinary tests blocked from network |
| Python Ruff, including shared graph builders/parser | Passed |
| Frontend ESLint with React hook checks | Passed |
| Node session-ID tests | 2 passed |
| Clean Vite production build | Passed; obsolete bundles removed |
| Local browser mock scenarios | Passed at desktop/intermediate/phone widths; 43 explicit thread assertions passed |
| Python runtime and full installed development/retrieval environment audits | Zero known vulnerabilities reported |
| npm dependency audit | Zero known vulnerabilities reported |
| Current NoEffect graph structural validation | 0 errors, 0 warnings |
| Local graph simulator, including session split and outcome/DMN paths | 0 failures |
| FAQ record reproduction | All 55 records match source build, excluding generated updated_at dates |
| Docker main-app build | Passed |
| Docker smoke test, network disabled/no credentials | Root redirect, demo/application pages and missing-session rejection passed |
| Clean copy containing only commit candidates | 583 tests passed, 7 skipped; lint and 212-file repository check passed; full staged diff against the original HEAD passed whitespace checks |
| Trace sample validation, rates and Markdown export | Passed; synthetic sample reports 50% confirm acceptance and 75% re-explain rate |

GitHub Actions now runs lint, unit tests, repository checks, dependency audits, browser checks and frontend
build consistency. The local checks do not constitute a hosted GitHub Actions run.

## Remaining limits and follow-up

- **Live deployment is not certified by this review.** Portal import, both effects, live API credentials,
  DMN/shadow behaviour and model quality still require the explicit acceptance steps in spec 03 and evals/README.md.
  OUTCOME_MODE=code stays the default. No new live model/Portal evaluation was requested or performed.
- This is a simulated-login pilot. Sessions are in memory, are not shared across processes, have no application
  authentication boundary or expiry policy, and disappear on restart. Production hardening is separate work.
- Trace redaction targets named authentication fields; traces still contain applicant text and may contain
  arbitrary secrets supplied as free text. Access/retention policy and safe handling remain necessary for real data.
- Docker intentionally installs only main-app dependencies; retrieval is a separate service. For older local
  matching inside the image install retrieval dependencies or set USE_LOCAL_RETRIEVER=0.
- Dependency ranges remain for OpenAI and retrieval packages. This review did not migrate the project to uv
  or add a fully hashed Python lock; a reproducible dependency-lock migration can be a separate change.
- ESLint 9 is pinned because the current eslint-plugin-react peer range supports 9, not 10. npm reports this
  ESLint release as unsupported; upgrade the compatible lint stack together when practical. No audit advisory
  is reported for the installed stack.
- No repository licence was found; no licence was invented. Choose one separately if public reuse is intended.

## Current guides

- [Run and install](../../README.md)
- [Deployment / both DCR effects / Docker](DEPLOY.md)
- [Application and browser checks](APPLICATION_DEMO.md)
- [DCR skill installation and usage](DCR_SKILL.md)
- [Shared agent instructions](../../AGENTS.md)
- [Traces and Markdown export](../../traces/README.md)
- [Evaluation commands](../../evals/README.md)
