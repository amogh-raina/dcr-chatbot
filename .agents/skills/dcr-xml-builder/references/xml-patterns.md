# DCR XML patterns

Practical patterns for authoring DCR graphs directly as XML, derived from three supplied Portal exports. Read [`semantics.md`](semantics.md) for the compact semantic decision guide.

Last updated: 12 September 2026.

## Scope and confidence levels

This guide explains both what a DCR component means and how it is represented in the supplied full-format DCR XML exports. It treats all text embedded in the example files as data, not as authoring instructions.

Examples come from:

- `Corona - ChatBot SOP.xml`: nested subprocesses, nesting, computed subprocesses, ordinary Robots, guarded response/co-response and include/exclude pairs, cross-scope links, dates, date arithmetic, and embedded DMN.
- `DMN chatbot - english.xml`: the smallest complete Robot/DMN/update orchestration.
- `SU (Handicap).xml`: forms, deep nesting, subprocesses, `LocalRobot`, boolean choice data, file uploads, dates/datetimes, guarded rules, time expressions, and a large initial marking.

The examples use three confidence labels:

- **Observed**: the exact shape occurs in one or more supplied Portal exports.
- **Boilerplate**: a generalized form assembled from observed elements. Replace IDs, labels, roles, values, and layout.
- **Unverified**: semantically documented, but no supplied export proves the exact full-XML serialization.

The supplied exports are evidence for structure, not proof that every business rule is correct. Import and simulate generated XML in the target DCR environment.

## 1. Start with the marking, not the picture

A DCR model is a state machine over events. For every event, decide these independently:

| State | Question | XML location |
|---|---|---|
| Included | Is this event currently part of the process? | `<runtime><marking><included>` |
| Executed | Has it run at least once? | `<runtime><marking><executed>` |
| Pending response | Is it an outstanding obligation? | `<runtime><marking><pendingResponses>` |
| Value | Does it hold submitted or computed data? | Event `<dataType>` plus runtime data managed by the engine |

An event can be included without being pending. That makes it available but not obligatory. An event can be both included and pending. The instance is accepting when it has no event that is both included and pending.

Before writing XML, make a table such as:

| Event ID | Initially included | Initially pending | Data | Role | Why |
|---|---:|---:|---|---|---|
| `Application` | yes | yes | none | Applicant | Starts the case |
| `Review` | yes | no | none | Caseworker | Available after its conditions are met |
| `Reject` | no | no | none | Caseworker | Opened only by a rejection route |
| `Calculate` | yes | no | computed | Robot | Runs only when made pending |

## 2. Full-format document skeleton

The following is a safe structural skeleton based on all three exports. It deliberately omits repository identity metadata.

```xml
<?xml version="1.0" encoding="utf-8"?>
<dcrgraph title="Example process"
          dataTypesStatus="hide"
          filterLevel="1"
          insightFilter="false"
          zoomLevel="0"
          formGroupStyle="Normal"
          formLayoutStyle="Horizontal"
          formShowPendingCount="true"
          graphBG="#ffffff"
          graphType="0"
          exercise="false"
          version="1.1">
  <specification>
    <resources>
      <events>
        <!-- Event tree -->
      </events>
      <subProcesses/>
      <distribution/>
      <labels/>
      <labelMappings/>
      <expressions/>
      <variables/>
      <variableAccesses>
        <writeAccesses/>
      </variableAccesses>
      <custom>
        <!-- Graph-wide Portal metadata -->
      </custom>
    </resources>
    <constraints>
      <conditions/>
      <responses/>
      <coresponses/>
      <excludes/>
      <includes/>
      <milestones/>
      <updates/>
      <spawns/>
      <templateSpawns/>
    </constraints>
  </specification>
  <runtime>
    <custom>
      <globalMarking/>
    </custom>
    <marking>
      <globalStore/>
      <executed/>
      <included/>
      <pendingResponses/>
    </marking>
  </runtime>
</dcrgraph>
```

Best practices:

- Preserve all empty resource and constraint collections when adapting a Portal export.
- Preserve the element order of the compatible export used as a skeleton. The two chatbot exports place `excludes` before `includes` and `updates` before `spawns`; the newer SU export uses a different order. This is version/exporter evidence, not a semantic distinction.
- Do not copy `<meta>` values such as graph IDs, revision IDs, GUIDs, hashes, owners, or organizations from another graph.
- Treat root attributes such as zoom, colors, and form layout as presentation settings, not process semantics.
- Match the `version` used by an export known to import into the target repository. The supplied files use both `1.0` and `1.1`.

## 3. Events

### 3.1 Minimal full-format event

**Boilerplate**, generalized from every supplied export:

```xml
<event id="ReviewApplication">
  <precondition message=""/>
  <custom>
    <visualization>
      <location xLoc="300" yLoc="100"/>
      <colors bg="#f9f7ed" textStroke="#000000" stroke="#cccccc"/>
    </visualization>
    <roles>
      <role>Caseworker</role>
    </roles>
    <readRoles>
      <readRole/>
    </readRoles>
    <groups>
      <group/>
    </groups>
    <phases>
      <phase/>
    </phases>
    <eventType/>
    <eventScope>private</eventScope>
    <eventTypeData/>
    <eventDescription>&lt;p&gt;Review the submitted application.&lt;/p&gt;</eventDescription>
    <purpose/>
    <guide/>
    <insight use="false"/>
    <level>1</level>
    <sequence>0</sequence>
    <costs>0</costs>
    <eventData/>
    <interfaces/>
  </custom>
</event>
```

Only `id` participates in relation references. The visible name is a separate label. Prefer stable ASCII IDs such as `ReviewApplication`; labels can change or be translated without rewriting relations and expressions.

### 3.2 Labels and label mappings

**Observed** in all three exports:

```xml
<labels>
  <label id="Review the application"/>
  <label id="Send the decision"/>
</labels>
<labelMappings>
  <labelMapping eventId="ReviewApplication"
                labelId="Review the application"/>
  <labelMapping eventId="SendDecision"
                labelId="Send the decision"/>
</labelMappings>
```

