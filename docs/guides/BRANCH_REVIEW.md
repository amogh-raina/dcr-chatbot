# Branch review against main — 2026-11-13

Base: `origin/main` (`cfa461fb46948a6331b5c44ff2847d5d5683f23d`).
Reviewed branch: `experiment/faq-retrieval-determinations`, initially at `27afbe1`.
Main is an ancestor of this branch; the comparison includes the full retrieval/application pilot, not only
the latest repository-preparation commit. No open PR existed at review time; this was a branch-diff review.

## GitHub Actions

The [original pushed run](https://github.com/amogh-raina/dcr-chatbot/actions/runs/43456089362) succeeded.
Both `python` and `frontend` jobs passed, including audits, offline tests, browser checks and build consistency.
There was no failed workflow to repair. The findings below came from reviewing runtime and test behaviour.

## Findings corrected

1. **P1 — One slow application session blocked all other sessions.** The route installation used a single
   lock around entire Help/model/DCR operations. A pending network call held that lock for every user.
   The shared lock now only protects state lookup/publication, while each session serializes its own operations.
   A threaded regression verifies that a second session progresses while the first is blocked; a second check
   verifies that operations within one session still serialize.
2. **P2 — Clarification and confirmation answers lost their citations.** The search API emitted option answers
   without `optionN_citation`, although the runtime read that key. Every answer chosen from multiple candidates,
   including a list pruned to one candidate, therefore arrived without its source. The fixed-shape API now includes
   the option citations. A regression follows the real API payload through the chat runtime and user selection
   for one and two candidates, rather than testing only a synthetic runtime response.
3. **P2 — Help traces read the wrong retrieval continuation.** The recorder always read `FAQ_RetrievalOk`, while
   split application sessions use `Help_RetrievalOk`. It could record old chat scores or omit panel retrieval
   details. Event selection now matches the runtime surface, with the older graph fallback retained.
   The regression covers split panels, older panels and standalone chat with deliberately different scores.
4. **P2 — Ordinary fixture cleanup removed the offline network guard.** The suite-wide guard was registered
   through `mock.patch.start()`, so the many fixtures calling `patch.stopall()` removed it during discovery/tests.
   The process-wide test guard is now independent of that registry. A regression verifies that cleanup cannot
   restore network access. Opt-in embedding integration checks still permit model downloads.

The first three runtime regressions were reproduced against the original branch before the fixes.
The cleanup defect was also reproduced separately: the connect guard changed after `patch.stopall()`.
All corrections have regression coverage. The API change is additive; no graph policy, prompt or answer text changed.

## Validation and limits

The corrected branch passes Python lint, all 588 tests (7 intentional skips) and the 214-file repository
check locally.
The push following this review runs the same GitHub Actions workflow again; consult the latest branch run
for its hosted result. Frontend source and its committed build were not changed by these fixes.

This review does not verify a live Portal graph import, Robot effect credentials, DMN freshness on the remote
engine or model-answer quality. Existing deployment acceptance steps in the specs remain necessary.
The repository still uses pip requirements files; `pyproject.toml` configures Ruff, and no uv project migration
or uv.lock was introduced. See [setup](../../README.md) and [the broader repository review](REPOSITORY_REVIEW.md).
