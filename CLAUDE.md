# Agent orientation

Read `README.md` for setup and `Overview.md` for current architecture and endpoints.

- The primary chatbot is Flask (`app.py`), with FAQ presentation in `faq_runtime.py` and OpenAI ranking in `openchat.py`.
- DCR controls all runtime events, answers and navigation. Do not introduce an XML-derived runtime FAQ map.
- The main UI is `templates/index.html` + `static/script.js`; `demo-ui` is a separate unfinished React/Vite showcase.
- Only `external_scripts/graph_parser.py` and `__init__.py` are shared from that folder. The parser is review-only and uses standard-library dependencies; legacy LLM/explanation scripts remain excluded. The app also handles a missing parser.
- Never commit `.env`, logs, caches or excluded review material. Do not read `.env` to troubleshoot without explicit user authorization.
- Run `python -m unittest discover -s tests` for focused checks. Keep browser/live testing brief unless requested.