Rules:

- Every `labelMapping/@eventId` must resolve to a resource event.
- Every `labelMapping/@labelId` must resolve to a label.
- A label ID may contain spaces and punctuation; an event ID should remain machine-stable.
- XML-escape label text in attributes: `&amp;`, `&quot;`, `&lt;`, and `&gt;`.

### 3.3 Descriptions and HTML

`SU (Handicap).xml` stores rich descriptions as XML-escaped HTML:

```xml
<eventDescription>
  &lt;p&gt;Explain what the reviewer must check.&lt;/p&gt;
  &lt;p&gt;&lt;strong&gt;Important:&lt;/strong&gt; attach evidence.&lt;/p&gt;
</eventDescription>
```

The element contains text whose value is HTML. Do not insert raw `<p>` tags unless the importer explicitly expects child markup. Escape ampersands in URLs and prose before inserting the HTML string.

### 3.4 Roles, read roles, groups, and phases

Event assignment is stored inside event-level `<custom>`:

```xml
<roles>
  <role description="" specification="">Caseworker</role>
</roles>
<readRoles>
  <readRole>Auditor</readRole>
</readRoles>
<groups>
  <group>ShowInChat</group>
</groups>
<phases>
  <phase>Conclusion</phase>
</phases>
```

The same names should normally be declared in graph-wide custom metadata:

```xml
<custom>
  <roles>
    <role description="" specification="">Caseworker</role>
    <role description="" specification="">Robot</role>
  </roles>
  <groups>
    <group description="">ShowInChat</group>
  </groups>
  <phases>
    <phase description="">Conclusion</phase>
  </phases>
  <!-- other graph metadata -->
</custom>
```

The Corona and DMN exports use `User` and `Robot`; the SU export uses domain roles and `LocalRobot`. Empty placeholders such as `<role/>` are common in exports. Preserve them when adapting a skeleton, but do not interpret them as named roles.

### 3.5 Event metadata inventory

The supplied Portal exports give every resource event a `<precondition>` followed by a `<custom>` block. Much of this is presentation or host metadata rather than core DCR semantics.

| Element | Observed purpose | Authoring guidance |
|---|---|---|
| `<precondition message=""/>` | Holds a precondition message field | Preserve the element. Do not confuse it with a DCR `<condition>` relation. |
| `<visualization>` | Coordinates and colors | Add after semantics; duplicate coordinates do not change DCR behavior. |
| `<roles>` | Event execution role | Use exact names also declared graph-wide. |
| `<readRoles>` | Read visibility metadata | Security behavior is host-dependent; test it rather than treating it as a substitute for authorization. |
| `<groups>` | UI/filter grouping | The Corona fixture uses a chat display group. It does not create DCR nesting. |
| `<phases>` | UI/filter phase | Use for presentation or filtering; it is not a condition relation. |
| `<eventType>` | Custom event-type slot | Empty in all three attachments. Preserve unless a proven fixture uses it. |
| `<eventScope>` | Event visibility/scope setting | All attached resource events use `private`; verify other values before generating them. |
| `<eventTypeData>` | Custom event-type payload | Empty in all three attachments. |
| `<eventDescription>` | Rich event description | Store observed rich content as escaped HTML text. |
| `<purpose>` / `<guide>` | Documentation fields | Useful for authoring guidance; empty in many exports. |
| `<insight use="false"/>` | Portal insight setting | Presentation/analytics metadata, not marking semantics. |
| `<level>` | Portal filter level | Keep consistent with the graph and relations; supplied values include `1` and `100`. |
| `<sequence>` | Form/display ordering | Make unique and stable where the host uses form order. |
| `<costs>` | Cost metadata | `0` throughout the attached examples. |
| `<eventData>` | Data field configuration | Contains a type, dictionary, and validation rules when the event carries data. |
| `<interfaces>` | Host integration metadata | Empty in the attachments; do not invent an interface schema. |

Graph-wide scaffolding has similarly cautious treatment:

| Element | Guidance |
|---|---|
| `<subProcesses/>` | Empty even when static `type="subprocess"` containers exist. Do not populate it for ordinary nested subprocesses. |
| `<distribution/>` | Empty in the attachments. Preserve it as export scaffolding. |
| `<variables/>` and `<variableAccesses><writeAccesses/></variableAccesses>` | Empty in the attachments. Computations and updates work through expression references without hand-authored entries here. |
| `<custom>` under resources | Declares roles, groups, phases, graph documentation, language/domain, filters, and highlight metadata. Copy its shape from a compatible export. |
| `<custom>` under runtime | Contains a global-marking cache shape in some exports. Do not confuse it with the authored `<marking>`. |

## 4. Event data types

`<eventData>` is placed under the event's `<custom>` element. Its `<dataType>` text is the type name; attributes configure rendering and validation.

### 4.1 Integer

**Observed** for `Age` in the DMN chatbot:

```xml
<eventData>
  <dataType sequence="0" width="small"
            min="NaN" max="NaN"
            placeholder="" hinttext="">int</dataType>
  <validationRules/>
</eventData>
```

Use actual numeric bounds when they are business constraints. The observed `NaN` values behave as unspecified bounds in that export, but empty or omitted bounds may be safer in a different importer version.

### 4.2 Boolean choice

**Observed** repeatedly in `SU (Handicap).xml`:

```xml
<eventData>
  <dataType sequence="1" width="small"
            placeholder="" hinttext=""
            dataSetList="" radio="horizontal"
            multiple="false" format="bool">choice</dataType>
  <dictionary>
    <item label="Yes" value="true"/>
    <item label="No" value="false"/>
  </dictionary>
  <validationRules/>
</eventData>
```

Guards compare the value as a boolean, for example `HasDiagnosis = false`, not as the string `"false"`.

### 4.3 Integer-coded choice

**Observed** in the Corona graph:

