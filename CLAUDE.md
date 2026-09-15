# Agent orientation

Read `README.md` for setup and `Overview.md` for current architecture and endpoints.

- The primary chatbot is Flask (`app.py`), with FAQ presentation in `faq_runtime.py` and OpenAI ranking in `openchat.py`.
- DCR controls all runtime events, answers and navigation. Do not introduce an XML-derived runtime FAQ map.
- The main UI is `templates/index.html` + `static/script.js`; `demo-ui` is the React/Vite showcase using the same FAQ API flow (chat component: `demo-ui/src/SupportChat.jsx`). Rebuild it into `static/demo` after UI edits.
- The simulated login/application demo (`/mitid`, `/application` routes, `demo-ui/src/ApplicationDemo.jsx`) is driven by `application_runtime.py` via `/application/init` and `/application/answer`. Same rule as FAQ: it reads only live DCR events (labels, types, choices, pending state) — no local XML, no LLM. It runs its own DCR simulation, separate from the FAQ session, though both hang off the same `X-Session-ID`.
- File-upload fields in the application demo are simulated: a filename is recorded as text in DCR, never actually read or uploaded. Don't "fix" this into a real upload without being asked — see `APPLICATION_DEMO.md`.
- Only `external_scripts/graph_parser.py` and `__init__.py` are shared from that folder. The parser is review-only and uses standard-library dependencies; legacy LLM/explanation scripts remain excluded. The app also handles a missing parser.
- Never commit `.env`, logs, caches or excluded review material. Do not read `.env` to troubleshoot without explicit user authorization.
- Run `python -m unittest discover -s tests` for focused checks. Keep browser/live testing brief unless requested.
