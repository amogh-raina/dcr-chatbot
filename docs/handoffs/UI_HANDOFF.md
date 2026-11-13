# UI handoff: FAQ chat and application Help panel (written 2026-10-08)

Goal of the next session: improve the UI of the FAQ chat (`/demo`, floating SU-support widget) and of the application
page (`/application`), above all the "Ask in Help" entry and the Help panel (the chat window beside the form).
The backend and the DCR graph work and were tested live on graph **2014078**; this is front-end work. Keep the
backend contracts below unchanged unless a change is agreed first.

## 1. Where things are

| What | File |
|---|---|
| FAQ chat widget (launcher, panel, turns) | `demo-ui/src/SupportChat.jsx` (`RetrievalReply` renders retrieval turns) |
| FAQ landing page around the widget | `demo-ui/src/App.jsx` |
| MitID page, application page, Help panel | `demo-ui/src/ApplicationDemo.jsx` |
| Styles: FAQ page + chat | `demo-ui/src/styles.css` (has `:root` tokens `--ink`, `--chat-blue`, ...) |
| Styles: MitID + application + Help panel | `demo-ui/src/application.css` (no tokens; about 280 hard-coded hex colours) |
| Icons | `demo-ui/src/Icon.jsx` (inline SVG paths by name) |
| Built output served by Flask | `static/demo/index.html` + `static/demo/assets/` |
| Preview with mocked backend | `demo-ui/preview/preview.mjs` (new, see section 4) |

Components in `ApplicationDemo.jsx` (top to bottom): `AnswerBody` (safe HTML renderer, allows p, br, strong, em,
b, i, ul, ol, li, a), `MitIdDemo`, `FilePick`, `Answer` (field controls), `Composer` (form input with "Ask in Help"
and "Send answer"), `EditAnswer`, `FormControl`, `FormPanel` ("View form"), `ApplicationSidebar` (stepper,
documentation note, contact card, save/start again), `HELP_EXAMPLES`, `HelpPanel`, `ApplicationDemo` (state and
all request handlers).

## 2. How the Help panel works today (behaviour to preserve)

- **Entry points**:
  1. header "Help" button (unscoped),
  2. "Unsure about this question? Ask about the rules" link under the field (scoped to the field),
  3. "Ask in Help" button in the form composer (unscoped, sends the composer text),
  4. a form-composer message ending in `?`, or text typed on a file field (unscoped).
- **Layout**: the panel replaces the left sidebar column (`.application-page.with-help`). Below 1180px it is a fixed
  right drawer; below 600px the header buttons are icon-only. Opening Help closes "View form" and vice versa.
- **Field scope** shows a card at the top of the panel thread: field label, `field.help.html` (help text and
  option meanings from DCR) and related-question chips (`field.help.related`). A chip sends `{related: id}`. The
  scope chip "About: this question" above the input clears the scope.
- **Thread items** (`helpThread` kinds): `ask` (user bubble, optional "Searching for: ..." line), `notice`, `faq`
  (question, verbatim answer, "Source: ..."), `handover` (amber card). A pending match is rendered from `match`
  (confirm/clarify chips plus "No, that is not it" / "None of these").
- **Talk to a person** button in the panel composer posts `/application/handover`.
- After an answer the form gets a new prompt ticket; it is adopted silently (`asked.current`) so the form thread
  does not repeat the field.

## 3. Backend contracts the UI depends on (do not change without agreement)

Application (`dcrai/application/application_runtime.py`, all `POST`, header `X-Session-ID`):

| Endpoint | Request | Response used by the UI |
|---|---|---|
| `/application/init` | `{graph_id, demo_continue: true}` | view: `{status: question/review/complete/declined, field{id,label,type,options,multiple,help{html,topic,related[{id,question}]}}, prompt_id, answers[], form[]}` |
| `/application/answer` | `{prompt_id, value, source}` | view |
| `/application/interpret` | `{prompt_id or field_id, message}` | `{status: interpreted, value, display}` or `{status: not_interpreted, response, handover?}` |
| `/application/ask` | `{message, scope?: 'field'}` or `{related: id}` | `faq_confirm` / `faq_clarify` `{match_id, response, candidates[{candidate_key, question}]}`, `faq_no_match` / `faq_unavailable` `{response}`, `handover`; optional `searched_for`, `handover{reason, html}` |
| `/application/confirm` | `{match_id, candidate_key}` (`'none'` = none of these) | view + `{faq_id, faq_question, faq_response (HTML), faq_citation}`; or `faq_none {response, handover?}` |
| `/application/handover` | `{}` | `{status: handover, handover{reason, html}}` |
| `/application/edit` | `{field_id, value}` | view |

FAQ chat (`app.py` -> `dcrai/chat/retrieval_runtime.py`): `/init {graph_id}`, `/chat {message}` or `{action, ...}` (actions:
`reply`, `example {faq_id}`, `end {reason?: 'idle'}`, `apply`, `rephrase`). Turn shapes (`status`): `welcome`
(`response`, `examples[{id, question}]`), `options` (`prompt{id, kind, text, options}`; a single match is answered
directly since 2026-10-09),
`answer` (`answer{faq_id, question, html, citation}`, optional `prompt` for a follow-up determination, `actions`),
`determination_result` (`outcomes[]`), `out_of_scope`, `no_match`, `unavailable`, `ended`, `rephrase`,
`scope_check`, `navigate` (to `/mitid`). Optional `searched_for`. Reply buttons send
`{action: 'reply', retrieval_prompt_id, value}`.