```xml
<eventData>
  <dataType sequence="2" width="small"
            placeholder="" hinttext=""
            dataSetList="" dataSetActivity=""
            multiple="false" radio="" format="int">choice</dataType>
  <dictionary>
    <item label="Yes" value="1"/>
    <item label="No" value="0"/>
  </dictionary>
  <validationRules/>
</eventData>
```

Integer codes are useful for stable multilingual choices, but document what every code means. Avoid changing values when translating labels.

### 4.4 String choice

**Observed** for `Country` in the DMN chatbot:

```xml
<eventData>
  <dataType sequence="3" width="small"
            placeholder="" hinttext=""
            dataSetList="" dataSetActivity=""
            multiple="false" radio="" format="string">choice</dataType>
  <dictionary>
    <item label="Denmark" value="Denmark"/>
    <item label="United Kingdom" value="UK"/>
  </dictionary>
  <validationRules/>
</eventData>
```

The visible label and machine value may differ. Guards and DMN rules use the machine value, such as `Country = "UK"`.

### 4.5 Date and datetime

**Observed** in Corona and SU:

```xml
<eventData>
  <dataType sequence="4" width="small"
            min="0" max="255"
            placeholder="" hinttext="">date</dataType>
  <validationRules/>
</eventData>
```

```xml
<eventData>
  <dataType sequence="5" width="small"
            min="0" max="255"
            placeholder="" hinttext="">datetime</dataType>
  <validationRules/>
</eventData>
```

The observed `min="0" max="255"` values are export metadata, not meaningful calendar limits. Preserve them when cloning the proven event shape; validate actual date restrictions separately.

### 4.6 File upload

**Observed** in the SU application form:

```xml
<eventData>
  <dataType sequence="6" width="small"
            min="" max=""
            placeholder="" hinttext="">file</dataType>
  <validationRules/>
</eventData>
```

The DCR event records the upload activity. File storage, size, media type, scanning, and retention still depend on the host application.

### 4.7 Label/display field

**Observed** in both chatbot exports:

```xml
<eventData>
  <dataType sequence="7" width="small"
            default="" placeholder="" hinttext="">label</dataType>
  <validationRules/>
</eventData>
```

Use a label event to display a computed result. It can be the target of an update relation.

### 4.8 Computed choice dataset

Additional verified project fixtures establish this pattern, although it is not present in the three primary exports:

```xml
<event id="BuildChoices" computation="BuildChoices-computation">
  <!-- custom metadata with Robot role -->
</event>

<event id="ChooseNext">
  <precondition message=""/>
  <custom>
    <!-- ordinary event metadata -->
    <eventData>
      <dataType sequence="8" width="small"
                dataSetList="" dataSetActivity="BuildChoices"
                multiple="false" radio="" format="int">choice</dataType>
      <dictionary/>
      <validationRules/>
    </eventData>
    <interfaces/>
  </custom>
</event>
```

`BuildChoices-computation` must return value/label pairs such as `[[1, "First"], [2, "Second"]]`. Test that the actual host serializes and renders computed datasets.

## 5. Structural containers

Container semantics are not interchangeable.

### 5.1 Form

**Observed** in `SU (Handicap).xml`:

```xml
<event id="ApplicationForm"
       type="form"
       cancelText=""
       sendText=""
       hideCancel="false"
       formShowInitialPhase="1">
  <precondition message=""/>
  <custom>
    <!-- container metadata -->
  </custom>

  <event id="MedicalRecord">
    <!-- child event with file data type -->
  </event>
  <event id="ApplicationStatement">
    <!-- child event -->
  </event>
</event>
```

A form groups fields for submission and UI presentation. Do not assume a form is semantically equivalent to a subprocess or classical nesting; verify how form submission maps to child execution in the target host.

### 5.2 Classical nesting

**Observed** in Corona and SU:

```xml
<event id="Assessment" type="nesting">
  <precondition message=""/>
  <custom>
    <!-- container metadata -->
  </custom>

  <event id="CheckEvidence">
    <!-- child -->
  </event>
  <event id="RecordFinding">
    <!-- child -->
  </event>
</event>
```

Use `type="nesting"` only when the classical “all relevant atomic children completed” semantics are intended. It is too strong for a purely visual collection of optional FAQ items.

### 5.3 Single-instance subprocess

**Observed** in all complex attachments:

```xml
<event id="MedicalAssessment" type="subprocess">
  <precondition message=""/>
  <custom>
    <!-- container metadata -->
  </custom>

  <event id="DiagnosisConfirmed">
    <!-- child -->
  </event>
  <event id="FunctionalImpactRecorded">
    <!-- child -->
  </event>
</event>
```

A subprocess completes according to acceptance: no included child obligation remains pending. The children are nested directly inside the container event. In all supplied exports, `<resources><subProcesses/>` is empty; it does not define these single-instance containers.

### 5.4 Deep nesting

`SU (Handicap).xml` nests subprocesses inside nesting containers and subprocesses inside subprocesses. The XML representation is simply recursive:

```xml
<event id="CaseAssessment" type="nesting">
  <custom><!-- ... --></custom>
  <event id="Eligibility" type="subprocess">
    <custom><!-- ... --></custom>
    <event id="MedicalCriteria" type="subprocess">
      <custom><!-- ... --></custom>
      <event id="ReviewDiagnosis">
        <custom><!-- ... --></custom>
      </event>
    </event>
  </event>
</event>
```

Keep every event ID globally unique even when events live in different containers. Relations still use the short ID; the optional `link` carries qualified paths for Portal relationship metadata.

### 5.5 Spawned, multi-instance subgraphs

**Unverified serialization.** All three attachments contain empty `<spawns/>`, `<templateSpawns/>`, and `<subProcesses/>` collections. They do not show how a reusable spawnable template is declared and linked in current full XML.

The semantics are clear: executing a spawn relation creates another runtime instance of a reusable subgraph. Do not guess its full XML. Create a tiny spawn model in the target Portal, export it, and use that export as the serialization fixture.

## 6. Expressions and guards

Expressions live under resources and are referenced by ID:

