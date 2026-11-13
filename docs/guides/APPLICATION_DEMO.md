# Application demo

## Run

Follow [the root installation guide](../../README.md) and [deployment/effect setup](DEPLOY.md).
Start `python app.py`, then open `http://localhost:8080/mitid?graphid=<your-imported-graph-id>`.
Starting the server does not open a browser automatically. `/application?graphid=<id>` opens the application
surface; the graph must include the required application events. Both screens use the committed React bundle.

For a retrieval graph, also install `faq_search/requirements.txt` and run `python -m faq_search.api` in another
terminal. Configure the effect on both retrieval Robots. Restart the app after `.env` changes and start a new
application after importing a revised graph. The UI fallback ID is historical; pass the intended graph ID explicitly.

## What is simulated

The login is a visual demo, not authentication. File fields record filenames as text; no attachment is uploaded
or read. Use fictional personal/medical details. State lives in the running process and is lost on restart.
This demo does not submit a real benefits application.

## Form conversation

`dcrai/application/application_runtime.py` reads the live DCR simulation for fields, labels, choices, descriptions,
groups and marking. Each accepted answer executes its DCR event; pending/enabled state selects the next step.
Stale prompt tokens and marking changes reject replayed submissions. Help actions check that form marking stays
unchanged. The application simulation is separate from the standalone FAQ chat simulation.

The application UI (`demo-ui/src/ApplicationDemo.jsx`) presents questions and accepted answers as a thread:

- Single choices and yes/no options submit with one click. Multiple choices require Continue.
- Number/text questions use the bottom composer. A plain numeric input submits directly; words requiring
  interpretation are shown as a suggestion that the person confirms. The backend still validates the value.
- Pencil controls edit earlier accepted answers. Later answers may be rewound according to the graph flow.
- Rejected input is restored to the composer and the error appears in the application thread.
- The fixed header/composer surround a scrolling thread. Theme controls apply to application/login surfaces.

The form itself does not use an LLM to choose the next field. Typed-answer interpretation can call a model.
The progress display is a presentation aid, not a separate source of workflow state.

## Ask SU-support

The Help panel uses the current field's help text/topic/related FAQ tags when question context is on. The person
can ask a general question with that context off. It uses relevance/context classifiers and the separate search
service, offers confirmation or related questions, and may ask modelled follow-up determinations or offer a
human handover. `Panel_Context` stores its context when enabled; `Help_UserQuestion` and `Help_Retrieve`
separate its retrieval from the standalone chat. `OUTCOME_MODE=code` remains the default.

See [architecture](../architecture/Overview.md), [spec 02](../specs/02-registry-and-trace-record.md),
[spec 03](../specs/03-graph-split-outcome-table-dmn.md) and [trace format](../../traces/README.md).

## Check the UI without credentials

From `demo-ui/`:

```sh
npm ci
npx playwright install chromium
npm run lint
npm test
npm run build
npm run test:ui
```

The browser scripts in `preview/` run a local mock backend, take desktop/mobile screenshots, and check chat
and application behaviour. Screenshots in `preview/shots*` are ignored. They do not verify DCR effects or real
model quality. For live verification follow [evals/README.md](../../evals/README.md).
