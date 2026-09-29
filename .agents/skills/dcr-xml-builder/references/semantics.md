# DCR semantic decisions

Read this reference before creating or behaviorally reviewing a DCR graph.

## Marking

Each event has independent runtime state:

- **included**: currently part of the process;
- **executed**: has executed at least once;
- **pending response**: is an outstanding obligation;
- **value**: submitted or computed typed data;
- **time**: conditions may delay and responses may carry deadlines.

An ordinary event is executable when it is included and active conditions and milestones allow it. Included events can generally repeat. Acceptance means there is no event that is both included and pending.

Excluding a pending event removes it from the current acceptance obligation because it is no longer included. Do not assume exclusion erases pending history if the event may later be re-included; simulate re-entry.

## Relations

| Relation | Meaning | Use |
|---|---|---|
| Condition `A -> B` | While A is included, B requires A to have executed; may also delay B | Real prerequisite |
| Response `A -> B` | Executing A makes B pending; may set a deadline | Create obligation |
| Co-response `A -> B` | Executing A removes B's pending status | Cancel obligation without excluding B |
| Include `A -> B` | Executing A includes B | Open branch or reactivate event |
| Exclude `A -> B` | Executing A excludes B | Close branch, cancel active acceptance obligation, or make A one-shot with `A -> A` |
| Milestone `A -> B` | B is blocked while A is included and pending | Prevent progress while an obligation remains |
| Update `A -> X` | Executing A writes an expression result to data event X | Maintain explicit derived data |
| Spawn `A -> G` | Executing A creates an instance of reusable subgraph G | Repeatable case entity; XML serialization needs a fixture |

A relation guard is evaluated when its source executes and controls only that relation. It is not a precondition on the source.

Useful paired patterns:

- excluded mandatory branch: guarded include + guarded response;
- editable relevance: include under guard + exclude under inverse guard;
- editable obligation that stays available: response under guard + co-response under inverse guard;
- one-shot event: self-exclude;
- reusable menu: keep included and have terminal events respond back to it.

## Containers

- `form`: Portal/host field grouping. Verify how submission maps to child executions.
- `nesting`: classical grouping with all-child completion semantics. Do not use only for visual grouping.
- `subprocess`: single-instance group completed by acceptance inside it. Optional unexecuted children do not block unless pending.
- spawned subgraph: reusable multi-instance template. Semantically distinct from static nested XML.

Children of form, nesting, and subprocess containers are nested `<event>` elements. The observed exports leave `<resources><subProcesses/>` empty for static subprocess containers.

## Data and expressions

Observed event data types include `int`, `choice` with `bool`/`int`/`string` format, `date`, `datetime`, `file`, and `label`.

Observed expression forms include:

- `Choice = 1`, `Flag = false`, `Country != "UK"`;
- `not(Choice = 1 or Choice = 2)`;
- `EventId@executed` for execution history;
- string concatenation with `+`;
- date arithmetic such as `LastContact + P4D` and `WhenSymptoms - PT48H`;
- compiled `If ... THEN ... ELSE ...` values associated with embedded DMN.

Fixtures consistently use single `=` for equality. XML-escape quotes, ampersands, and comparison characters in attributes.

## Robots

`Robot`, `LocalRobot`, `Robot:Prime`, and `Robot:Terminator` are roles on events, not relation types.

Automatic execution occurs in a fixed 4-phase **execution cycle** whenever a host requests an activity or a delay expires:
1. **Prime robots (`Robot:Prime`)**: Run first (if enabled, at most once per cycle, before user activity).
2. **User activity**: The activity requested by the host executes.
3. **Regular robots**: `Robot` (runs when enabled and pending) and `LocalRobot` (runs when enabled and locally pending) run in the middle (up to `MaxRobots`, default 256). Robots can toggle each other on and off within the cycle.
4. **Terminator robots (`Robot:Terminator`)**: Run last (if enabled, at most once per cycle).

Execution limits:
- Maximum 256 robots per cycle (configurable via runtime `MaxRobots`, can be raised to 4096+).
- Wall-clock timeout configurable via `Timeout` (format `HH:MM:SS`).
- Computation events normally self-exclude or otherwise stop becoming eligible.
- Hide automatic/System events (`Robot`, `Robot:Prime`, `LocalRobot`, `Robot:Terminator`, `System`) from ordinary user task lists.

## Dynamic Effects and Continuations

An **Effect** enables an activity to interact with external services (e.g. REST APIs, CVR lookups, SMS gateways).

- **Execution**: When an activity carrying a dynamic effect executes (typically triggered by a `Robot` or `LocalRobot`), the DCR engine invokes the external service.
- **Continuations**: An effect concludes with one of three outcomes, triggering an automatic continuation activity:
  - `ContinueOnOk`: Runs when the call succeeds (e.g. HTTP 200).
  - `ContinueOnFail`: Runs when the call fails (e.g. HTTP 4xx/5xx).
  - `ContinueOnTimeout`: Runs when the call times out.
- **Role `System`**: Continuation activities represent internal machine transitions and should use `role="System"`.
- **Continuations Limit**: At most 64 consecutive effect continuations can execute per cycle.
- **Administration**: In DCR Portal 7.3+, custom REST effects are registered centrally at the **Organization Level** via **Effect Admin** / **Effect Wizard**, rather than in raw XML per graph. In graph XML, the event carries `<effects><effect name="...">` with parameter bindings like `$(EventId)` and continuation target event IDs.

## Time

- A condition `time` is an enablement delay.
- A response `time` is an obligation deadline.
- A computation that adds a duration creates a data value; it is not itself a DCR delay/deadline.

Use ISO 8601 durations such as `P4D`, `P1W`, or `PT48H`. `P7WD` is a DCR working-day extension and may depend on licensing/host configuration. A supplied export also uses a date-event ID in `time`; treat dynamic time serialization as version-sensitive and test it.

## DMN

Observed DMN is an `<expression type="DMN">` containing both:

- a compiled engine expression in `value`; and
- an OMG `<definitions>` child.

The event refers to it with `computation="..."`. Keep compiled and DMN representations synchronized. Observed DMN input labels match in-scope DCR event IDs even when `<inputExpression><text/></inputExpression>` is empty.

Use DMN when a reviewable decision table is clearer than many guarded relations. Confirm input IDs/types, hit policy, fallback behavior, result type, Robot trigger, and downstream guards.

## Questions that materially affect a graph

Ask rather than guess when the answer changes semantics:

- Which events are obligations versus merely available?
- What makes the process or subprocess accepting?
- Can an event repeat, and should it retain pending history on re-entry?
- Can users edit prior data, and must old branches/obligations be removed?
- Is a group a form, classical nesting, accepting subprocess, or repeatable subgraph?
- Does a time value represent a delay, deadline, calculated date, calendar days, or working days?
- Should an automatic event be global Robot behavior or local subprocess behavior?
- Is a decision advisory routing or an authoritative business conclusion?