```xml
<expressions>
  <expression id="HasDiagnosis-path-Review--include"
              value="HasDiagnosis = true"/>
  <expression id="NoDiagnosis-path-Reject--response"
              value="HasDiagnosis = false"/>
</expressions>
```

```xml
<include sourceId="HasDiagnosis"
         targetId="Review"
         filterLevel="1"
         description=""
         time=""
         groups=""
         expressionId="HasDiagnosis-path-Review--include"/>
```

Guard rules:

- A guard controls whether that relation fires when its source executes. It does not enable or disable the source event.
- Give each expression a unique, stable ID.
- The fixtures use single `=` for equality and `!=` for inequality.
- Use lowercase `true`, `false`, and `null` for literals.
- String literals use quotes, which become `&quot;` inside XML attributes.
- Escape `<`, `>`, and `&` as `&lt;`, `&gt;`, and `&amp;`.
- Parenthesize mixed boolean expressions.
- Check scope: a syntactically valid event reference may still be invalid from a nested location.

**Observed expression forms:**

```xml
<expression id="RouteYes" value="Answer = 1"/>
<expression id="RouteNo" value="Answer != 1"/>
<expression id="SymptomsRelevant" value="Symptoms = 1 or Symptoms = 2"/>
<expression id="Adult" value="Age &gt;= 18"/>
<expression id="NotEligible" value="not(Eligible = true)"/>
<expression id="FirstTest-computation" value="LastContact + P4D"/>
<expression id="DisplayResult" value="&quot;Result: &quot; + Decision"/>
```

The SU export also uses execution history and duration arithmetic:

```xml
<expression id="RenewalWindow"
            value="Expiry - Approval@executed - P3M"/>
```

That exact expression is observed, but its resulting type and use as a relation guard should be verified in the target engine. Keep date/duration tests explicit.

## 7. Relations: exact XML and modeling patterns

The relation collections are siblings under `<constraints>`. `sourceId` is the event whose execution or state drives the relation; `targetId` is the affected or gated event.

Common relation attributes in the attachments are:

| Attribute | Purpose |
|---|---|
| `sourceId` | Stable source event ID. |
| `targetId` | Stable target event ID. |
| `filterLevel` | Portal filtering/display metadata; use the graph's established convention. |
| `description` | Human documentation for the relation. |
| `time` | Delay on a condition or deadline on a response; empty when unused. |
| `groups` | Portal group metadata; empty throughout most attached relations. |
| `expressionId` | Optional guard expression reference. |
| `valueExpressionId` | Update value expression reference; used on `<update>`. |
| `link` | Optional qualified relationship metadata for nested paths. Preserve proven values. |

### 7.1 Condition — prerequisite

Meaning: while the source is included, the target requires the source to have executed.

```xml
<conditions>
  <condition sourceId="SubmitApplication"
             targetId="ReviewApplication"
             filterLevel="1"
             description=""
             time=""
             groups=""/>
</conditions>
```

Use a condition for a real prerequisite, not merely to force a preferred screen order.

### 7.2 Delayed condition

For a fixed ISO 8601 delay:

```xml
<condition sourceId="NotifyApplicant"
           targetId="SendReminder"
           filterLevel="1"
           description="Wait four days"
           time="P4D"
           groups=""/>
```

The SU export also uses an event/data reference in `time`, for example `time="frist"`. This suggests the Portal can serialize data-driven time values:

```xml
<condition sourceId="SetDeadline"
           targetId="DeadlineExpired"
           filterLevel="100"
           description=""
           time="DeadlineValue"
           groups=""/>
```

Treat the data-driven form as version-sensitive. Verify whether the referenced event represents a duration, date, or deadline in the target engine.

### 7.3 Response — create an obligation

Meaning: executing the source makes the target pending.

```xml
<responses>
  <response sourceId="SubmitApplication"
            targetId="ReviewApplication"
            filterLevel="1"
            description=""
            time=""
            groups=""/>
</responses>
```

An event made pending is only an active acceptance obligation while it is included. If the target begins excluded, pair the response with an include.

### 7.4 Response with deadline

```xml
<response sourceId="RequestInformation"
          targetId="ProvideInformation"
          filterLevel="1"
          description="Due in one week"
          time="P1W"
          groups=""/>
```

The `time` on a response is a deadline, whereas `time` on a condition is a delay. They use the same attribute but have different semantics.

### 7.5 Co-response — cancel pending status

Meaning: executing the source removes the target's pending-response status without necessarily excluding the target.

**Observed** complementary pattern from Corona:

```xml
<expressions>
  <expression id="ContactYes" value="CloseContact = &quot;yes&quot;"/>
  <expression id="ContactNotYes" value="CloseContact != &quot;yes&quot;"/>
</expressions>

<responses>
  <response sourceId="CloseContact" targetId="PeriodFit"
            filterLevel="1" description="" time="" groups=""
            expressionId="ContactYes"/>
</responses>
<coresponses>
  <coresponse sourceId="CloseContact" targetId="PeriodFit"
              filterLevel="1" description="" time="" groups=""
              expressionId="ContactNotYes"/>
</coresponses>
```

Use co-response when the target should remain available but cease to be obligatory. Use exclude when it should leave the active process as well.

### 7.6 Include — activate an event or branch

```xml
<includes>
  <include sourceId="SelectDetailedReview"
           targetId="DetailedReview"
           filterLevel="1"
           description=""
           time=""
           groups=""/>
</includes>
```

An include does not make the target pending. Pair it with a response when the opened event must also become an obligation.

### 7.7 Exclude — deactivate an event or branch

```xml
<excludes>
  <exclude sourceId="CancelCase"
           targetId="ReviewApplication"
           filterLevel="1"
           description=""
           time=""
           groups=""/>
</excludes>
```

Excluding an included pending event removes it from the current acceptance obligation. If it is later re-included, test whether its pending history should reappear for the intended workflow.

For a one-shot event, use self-exclusion:

```xml
<exclude sourceId="SubmitApplication"
         targetId="SubmitApplication"
         filterLevel="1"
         description=""
         time=""
         groups=""/>
```

