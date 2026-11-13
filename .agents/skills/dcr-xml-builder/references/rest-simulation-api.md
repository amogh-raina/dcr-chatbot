# DCR REST simulation API (Robots and effects)

Verified on repository.dcrgraphs.net, 2026-10-07, against a graph with a Robot that calls an organization HTTP effect. Treat anything not listed under "Verified" as unconfirmed.

## Contents
- Two engines
- Routes (new engine)
- The execute body and the role
- Effect parameters on a Robot (quoting rules)
- Continuations and where the result lands
- Observed XML for an effect on an event
- Error messages and their causes
- Not available / unconfirmed

## Two engines
- `/api/graphs/{id}/simulation...` is the new engine. It runs Robots and their effects in the same request as the user event.
- `/api/graphs/{id}/sims...` is the old engine. It does not run Robots by itself, and executing a Robot explicitly there marks it executed without running its effect. Do not use it to drive graphs with Robots.

## Routes (new engine)
| Purpose | Call | Result |
|---|---|---|
| Create | `POST /api/graphs/{id}/simulation` (empty body) | 201, simulation ID in header `X-DCR-simulation-ID` |
| Read events | `GET /api/graphs/{id}/simulation/{simid}/event` | 200 JSON: `isAccepting`, `events[]` with `id`, `label`, `roles`, `dataType`, `value`, `included`, `enabled`, `pending`, `executed`, `choiceValues`, `tags`, `description`, `eventType` |
| Execute | `POST /api/graphs/{id}/simulation/{simid}/event` | 204 on success; the whole step (user event, Robots, continuations) rolls back on error |

Auth headers as for the rest of the repository API: `X-DCR-AuthToken: <api key>` and, if used, `Authorization: Bearer <token>`.

The `Location: /api/Simulation/{simid}` header returned on create gives 404 on GET. There is no known full-payload or log read for this engine.

## The execute body and the role
```json
{"eventId": "FAQ_UserQuestion", "eventValue": "the user's text", "comment": "", "isNull": false, "role": "Chatbot"}
```
- **Send `role`.** If the executed event, or anything it triggers, runs a Robot with an effect, a missing role gives 500 `Value cannot be null. (Parameter 'input')` in under 100 ms, before any HTTP call. The Portal always sends the user's role, which is why the same graph works there.
- Use the event's own role from the event list (`roles`, first entry). Events without a role execute fine without one.
- Executing a Robot directly needs its role, e.g. `"role": "Robot"`.

## Effect parameters on a Robot (quoting rules)
The effect is defined at organization level (Effect Administration: implementation, URL, authentication, declared parameters, outputs). The graph only binds values to the declared parameters on the Robot event.

- The effect's URL refers to its parameters as `$(name)`, e.g. `https://host/api/faq/search?q=$(q)`.
- On the Robot, a **text parameter value is evaluated as an expression**:
  - Unquoted event ID → that event's **value**. `q` = `FAQ_UserQuestion` sends the user's question.
  - Quoted → a literal string. Use quotes for constants: `header#X-API-Key` = `"<key>"`.
  - `$(...)` on the Robot is rejected by the simulator: "Parameters of type 'text' cannot use '$(...)' syntax".
- Parameter names `header#<Name>` become HTTP request headers.
- Only parameters declared on the effect appear on the Robot. After changing the effect's parameters, re-import the effect into the graph; re-import can drop the quotes from existing values, so check them.

## Continuations and where the result lands
- To route the outcome, the effect must declare `ContinueOnOk`, `ContinueOnFail`, `ContinueOnTimeout` (text, not mandatory, empty default), and the Robot must set them to **quoted** event IDs: `"FAQ_RetrievalOk"`, `"FAQ_RetrievalFail"`, `"FAQ_RetrievalTimeout"`. Give the continuation events the role `System`.
- With continuations: on an ok output the response body (json transformer, whole body) becomes the value of the Ok event, and that event is executed in the same request. On a fail output the Fail event is executed with the error body as its value.
- Without continuations: the response body stays as the value of the Robot event itself, and no follow-up event runs.
- Read the result from the event list (`value` of the continuation event). It may be a JSON string; parse it, and parse again if the result is still a string.

## Observed XML for an effect on an event
From a Portal export (a Robot with an organization effect attached):
```xml
<event id="A1">
  <custom>
    <roles><role description="" specification="">Robot</role></roles>
    <eventType>handicap-faq</eventType>
    <eventTypeData>
      <parameter required="true" title="q" value="&quot;What is DCR&quot;" type="text" />
    </eventTypeData>
    ...
  </custom>
</event>
...
<resources><custom>
  <eventTypes><eventType description="">handicap-faq</eventType></eventTypes>
  <eventParameters>
    <parameter required="true" title="q" value="" type="text" eventtypeid="handicap-faq" />
  </eventParameters>
</custom></resources>
```
The quoted value (`&quot;...&quot;`) is a literal; an unquoted value is an expression (usually an event ID). Values of `header#...` parameters are stored in clear text in the graph, so treat graph exports and event lists as containing secrets.

