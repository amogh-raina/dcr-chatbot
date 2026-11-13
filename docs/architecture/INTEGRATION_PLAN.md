> Historical pilot plan. Use [current architecture](Overview.md), [deployment](../guides/DEPLOY.md), and [spec 03](../specs/03-graph-split-outcome-table-dmn.md) for the implemented system. Commands and graph IDs below are historical.

# Plan: connecting the retrieval graph to the chatbot application

Status: plan only. Nothing in this file is implemented yet. Written 2026-10-06 on branch `experiment/faq-retrieval-determinations`.

## 1. Goal and boundary

The chatbot (`app.py`, `dcrai/chat/faq_runtime.py`, UI) should run on `xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml` (the effect is attached in the Portal):

1. The user types a question. The host executes `FAQ_UserQuestion` in DCR.
2. DCR's Robot `FAQ_Retrieve` calls the search API through the `handicap-faq` effect. The JSON lands in `FAQ_RetrievalOk`.
3. The host shows the answer from that JSON, or asks the user to pick between options.
4. If the matched question has a modelled follow-up (FAQ_05b, FAQ_09, FAQ_31, FAQ_42), the host executes `FAQ_DeterminationSelector`. DCR then drives the yes/no question and the outcome.
5. If the user wants to apply, the host executes the selector with the application value and the existing application flow (`Form0`) takes over.

Rules kept from `CLAUDE.md`: DCR controls events, enablement and navigation. The host reads only live DCR events. No XML-derived FAQ map. The only new input to the host is the JSON value stored in DCR by the effect. The LLM ranking call (`openchat.rank`) is not used on this path.

## 2. What exists and what does not fit

| Piece | State |
|---|---|
| Search API (`faq_search/api.py`), effect `handicap-faq`, tunnel | Working. A simulation executes the Robot and returns JSON. |
| Clean graph | Validated, simulated locally, imported in the Portal. |
| `dcrai/chat/faq_runtime.py` | Built for the Lean/Structured graphs. Does not fit, see below. |
| `dcrai/application/application_runtime.py` | Reusable, one gap in `start()`. |
| UI (`demo-ui/src/SupportChat.jsx`, `static/script.js`) | Renders menus, confirm and clarify chips, answers. No yes/no determination step. |

Why `dcrai/chat/faq_runtime.py` does not work on the Clean graph, from reading the code:

- `view()` requires exactly one pending `FAQHome` or `FAQTopicMenu` event. The Clean graph has none, so it raises `Expected one pending navigation event`.
- `execute()` requires exactly one pending `FAQAnswer` event and treats any other pending event as an error. After the selector runs, `Det*_Ask` is pending and is not an answer, so it raises.
- Ranking goes through `openchat.rank`, which the retrieval path replaces.
- `application_runtime.start()` looks for a group `ApplicationStart:<event>:<value>` on `Form0`, and otherwise for a pending `FAQ_Home`. The Clean graph has neither, so "start application" fails with `The application entry is not available.`

What already fits:
- `catalogue()` needs exactly one enabled `GlobalInterpreter` choice event. `FAQ_DeterminationSelector` has that group, so the catalogue of canonical questions works unchanged.
- `is_application_event()` matches ids starting with `Form0:`, so the form events are recognised.
- `dcr_repository.get_raw_events` and `execute_raw_event` can execute `FAQ_UserQuestion` and read `FAQ_RetrievalOk`.

## 3. Design decisions

1. **Add a separate module `dcrai/chat/retrieval_runtime.py`** instead of bending `dcrai/chat/faq_runtime.py`. `app.py` picks the flow per graph: if the live events include `FAQ_UserQuestion`, use the retrieval flow, otherwise the existing flow. The Lean graph and the demo keep working, and `?graphid=` still selects the graph.
2. **Match the selector by label.** The selector's choice labels are the canonical questions. The host compares the JSON `question` (single match) or the picked option's question with the labels from `catalogue()`. An exact match means "this FAQ has a determination" and gives the value to execute. No local FAQ map, no XML read.
3. **Show the answer from the JSON.** DCR does not store answers any more. `answer` and `citation` come from `FAQ_RetrievalOk`. Options carry their own `answer`, so picking an option needs no second search call.
4. **Single match is shown directly** (the thresholds already require score and margin). Clarify match shows up to three chips and then the picked option's answer. No match shows the fallback text. This replaces the old "Is this the question you mean?" step; keep that step as a switch only if you want it back.
5. **Failure path stays in DCR.** `FAQ_RetrievalFail` and `FAQ_RetrievalTimeout` make `FAQ_RetrievalUnavailable` pending. The host shows its description and acknowledges it. Whether to fall back to `openchat.rank` in that case is an open decision (section 8).