Without self-exclusion or another constraint, an ordinary included event can generally execute again.

### 7.8 Complementary include/exclude guards

**Observed** extensively in Corona. This pattern recalculates relevance in both directions when an answer changes:

```xml
<expressions>
  <expression id="Symptoms-Date-include"
              value="Symptoms = 1 or Symptoms = 2"/>
  <expression id="Symptoms-Date-exclude"
              value="not(Symptoms = 1 or Symptoms = 2)"/>
</expressions>

<includes>
  <include sourceId="Symptoms" targetId="SymptomDate"
           filterLevel="1" description="" time="" groups=""
           expressionId="Symptoms-Date-include"/>
</includes>
<excludes>
  <exclude sourceId="Symptoms" targetId="SymptomDate"
           filterLevel="1" description="" time="" groups=""
           expressionId="Symptoms-Date-exclude"/>
</excludes>
```

An include-only branch can stay incorrectly included after the source value changes. Use complementary rules for editable data.

### 7.9 Include plus response for exact routing

```xml
<expressions>
  <expression id="Route-Answer-include" value="Question = 2"/>
  <expression id="Route-Answer-response" value="Question = 2"/>
</expressions>

<includes>
  <include sourceId="Question" targetId="AnswerTwo"
           filterLevel="1" description="" time="" groups=""
           expressionId="Route-Answer-include"/>
</includes>
<responses>
  <response sourceId="Question" targetId="AnswerTwo"
            filterLevel="1" description="" time="" groups=""
            expressionId="Route-Answer-response"/>
</responses>
```

The two expression records may contain the same guard text, but separate IDs match the export convention and simplify traceability.

### 7.10 Milestone — block while another obligation is pending

Meaning: the target is blocked while the source is included and pending.

```xml
<milestones>
  <milestone sourceId="ProvideInformation"
             targetId="CloseCase"
             filterLevel="1"
             description=""
             time=""
             groups=""/>
</milestones>
```

A common input-to-Robot pattern combines condition and milestone:

```xml
<conditions>
  <condition sourceId="Age" targetId="Decision"
             filterLevel="1" description="" time="" groups=""
             link="Age--condition--Decision"/>
</conditions>
<milestones>
  <milestone sourceId="Age" targetId="Decision"
             filterLevel="1" description="" time="" groups=""
             link="Age--condition--Decision"/>
</milestones>
```

The condition requires an executed input; the milestone blocks the decision while that same input is still pending. The identical `link` is observed Portal metadata.

### 7.11 Update — write a computed value

**Observed** in the DMN chatbot:

```xml
<expressions>
  <expression id="Decision-ResultLabel--value"
              value="&quot;Decision: &quot; + Decision"/>
</expressions>

<updates>
  <update sourceId="Decision"
          targetId="ResultLabel"
          filterLevel="1"
          description=""
          time=""
          groups=""
          valueExpressionId="Decision-ResultLabel--value"/>
</updates>
```

An update's value is referenced through `valueExpressionId`, not `expressionId`. The target should have a compatible data type.

### 7.12 Cross-scope links

Relations between nested events still use short endpoint IDs. Corona and SU add a qualified `link`:

```xml
<include sourceId="Symptoms"
         targetId="SymptomDate"
         filterLevel="1"
         description=""
         time=""
         groups=""
         expressionId="Symptoms-Date-include"
         link="Assessment.Symptoms--include--Assessment.SymptomDate"/>
```

Use globally unique short IDs for semantic references. Preserve a `link` from an exported model. Do not invent qualified path syntax without validating a minimal imported example, especially for deeply nested or cross-instance relations.

## 8. Robots and computations

### 8.1 Ordinary Robot

**Observed** in Corona and the DMN chatbot:

```xml
<event id="CalculateDeadline" computation="CalculateDeadline-computation">
  <precondition message=""/>
  <custom>
    <visualization>
      <location xLoc="500" yLoc="100"/>
      <colors bg="#666666" textStroke="#ffffff" stroke="#434343"/>
    </visualization>
    <roles>
      <role>Robot</role>
    </roles>
    <!-- remaining standard custom fields -->
    <eventData>
      <dataType sequence="9" width="small"
                min="0" max="255"
                placeholder="" hinttext="">date</dataType>
      <validationRules/>
    </eventData>
    <interfaces/>
  </custom>
</event>

<expressions>
  <expression id="CalculateDeadline-computation"
              value="SubmissionDate + P4D"/>
</expressions>
```

The event's `computation` must resolve to an expression ID. A regular Robot runs automatically when it is enabled and pending. Merely including it is not a trigger; create a response to it.

```xml
<responses>
  <response sourceId="SubmissionDate"
            targetId="CalculateDeadline"
            filterLevel="1" description="" time="" groups=""/>
</responses>
```

Give every Robot a termination strategy: a self-exclude, a downstream exclusion, or a topology in which it no longer becomes pending. Never rely on the engine's robot execution limit to stop a loop.

### 8.2 LocalRobot

**Observed** several times in `SU (Handicap).xml`:

```xml
<event id="InsufficientDocumentation">
  <precondition message=""/>
  <custom>
    <!-- standard metadata -->
    <roles>
      <role>LocalRobot</role>
    </roles>
    <!-- standard metadata -->
  </custom>
</event>
```

A `LocalRobot` runs when enabled and locally pending. Use it when automatic activity should be scoped to the local subprocess context. The supplied SU Robot-like events do not carry computations; they act as automatic control-flow events.

### 8.3 Computed subprocess

**Observed** in Corona:

```xml
<event id="CloseContact"
       computation="CloseContact-computation"
       type="subprocess">
  <precondition message=""/>
  <custom><!-- container metadata --></custom>
  <event id="LivesWithPerson"><!-- choice input --></event>
  <event id="PhysicalContact"><!-- choice input --></event>
  <event id="WithinOneMeter"><!-- choice input --></event>
</event>
```