## Error messages and their causes
| Message | Cause |
|---|---|
| 500 `Value cannot be null. (Parameter 'input')` on execute | No `role` in the body while a Robot with an effect runs |
| 409 on create: `Runtime error evaluating <Robot>@parameter(<name>): [0605] Unknown activity id '<value>'` | A literal parameter value is missing its quotes |
| 500 `Runtime error evaluating <Robot>@effect: [0905] Unknown continuation 'ContinueOnFail=undefined'` | ContinueOn values set to unquoted event IDs (evaluated to the event's value) |
| Portal: `unknown activity id '"true"'` | ContinueOn set to something other than an existing event ID |
| Portal: `No value for mandatory parameter 'ContinueOnTimeout'` | ContinueOn declared mandatory on the effect; make them optional |

## Not available / unconfirmed
- No REST read of the full simulation payload or log on the new engine.
- Behaviour of `LocalRobot`, `Robot:Prime` and `Robot:Terminator` over REST was not tested.
- Whether a wrong (not missing) role is rejected was not tested; the runtime option `detectRoleMismatch` was `false`.
## Authoring organization effects and attaching them to a graph

Observed in Portal Effect Administration (live.dcrgraphs.net/effects), 2026-10. Field names follow the Portal form.

**Build the effect (Effect Administration, Edit Custom Effects)**
1. **Id and description**: a stable, versioned id (`handicap-faq-v2`). A new id is safer than editing an effect that graphs already use.
2. **Authentication**: a named method plus an authenticator type (`Anonymous`, `HttpBasicAuthenticator`, `HttpTokenAuthenticator`, `HttpOAuth2Authenticator` and others). The token authenticator stores the token encrypted, re-encrypts it on every save, and rewrites its header (`X-DCR-AuthToken`, later seen as `Authorization`), so the receiving API sees a different 88-character value after each save. An authenticator choice did not always survive a save (Anonymous came back as token); recheck after saving.
3. **Implementation**: `DCR.Workflow.Effect.Http.Get` for lookups (a before-effect: its output becomes the value, failures abort the step, safe to repeat); `Http.Post` only for side effects (an after-effect, result visible only through a continuation). Others: `Const` (fixed value, useful as a control), `Graph`, `Mail`, `Http.Put/Patch/Delete`.
4. **Arguments**: `URL` with `$(name)` placeholders for declared parameters (`https://host/api/faq/search?q=$(q)`), `timeout` in seconds (10 is enough for a warm lookup), `accept` (`application/json`).
5. **Effect Parameters**: one row per value the graph supplies (name, required, type, default). Declare `ContinueOnOk`, `ContinueOnFail`, `ContinueOnTimeout` here (text, not required, empty default) or the graph cannot route the result. `header#<Name>` rows become request headers; a default value there is stored in clear text and copied into every graph that imports the effect.
6. **Output**: rows of status codes -> continuation (Ok/Fail/Timeout), format (`json`, `string`, `dcr`, `preserve`), apply to (PRE/POST/ALL), value expression. Working default: 200-208 Ok `json` ALL with an empty expression (whole body), -408/408/504 Timeout `preserve`, everything else Fail `preserve`.
7. **Advanced -> Finalized Configuration: JSON** is a read-only view of the whole effect, useful to check the result; it is not an input and contains secrets.
8. **Test Effect** (right column): fill the runtime parameters and press Go. Leave the ContinueOn fields empty there, or the output goes to those events and the panel shows nothing.
9. **Save to organization**. "Portal rejected our submission: (Unauthorized)" is usually a stale Portal session: log out and in, open the editor from a fresh link, refill, save. After saving, reload the page and select the effect to confirm the stored definition.
10. Tick the effect in the **Use** column so graphs can import it.

**Attach it in the graph**
1. Graph -> Effects -> Import the effect, then select it on the Robot event (role `Robot`).
2. Set every parameter on the Robot. Values are expressions: unquoted event ID = that event's value (`q` = `FAQ_UserQuestion`), quoted = literal (`"FAQ_RetrievalOk"`, `"<key>"`), never `$(...)`.
3. Continuation targets are separate events with role `System`; Fail and Timeout should lead to a user-visible message event (respond to it), so a broken API never leaves the conversation silent.
4. Whenever the effect's parameters change, re-import it into the graph and recheck every value and its quotes.
5. Run a Portal simulation of the full path, then the same path over REST with roles (see the REST section).

**Running the API behind the effect**
- **Keys**: give DCR its own key, separate from keys used by people or other services, so it can be rotated alone. Expect a key placed in a `header#` parameter to be readable in the effect JSON, the graph XML and the live event list; treat those as secret-bearing. With the token authenticator, accept DCR's encrypted token as an extra key and update it after every effect save.
- **Rotation**: change the key in the API, in the effect default, and on every Robot that sets it (quoted), then rerun a test. Rotate after any key appeared in a form, screenshot, chat or log.
- **Stable address**: a quick tunnel changes URL on each restart and forces an effect save each time; use a fixed hostname for anything beyond a test.
- **Response shape**: one small flat JSON object with every key always present, so the host and any DCR expressions never meet a missing key. The value lands in an event, so keep it well below a few KB and avoid secrets or stack traces in error bodies (the Fail event stores them).
- **Input**: reject an empty or missing query with 400 (DCR routes it to Fail), cap its length, and do not log query text. Check that DCR URL-encodes special characters (`&`, `#`, `%`) before relying on it.
- **Latency**: the effect runs inside the user's execute request; a cold model load or slow call delays the whole step and hits the effect timeout. Keep the service warm and cache repeated queries.
- **Logging**: log decision, score, latency and which credential sources arrived (names and lengths, not values).
- **Data**: queries pass through DCR and any tunnel provider; use fictional data until the service runs on infrastructure you control.

**Caveats seen in practice**
- The same graph can work in the Portal and fail over REST: REST callers must send the role (see the REST section).
- A missing role, unquoted literals and unquoted continuation IDs each give a different error (see the error map).
- Without continuations the result stays on the Robot event; `FAQ_RetrievalOk`-style events never run.
- Re-importing an effect can drop quotes from parameter values.
- Saving the effect changes the token the API receives.
