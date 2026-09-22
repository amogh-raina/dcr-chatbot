# Conversational application demo

Branch: `feature/demo-application-flow`. This is a simulated login and submission, not a real MitID integration or an official SU application service.

## Run

1. Import `xml graphs/SU_handicaptillaeg_FAQ_Application_Demo.xml` into DCR as a **new graph**, and note its ID. The existing MVP and supplied form are preserved.
2. Restart `python app.py` using your normal environment.
3. Open `http://localhost:8080/demo?graphid=NEW_ID`, open support, and choose **Proceed to application**.
4. At `/mitid`, choose **Continue demo**. No credentials are requested. Start the conversational application and use fictional information only.
5. Review the answers and choose **Send demo application**. The requested e-Boks confirmation wording is shown alongside an explicit notice that nothing was submitted and no message will be sent.

You can also open `/mitid?graphid=NEW_ID` directly. The default remains MVP `2012701`; use the newly imported graph ID for this experiment. Restarting the app or starting again loses the in-memory application session. Review is read-only in this iteration; changing prior answers requires starting again.

## How it works

- The login design is adapted from the separate Next.js replica. This repository now serves its own `/mitid` and `/application` pages from the built React demo.
- `/application/init` creates a new DCR simulation. `ApplicationForm` and `ApplicationStart` API tags identify the entry choice. The application session is separate from the FAQ session.
- `application_runtime.py` reads **only the DCR event API** for labels, data types, choices, inclusion, enablement, pending state and explicit application tags. It does not parse local XML or call an LLM.
- Each submitted value executes its DCR event. The next included, enabled, pending application field becomes the next question. If no application step is pending, the handler accepts exactly one included and enabled application step, matching the live form API behaviour observed on graph 2012720. Multiple available steps remain an error; no pending flags are changed. Prompt tokens and marking checks reject stale/replayed requests.
- Date/month, text, long text, numbers, choices, booleans and email controls are supported. The supplied graph uses a subset. Files are intentionally simulated: a browser-selected or typed filename is recorded as text in DCR; the file contents are never read or uploaded. No file storage, email delivery or e-Boks integration exists.
- The demo graph changes its two `file` events to text with an `ApplicationDemoFile` tag. This is a deliberate simulator accommodation, not evidence that DCR lacks a file datatype. Real uploads need a separate upload/Form Server integration.
- The final modeled completion event is acknowledged through DCR before displaying the confirmation. A declined demo consent follows a separate cancellation event.

## Layout and UI Design

The interface is built to public-sector design standards (reflecting the official *Det Fælles Designsystem* styling of NemLog-in and su.dk) while keeping interactions smooth, conversational, and non-robotic.

### 1. Dual Layout & 50/50 Form Split
- **Default View (Sidebar + Centered Application)**:
  - When the form overview is closed, the screen presents a clean two-column view: guidance sidebar on the left (~320px) and the conversational application centered in a comfortable reading width.
- **Open Form View (50/50 Half-and-Half Split)**:
  - When the user opens the form overview, the left sidebar automatically collapses and the screen transitions into a balanced **50% application / 50% form overview** split (`1fr 1fr`).
  - This eliminates cramping and allows the applicant to compare their conversational answers directly against the structured form overview.
  - Closing the form (via `Hide form` in the top header or `✕` on the form panel) immediately restores the default sidebar layout.

### 2. Single "View form" Toggle Control
- Only **one** primary toggle for the form exists in the interface, positioned in the top-right header (`View form` / `Hide form`). Redundant duplicate toggles in the sidebar have been removed for visual clarity and predictable navigation.

### 3. Left Sidebar Guidance (`ApplicationSidebar`)
The left sidebar anchors applicant orientation with three core blocks:
- **Faser i ansøgningen**: A 5-stage progress roadmap:
  1. *Studieoplysninger* (Indskrivning & uddannelsessted) — marked with an active `I gang` badge when current.
  2. *Funktionsnedsættelse* (Lidelsens art & varighed).
  3. *Arbejdsevne & job* (Erhvervserfaring & timer).
  4. *Lægelig dokumentation* (Speciallægeerklæring).
  5. *Gennemse & bekræft* (Samlet oversigt & kvittering).
  Stages update dynamically with completed checkmarks based on the current DCR step.
- **Krav til dokumentation**: Highlights that documentation must substantiate concrete functional loss in relation to holding a student job, not merely state a diagnosis.
- **Spørgsmål til SU?**: Official helpline reference (`Man–fre 9.00–15.00 · Tlf. 72 31 79 00`).
- **Sidebar Actions**: Contains `Save session` (visual preview button for future persistence) and `Start again` (session reset with confirmation).

### 4. Natural, Non-Robotic Conversational Interface
- **Clean Speech Bubbles**: Repetitive robot avatar icons on every message turn have been removed. Turns are styled as clean, lightweight speech bubbles with high readability and subtle elevation.
- **Language**: Interactive controls, buttons, placeholders, choice chips (`Yes`/`No`), and confirmation messages are in **English**, matching the DCR graph's language.
- **In-place Editability**: Completed answer turns feature the dedicated rounded-square pen edit icon (`Icon name="edit"`). Clicking it allows re-interpreting answers or picking different choices without restarting the entire simulation.
- **Support Chatbot Integration (`SupportChat.jsx`)**: The floating FAQ support launcher features an animated guide bot, while internal message bubbles remain clean, legible, and un-robotic.

## Form adjustments

The 15 supplied fields are embedded in `Form0`. Responses and matching includes select each next step; completed fields self-exclude to prevent editing earlier branches in this initial version. A milestone protects the Send event against outstanding included field obligations.

- Application fields start excluded and non-pending; choosing the entry option activates the first field after the demo login screen.
- A congenital impairment bypasses the permanence follow-up, but still asks about an existing time-limited award.
- An acquired impairment marked permanent continues to the award question; other permanence choices ask about duration first. No answers automatically decide eligibility.
- Previous work = No still asks about planned work during studies.
- Hours are collected only for the corresponding Yes answer.
- The vague consent placeholder is now explicitly **demo consent to continue with fictional data**, not legally operative consent.
- No stops the demonstration. Yes continues to simulated attachments, review/Send and completion.
- No computational activities or Robots are needed for these branches; guarded relations control them.

The FAQ graph stays reusable; the application portion is one pass per simulation. Only `FAQ_Home` is initially pending. After the final application message is acknowledged, its path has no remaining included pending obligations. This is process completion, not delivery to an authority.

## Validation and limits

XML structural validation passed with zero errors/warnings. Focused offline tests cover the main conditional routes, cancellation, validation, replay rejection and completion. The React production build passed. Live DCR import/execution and real rendering still require checking; browser preview was blocked by an unavailable browser security-policy check. In particular, the live API must expose the embedded field IDs and tags as modeled.

No authentication or login data is collected. Fictional application answers and filenames are sent to the DCR simulation, where simulation data may remain. Do not use real personal or medical details for this demo.

Project copy of the XML: `outputs/dcr_conversation/SU_handicaptillaeg_FAQ_Application_Demo.xml` in the ChatGPT project. Repository copy: `xml graphs/SU_handicaptillaeg_FAQ_Application_Demo.xml`. Neither original input XML is overwritten.

## MISC.
One trade-off worth naming: the tag and the attribute can drift. If someone flips multiple back to false in the Portal but leaves the tag, your UI will still offer a checklist while DCR expects one value. Keeping both in sync is a manual discipline, the same way the DMN value and <definitions> have to be kept in sync. If that becomes a real risk, the honest fix is to detect it at import time rather than trust it.