```xml
<expression id="CloseContact-computation"
            type="DMN"
            value="( If( LivesWithPerson = 1 ) THEN ( &quot;yes&quot; ) ELSE ( &quot;no&quot; ) )">
  <!-- embedded OMG DMN definitions -->
</expression>
```

The computed value of the container can drive guarded relations. Corona also uses a guarded self-response when the result is `"retry"`, making the subprocess pending again until enough child data exists. This is powerful but version-sensitive: clone the complete proven structure and test partial input, retry, accepting, and final-result states.

## 9. Embedded DMN

### 9.1 Event linkage

The decision activity references a DMN expression exactly like an ordinary computation:

```xml
<event id="Decision" computation="Decision-computation">
  <precondition message=""/>
  <custom>
    <!-- visualization and other standard fields -->
    <roles>
      <role>Robot</role>
    </roles>
    <!-- no explicit eventData in the supplied DMN chatbot -->
  </custom>
</event>
```

### 9.2 Expression and embedded definitions

**Observed shape**, shortened from the English DMN chatbot:

```xml
<expression id="Decision-computation"
            value="( If( ((Country = &quot;Denmark&quot;) AND (Age &gt;= 18)) ) THEN ( &quot;Yes&quot; ) ELSE ( &quot;No&quot; ) )"
            type="DMN">
  <definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/"
               xmlns:biodi="http://bpmn.io/schema/dmn/biodi/2.0"
               id="definitions_example"
               name="definitions"
               namespace="http://camunda.org/schema/1.0/dmn"
               exporter="dmn-js (https://demo.bpmn.io/dmn)"
               exporterVersion="11.0.1">
    <decision id="decision_example" name="">
      <decisionTable id="decisionTable_example" hitPolicy="FIRST">
        <input id="input_country" label="Country" biodi:width="150">
          <inputExpression id="expr_country" typeRef="string">
            <text/>
          </inputExpression>
        </input>
        <input id="input_age" label="Age" biodi:width="150">
          <inputExpression id="expr_age" typeRef="integer">
            <text/>
          </inputExpression>
        </input>
        <output id="output_decision" label="Decision"
                name="" typeRef="string" biodi:width="150"/>
        <rule id="rule_denmark_adult">
          <description>Adult in Denmark</description>
          <inputEntry id="test_country_denmark">
            <text>&quot;Denmark&quot;</text>
          </inputEntry>
          <inputEntry id="test_age_18">
            <text>&gt;=18</text>
          </inputEntry>
          <outputEntry id="result_yes">
            <text>&quot;Yes&quot;</text>
          </outputEntry>
        </rule>
        <rule id="rule_fallback">
          <inputEntry id="test_country_any"><text>-</text></inputEntry>
          <inputEntry id="test_age_any"><text>-</text></inputEntry>
          <outputEntry id="result_no"><text>&quot;No&quot;</text></outputEntry>
        </rule>
      </decisionTable>
    </decision>
  </definitions>
</expression>
```

Preserve both representations:

- `value` is the compiled engine expression in the supplied exports.
- `<definitions>` is the embedded OMG DMN model.

Do not assume the importer reconstructs one from the other. Keep them logically synchronized.

The fixtures bind DCR data to DMN inputs through the DMN input `label`; the nested `<inputExpression><text/></inputExpression>` is empty. Confirm all labels exactly match in-scope DCR event IDs and all `typeRef` values match their data.

### 9.3 Complete orchestration

The smallest supplied DMN graph uses this relation set:

```xml
<conditions>
  <condition sourceId="Country" targetId="Decision"
             filterLevel="1" description="" time="" groups=""/>
  <condition sourceId="Age" targetId="Decision"
             filterLevel="1" description="" time="" groups=""/>
  <condition sourceId="Decision" targetId="Conclusion"
             filterLevel="1" description="" time="" groups=""/>
</conditions>
<responses>
  <response sourceId="Country" targetId="Decision"
            filterLevel="1" description="" time="" groups=""/>
  <response sourceId="Age" targetId="Decision"
            filterLevel="1" description="" time="" groups=""/>
</responses>
<milestones>
  <milestone sourceId="Country" targetId="Decision"
             filterLevel="1" description="" time="" groups=""/>
  <milestone sourceId="Age" targetId="Decision"
             filterLevel="1" description="" time="" groups=""/>
  <milestone sourceId="Decision" targetId="Conclusion"
             filterLevel="1" description="" time="" groups=""/>
</milestones>
<updates>
  <update sourceId="Decision" targetId="Conclusion"
          filterLevel="1" description="" time="" groups=""
          valueExpressionId="Decision-Conclusion--value"/>
</updates>
```

Initially include all four events, but initially make only the two human inputs pending. Each input execution requests the Robot; conditions require both inputs to have executed; milestones prevent premature calculation while either input is still an obligation; the update copies the formatted result to the conclusion label.

## 10. Runtime and initial marking

### 10.1 Basic marking

**Observed** in the DMN chatbot:

```xml
<runtime>
  <custom>
    <globalMarking/>
  </custom>
  <marking>
    <globalStore/>
    <executed/>
    <included>
      <event id="Country"/>
      <event id="Age"/>
      <event id="Decision"/>
      <event id="Conclusion"/>
    </included>
    <pendingResponses>
      <event id="Country"/>
      <event id="Age"/>
    </pendingResponses>
  </marking>
</runtime>
```

Every marking ID must resolve to a resource event. Do not put an event in `<pendingResponses>` merely to make it visible; pending means a real outstanding obligation.

### 10.2 Initially executed events

```xml
<executed>
  <event id="CaseCreated"/>
</executed>
```

Use this only when the process genuinely begins with historical execution state. An initially executed prerequisite can enable downstream events immediately.

### 10.3 Acceptance attribute and global marking cache

The SU export contains `runtime accepting="false"` and a populated shape for a Portal cache:

```xml
<runtime accepting="false">
  <custom>
    <globalMarking>
      <enabled/>
      <enabledSubprocesses/>
      <executed/>
      <pending/>
      <included/>
    </globalMarking>
  </custom>
  <marking><!-- authoritative initial marking --></marking>
</runtime>
```

