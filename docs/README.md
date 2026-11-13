# docs/

All documentation except the root `README.md` (quick start) and `AGENTS.md` (shared agent guide; `CLAUDE.md` imports it).

| Folder | What belongs here |
|---|---|
| `architecture/` | How the system is built and why: `Overview.md`, `XHAIL.md`, `INTEGRATION_PLAN.md` |
| `guides/` | How to run, deploy and demo: `DEPLOY.md`, `APPLICATION_DEMO.md` |
| `handoffs/` | Dated session handoffs and next-session notes. Newest first by date in the file name |
| `sources/` | Inputs that the data build reads (guideline docx, practical FAQ markdown). Changing one means rebuilding `faq_search/data/` |
| `specs/` | Specs for planned work |
| `local/` | Personal notes, screenshots and packaged skills. Gitignored; not part of the repository |

New handoffs go in `handoffs/` named `HANDOFF_<date>_<topic>.md`.

## Start here

- [Run and deploy](guides/DEPLOY.md)
- [Install and use the DCR graph skill](guides/DCR_SKILL.md)
- [Repository review and tracking policy](guides/REPOSITORY_REVIEW.md)
- [Branch review against main](guides/BRANCH_REVIEW.md)
- [Current architecture](architecture/Overview.md)
- [Trace format and export](../traces/README.md)
- [Specs](specs/README.md)

Handoffs are historical and may contain superseded commands or IDs. Prefer the guides above.