## 4. Phases

### Phase 0: probe the live event API (no code changes)
Questions only a real DCR call can answer. Run once with a throwaway script that creates a simulation, executes `FAQ_UserQuestion` with a real question, and prints the events (not credentials):

- Does the raw event list include System-role events such as `FAQ_RetrievalOk`, with `value`, `executed`, `enabled`, `pending`?
- Is the JSON value complete, or truncated by a text length limit? (Single answers are a few hundred characters; clarify responses carry three answers, roughly 2 to 3 KB.)
- What do `label`, `description`, `choiceValues`, `groups` and `tags` look like on `Det05b_Ask`, `Det05b_Yes` and the selector?
- How long does the execute call take with the effect inside it? (Expect well under the 30 s request timeout; the effect timeout is 10 s.)

Exit criterion: a printed, reviewed sample payload saved as a test fixture.
If System events are hidden or the value is truncated, stop and adjust the graph (see section 6) before any host code.

### Phase 1: small graph changes (build script `build_clean.py`, then re-import)
1. Add the group `ApplicationStart:FAQ_DeterminationSelector:5` to `Form0`. `application_runtime.start()` already reads this tag, so no host change is needed for the hand-over. The group must also be declared in the graph's groups list.
2. Decide the no-match message (section 8). If it should live in DCR, add a label event for it and a way to reach it. Otherwise the host shows static text.
3. Regenerate with `python tools/clean_graph/build_clean_graph.py`, re-validate (`validate_dcr_xml.py`), re-run `tools/clean_graph/simulate_clean_graph.py`, import the NoEffect file and attach the effect in the Portal again.

### Phase 2: backend (`dcrai/chat/retrieval_runtime.py`, small changes in `app.py`)
Request handling, all under the existing per-session lock (`faq_lock`):

| Request | Host does |
|---|---|
| typed message | Execute `FAQ_UserQuestion` with the text. Refresh events. If `FAQ_RetrievalUnavailable` is pending, return its description and acknowledge it. Otherwise parse the `FAQ_RetrievalOk` value (must be a JSON object with `decision`). Store it with a short-lived id (like `faq_match`). |
| `single_match` | Return the answer (`answer`, `citation`, `id`). If the question matches a selector label, also execute the selector with that value, then return the pending `Det*_Ask` as a yes/no step. |
| `clarify_match` | Return up to three chips (`optionN_id`, `optionN_question`). |
| chip picked | Look the option up in the stored JSON, return its answer. Same determination check as above. |
| yes / no | Execute `Det*_Ask` with `true` or `false`. Return the pending outcome label (its description) and acknowledge it. |
| `no_match` | Return the fallback text and the contact option. |
| start application | Execute the selector with value 5 (or call `application_runtime.start`), then continue with the existing application turns. |

Guards to keep from the old runtime: stale-request rejection (compare marking, issued id with expiry), only execute events that are currently enabled, one request at a time per session, no secrets in logs, query text never logged.

Stale-value risk: `FAQ_RetrievalOk` keeps its last value. Read it only in the same locked request that executed `FAQ_UserQuestion`, and treat a missing or unparsable value as failure. If the same question is asked twice the value may be identical, which is harmless.

### Phase 3: UI
- Reuse the existing `answer`, `clarify_match` and navigation rendering where possible. Add one new status for the determination step (question text plus Yes and No buttons) in `demo-ui/src/SupportChat.jsx` and in `static/script.js`.
- Show the `citation` under answers.
- Rebuild the demo (`cd demo-ui && npm ci && npm run build`) and check `/demo` and the main widget.