Treat `marking` as the authored initial state. Do not hand-maintain cached or derived global-marking entries unless the target importer requires them. Let the engine calculate acceptance and enabledness.

## 11. Time modeling

Use ISO 8601 durations:

- `P4D`: four calendar days.
- `P1W`: one week.
- `P5DT3H4M2S`: five days, three hours, four minutes, two seconds.
- `P7WD`: seven working days in DCR's extension; host configuration and licensing may affect holiday calculation.

Three distinct patterns exist:

```xml
<!-- Delay target enablement -->
<condition sourceId="Submitted" targetId="FollowUp"
           filterLevel="1" description="" time="P4D" groups=""/>

<!-- Give a pending obligation a due time -->
<response sourceId="RequestSent" targetId="Reply"
          filterLevel="1" description="" time="P1W" groups=""/>

<!-- Compute a date value -->
<expression id="DueDate-computation" value="SubmittedAt + P4D"/>
```

Do not confuse them. The first two change DCR semantics; the third computes event data.

The attachments do not show initial execution timestamps or initial pending deadlines. Obtain a Portal export before authoring those by hand.

## 12. End-to-end minimal model

This boilerplate demonstrates an initially required submission, a review obligation, a boolean decision, and mutually exclusive outcomes. It omits most Portal presentation metadata for readability; when importing full XML, insert these semantic pieces into a proven skeleton with complete event `<custom>` blocks.

```xml
<dcrgraph title="Minimal review" version="1.1"
          dataTypesStatus="hide" filterLevel="1"
          insightFilter="false" zoomLevel="0"
          formGroupStyle="Normal" formLayoutStyle="Horizontal"
          formShowPendingCount="true" graphBG="#ffffff"
          graphType="0" exercise="false">
  <specification>
    <resources>
      <events>
        <event id="Submit"><precondition message=""/><custom><!-- full event custom --></custom></event>
        <event id="Approve"><precondition message=""/><custom><!-- bool choice data --></custom></event>
        <event id="Accepted"><precondition message=""/><custom><!-- full event custom --></custom></event>
        <event id="Rejected"><precondition message=""/><custom><!-- full event custom --></custom></event>
      </events>
      <subProcesses/>
      <distribution/>
      <labels>
        <label id="Submit application"/>
        <label id="Approve application?"/>
        <label id="Application accepted"/>
        <label id="Application rejected"/>
      </labels>
      <labelMappings>
        <labelMapping eventId="Submit" labelId="Submit application"/>
        <labelMapping eventId="Approve" labelId="Approve application?"/>
        <labelMapping eventId="Accepted" labelId="Application accepted"/>
        <labelMapping eventId="Rejected" labelId="Application rejected"/>
      </labelMappings>
      <expressions>
        <expression id="Approve-Accepted-include" value="Approve = true"/>
        <expression id="Approve-Accepted-response" value="Approve = true"/>
        <expression id="Approve-Rejected-include" value="Approve = false"/>
        <expression id="Approve-Rejected-response" value="Approve = false"/>
      </expressions>
      <variables/>
      <variableAccesses><writeAccesses/></variableAccesses>
      <custom><!-- full graph custom --></custom>
    </resources>
    <constraints>
      <conditions>
        <condition sourceId="Submit" targetId="Approve"
                   filterLevel="1" description="" time="" groups=""/>
      </conditions>
      <responses>
        <response sourceId="Submit" targetId="Approve"
                  filterLevel="1" description="" time="" groups=""/>
        <response sourceId="Approve" targetId="Accepted"
                  filterLevel="1" description="" time="" groups=""
                  expressionId="Approve-Accepted-response"/>
        <response sourceId="Approve" targetId="Rejected"
                  filterLevel="1" description="" time="" groups=""
                  expressionId="Approve-Rejected-response"/>
      </responses>
      <coresponses/>
      <excludes>
        <exclude sourceId="Submit" targetId="Submit"
                 filterLevel="1" description="" time="" groups=""/>
        <exclude sourceId="Approve" targetId="Approve"
                 filterLevel="1" description="" time="" groups=""/>
      </excludes>
      <includes>
        <include sourceId="Approve" targetId="Accepted"
                 filterLevel="1" description="" time="" groups=""
                 expressionId="Approve-Accepted-include"/>
        <include sourceId="Approve" targetId="Rejected"
                 filterLevel="1" description="" time="" groups=""
                 expressionId="Approve-Rejected-include"/>
      </includes>
      <milestones/>
      <updates/>
      <spawns/>
      <templateSpawns/>
    </constraints>
  </specification>
  <runtime>
    <custom><globalMarking/></custom>
    <marking>
      <globalStore/>
      <executed/>
      <included>
        <event id="Submit"/>
        <event id="Approve"/>
      </included>
      <pendingResponses>
        <event id="Submit"/>
      </pendingResponses>
    </marking>
  </runtime>
</dcrgraph>
```

Expected behavior:

1. `Submit` is initially the only obligation.
2. Executing it satisfies that obligation, makes `Approve` pending, and self-excludes `Submit`.
3. `Approve` is enabled because its condition is satisfied.
4. Its boolean value includes and makes exactly one outcome pending.
5. `Approve` self-excludes, so the decision is one-shot.

For editable decisions, replace the one-shot design with complementary include/exclude and response/co-response rules so stale branches are removed.

## 13. Simplified importer XML

The simplified DCR importer is a separate format intended for generators. Do not mix it with the full Portal export schema.

**Boilerplate based on the documented simple-import concepts:**

```xml
<dcrGraph title="Simple review" description="Generated example" type="DCR">
  <roles>
    <role title="Applicant" description="" specification=""/>
    <role title="Caseworker" description="" specification=""/>
  </roles>
  <events>
    <event id="Case"
           label="Case"
           description=""
           purpose=""
           guide=""
           type="subprocess"/>
    <event id="Submit"
           label="Submit application"
           role="Applicant"
           parent="Case"/>
    <event id="Review"
           label="Review application"
           role="Caseworker"
           parent="Case"/>
  </events>
  <rules>
    <rule type="condition" source="Submit" target="Review"
          description="Submission is required first"/>
    <rule type="response" source="Submit" target="Review"
          description="Submission creates a review obligation"/>
  </rules>
</dcrGraph>
```