Rules that stay: answer text and help text are shown **verbatim** from DCR / the retrieval record (render through
`AnswerBody`, never `dangerouslySetInnerHTML`); every answer shows its source; the form never changes because of a
Help question; no question or answer text in logs.

## 4. Build, preview, deliver

- **Build on the Mac**: `cd demo-ui && npm ci && npm run build` (writes `../static/demo`, replaces the assets).
  The Linux VM behind the device bridge cannot run the Mac `node_modules`; an agent builds in its cloud workspace
  (`npm ci && npx vite build`) and copies `static/demo/index.html` plus the new `assets/*` back.
- **Never delete `static/demo/assets/` itself.** Keep every file `static/demo/index.html` references, plus
  `icons8-bot-K3HB9ED8.gif` (FAQ widget). On 2026-10-08 the folder was removed during clean-up and every asset
  returned 404.
- **Preview without DCR**: `node demo-ui/preview/preview.mjs [outDir]` after a build. It serves `static/demo`, answers
  every endpoint above with canned replies (edit `MOCKS` to try other shapes) and saves 21 screenshots: FAQ welcome
  and answer; application field, Help card, options, answer, handover; each at 1440, 1024 and 390 px. Needs
  Playwright (`npm i --no-save playwright`, on macOS also `npx playwright install chromium`).
- Use the screenshots for a structured review (`/design:design-critique`, `/design:accessibility-review`).
- **Live check** after changes: `python app.py`, `/demo?graphid=2014078`, then "Start the application", and the
  test script in `CLAUDE.md` ("Run and test the application panel").

## 5. Observations from the 2026-10-08 screenshots (input, not decisions)

Help panel and application page:
1. **Too many ways in.** Four entry points (header Help, "Unsure about this question?", "Ask in Help", `?` rule)
   lead to the same panel with different scope. "Ask in Help" sits next to "Send answer" in the same weight, so the
   composer reads as two equal choices.
2. **One button style, three meanings.** The dashed ghost chip is used for "Ask in Help", "None of these" and
   "Talk to a person".
3. **The field card dominates.** With three related questions it fills most of the panel before any conversation;
   long questions become tall rounded pills. Option text is left-aligned in the card but centred in the match bubble.
4. **"Searching for: ..."** is small, grey, right-aligned and wraps; its purpose (showing what was searched) is not
   obvious.
5. **Panel header** has a tiny "Help" eyebrow over "Ask about the rules"; the context strip ("Your application is
   at ...") and the field card repeat the field label.
6. **Sidebar hidden while Help is open** (the panel takes its column), so the stepper disappears exactly when the
   applicant is unsure where they are.
7. **Phone**: the sidebar (stepper, Danish documentation note, contact card, save/start again) stacks above the
   form, so the question is far down the page; the header wraps "Back to SU-support".
8. **Language mix**: sidebar texts are Danish ("Krav til dokumentation", "Spørgsmål til SU?", stepper labels)
   while the rest is English.
9. **Hard-coded SU phone number** in the sidebar contact card; FAQ_P02 says the chatbot does not store contact
   details (the handover message points to SU.dk instead).

FAQ chat widget:
10. ~~"Start the application" appears twice after an answer~~: resolved 2026-10-09 (action chips removed).
11. ~~Paragraph spacing is lost inside the answer box~~: resolved 2026-10-09. Still open: the "Source:" line uses the
    same size as the answer.
12. **Bot avatar alignment**: the small bot mark sits beside the last row of a reply (the chips), not the first.
13. **Focus ring and accent colours differ** between the chat (warm orange focus ring, light-green apply button)
    and the application (blue `#0059b3`).

Shared:
14. **Two style systems**: `styles.css` has colour tokens, `application.css` hard-codes about 280 hex values. A
    small shared token set would make the two surfaces consistent.
15. **Accessibility checks** not yet done: contrast of grey helper text, keyboard order between form and panel, focus
    return when the panel closes, `aria-live` noise on the panel thread, touch-target size of chips on phones.

## 6. Questions to settle with Amogh before redesigning

- Should "Ask in Help" stay in the form composer, or should the field's own link and the header button be the only
  entry points?
- Help panel: keep it in the sidebar column, or as an overlay drawer at all widths so the stepper stays visible?
- Field card: always expanded, collapsed to "About this question" with an expand toggle, or shown only on request?
- One visual language for both surfaces (which one: the SU site look of the FAQ page, or the application's
  public-service look)?
- Language: English only, or Danish for the sidebar and form texts?
- Phone layout: should the stepper collapse to a one-line progress bar above the question?

## 7. Context from earlier decisions (do not undo without asking)

- Side panel (not inline answers in the form thread) was chosen on purpose: the form thread holds only the
  applicant's own answers.
- The scope is set by the applicant's click only; there is no "Ask about this answer" button (removed: in 7 of 8
  eval cases its search came back to the answer already shown).
- Field questions search the typed words first and add the field question only when none of the field's linked
  FAQs comes back (eval: 34/36 offered, 28/36 first; see `CLAUDE.md`).
- The handover card text comes from DCR (`Help_Handover`); keep "Talk to a person" always available.
- Field help text was reviewed by Amogh (`tools/clean_graph/field_help.json`, project doc
  `claude/field_help_review.md`); changing it means a graph rebuild and re-import.