### Phase 4: tests
- Unit tests with the Phase 0 fixture and fake `repo` calls, in the style of `tests/test_faq_mvp.py` and `tests/test_structured_application.py`: single match with and without a determination, clarify then pick, no match, retrieval failure, bad JSON, stale request, yes then no (stale outcome), application hand-over.
- Keep the existing 147 tests passing in the `dcr` environment.
- `python -m unittest discover -s tests`

### Phase 5: end-to-end check (real DCR, tunnel, API)
1. Start the API and the tunnel, update the effect URL and the token (see `CLAUDE.md`, "Run everything").
2. `python app.py`, open `http://localhost:8080/demo?graphid=<Clean graph id>`.
3. Walk the script in section 7. Watch the API terminal: one request per typed question, no 401.
4. Test a special-character question (`is it A & B? it's 100% fine #1`) and confirm the API logs the full length.
5. Stop the tunnel and ask a question: the unavailable message must appear and the chat must stay usable.

### Phase 6: hardening for a longer pilot
- Fixed hostname for the API instead of a quick tunnel, or run it next to `app.py` on the Scaleway host (`ai-sop`) behind HTTPS. Update the effect URL once.
- Rotate `FAQ_API_KEY` (it appeared in the Portal form), update the effect token and `FAQ_API_EXTRA_KEYS`.
- Decide where the API runs and who restarts it. Today it needs a terminal and the model loaded (a few seconds at start).
- Log only ids, decisions, scores and latencies. The API already does this.

## 5. Dependencies and order

Phase 0 gates everything. Phase 1 can run in parallel with writing Phase 2 code against the fixture. Phase 3 needs the response shapes from Phase 2. Phase 5 needs all of them plus a live tunnel.

## 6. If the probe fails

| Finding | Response |
|---|---|
| System events or their values are not in the raw event list | Give `FAQ_RetrievalOk` a visible role (keep the continuation behaviour) or read the simulation log (`sims/{id}/log`) instead, then retest. |
| Value truncated | Add a second small effect output or shorten the payload: change the ok output transformer to a JSONPath that returns only `id`, `question`, `decision` and fetch the answer text from the API through a host call. |
| Execute call too slow | Raise the effect timeout, keep the API warm, check the cache. |
| Effect cannot be attached in the Portal | Use the NoEffect graph route and Portal export to learn the real effect XML, as described in `CLAUDE.md`. |

## 7. Acceptance script

| Step | Expected |
|---|---|
| Ask "Can I get handicaptillæg if I'm not a Danish citizen?" | Single or clarify match, answer shown with citation, then the FAQ_05b yes/no question. |
| Answer Yes, then change to No | Yes outcome shown, then replaced by the No outcome (stale outcome closed). |
| Ask "What if I miss the 4-week deadline for appealing?" | FAQ_42 answer and question. Previous unanswered question is gone. |
| Ask a vague question ("medical documents") | Clarify chips, picking one shows its answer. |
| Ask something off topic | No match, fallback text. |
| Ask something without a determination | Answer only, no yes/no step. |
| Choose "start the application" | Application questions start at the email field. |
| Stop the tunnel, ask a question | Unavailable message, chat still works. |

## 8. Open decisions for you

1. Keep the "Is this the question you mean?" confirmation for single matches, or show the answer straight away (proposed).
2. No-match and fallback contact: static host text (simplest) or a DCR event?
3. If the search API is down: show only the unavailable message (proposed), or fall back to the old OpenAI ranking?
4. Should the retrieval flow replace the Lean flow in `/demo`, or live next to it behind the graph id (proposed)?
5. Where the API runs for the pilot: your laptop plus tunnel, or a hosted service.
6. Add determinations beyond the four (each is an Ask/Yes/No cluster plus a selector item), and when.

## 9. Known gaps and risks

- The XML shape of an effect on an event is still unverified; the NoEffect file is the safe import.
- URL-encoding of special characters by DCR is untested.
- The Portal re-encrypts the effect token on every save, so each save needs an update to `FAQ_API_EXTRA_KEYS` and an API restart. A hosted setup should settle on one auth method first.
- Quick tunnels change URL on every restart and are meant for testing.
- Fictional data only until the API runs on a host you control, because the query passes through Cloudflare and DCR.