This section is conceptual boilerplate because the three attachments are full Portal exports, not simplified-import files. Confirm the exact root name and accepted attributes against the importer version. Do not assume that advanced full-XML features—Robots, computations, updates, initial marking, dynamic datasets, or embedded DMN—survive the simplified route.

## 14. What to copy and what to regenerate

Copy from a known-good export:

- Overall element ordering and empty collections.
- Complete event `<custom>` blocks.
- Graph-wide `<custom>` structure.
- An embedded DMN expression and its namespace declarations.
- Existing cross-scope `link` values when the hierarchy is unchanged.
- Version-specific form and event data attributes.

Regenerate for the new graph:

- Event IDs, labels, label mappings, expression IDs, and relation references.
- Coordinates, sequence numbers, descriptions, roles, groups, and phases.
- Initial included, executed, and pending sets.
- DMN element IDs and synchronized compiled expression.
- Repository metadata, if the importer does not create it.

Never copy stale:

- Graph/revision IDs, GUIDs, hash, owner, organization, or environment.
- Runtime state from a running case when the goal is a fresh model.
- Qualified `link` paths after moving or renaming containers.

## 15. Validation checklist

### XML integrity

- The document is well formed and UTF-8 encoded.
- Every event ID is globally unique.
- Every relation endpoint exists.
- Every computation, guard, and update expression reference resolves.
- Every label mapping resolves to both an event and a label.
- Every marking entry resolves to an event.
- XML attribute values are escaped.

### Semantic behavior

- Initially included and pending sets match the state table.
- Each true and false guard path has been simulated.
- Editable choices remove stale branches and stale obligations.
- Excluded pending events behave correctly if re-included.
- One-shot events cannot accidentally repeat.
- Every Robot is triggered only by a pending response and terminates.
- Subprocesses reach acceptance in all intended paths.
- Classical nesting is not used merely for visual grouping.
- Time tests use a controlled simulation clock.
- DMN inputs, result types, fallback rules, and hit policy are tested.

### Host integration

- Roles and read permissions display correctly.
- Previously executed reusable events remain selectable when intended.
- Choice values serialize with the expected boolean/integer/string type.
- File events work with the host's storage and security policy.
- Computed label and dataset values render correctly.
- Automatic events are hidden from ordinary user task lists.

## 16. Frequent errors

| Error | Consequence | Correction |
|---|---|---|
| Only responding to an excluded target | Obligation exists in history but is not active | Add a guarded include under the same route |
| Only including a required target | Target is available but not obligatory | Add a response |
| Include without complementary exclude on editable data | Old branch stays active | Add the inverse guarded exclude |
| Response without complementary co-response on editable obligation | Old obligation stays pending | Add inverse co-response or exclude, depending on intent |
| Treating a guard as enablement | Source can execute even when the guard is false | Use a condition/milestone to constrain source execution |
| Omitting self-exclude for a one-shot event | Event can repeat | Add self-exclude |
| Robot included but never pending | Robot never runs | Add a response trigger |
| Robot continually made pending | Execution loop until safety limit | Add explicit termination logic |
| Using `nesting` for an optional section | Completion semantics become too strong | Use plain events or an accepting subprocess |
| Copying graph metadata/hash | Import or repository identity conflicts | Remove stale `<meta>` or let the importer regenerate it |
| Editing only DMN `<definitions>` | Compiled `value` becomes inconsistent | Keep both representations synchronized |
| Inventing spawn or cross-scope serialization | Version-specific import failures | Export a minimal fixture first |

## 17. Coverage of the supplied examples

| Component | Corona | DMN chatbot | SU | Status in this guide |
|---|---:|---:|---:|---|
| Plain events | yes | yes | yes | Observed |
| Form containers | no | no | yes | Observed |
| Nesting | yes | no | yes | Observed |
| Subprocesses | yes | no | yes | Observed |
| Deep nested scopes | yes | no | yes | Observed |
| User/domain roles | yes | yes | yes | Observed |
| Robot | yes | yes | no | Observed |
| LocalRobot | no | no | yes | Observed |
| Computation | yes | yes | no | Observed |
| Computed subprocess | yes | no | no | Observed |
| Embedded DMN | yes | yes | no | Observed |
| Condition | no | yes | yes | Observed |
| Response | yes | yes | yes | Observed |
| Co-response | yes | no | no | Observed |
| Include | yes | no | yes | Observed |
| Exclude | yes | no | yes | Observed |
| Milestone | no | yes | yes | Observed |
| Update | no | yes | no | Observed |
| Fixed date arithmetic | yes | no | no | Observed |
| Relation `time` value | no | no | yes | Observed, version-sensitive |
| Runtime marking | yes | yes | yes | Observed |
| Spawn/template spawn | no | no | no | Unverified serialization |
| Initial timestamps/deadlines | no | no | no | Unverified serialization |
| Effect continuations | no | no | no | Unverified serialization |

## 18. Recommended authoring sequence

1. Define event IDs, roles, data types, and container semantics.
2. Write the intended initial marking as a table.
3. Add labels and label mappings.
4. Add unguarded conditions and milestones for genuine enablement constraints.
5. Add responses and co-responses for obligations.
6. Add includes and excludes for dynamic membership.
7. Add expressions, then connect them by `expressionId` or `valueExpressionId`.
8. Add Robots and computations after their triggers and termination are clear.
9. Add DMN only when a table is clearer than ordinary guarded relations.
10. Add layout and Portal metadata last.
11. Run structural reference checks.
12. Import a new copy and simulate marking changes after every event.
13. Test the graph through the real host application.

The core discipline is simple: every XML relation should have a one-sentence marking effect, and every marking change should be verified after import.
