"""Builder steps for the graph split and the outcome table (spec 03, T3 and T4).

build_clean_graph.py calls apply(h) once, after the handover and Panel_Context blocks and before the sweep of unused
expressions. `h` carries the builder's own helpers (add_event, relation, add_expr, sub, html, events, ...), so the
steps add events and relations through the same code path as every other event of the graph.

S1 session events        Session_Chat, Session_Panel, and the conditions that gate the two search inputs and the selector
S2 panel search          Help_UserQuestion, Help_Retrieve (Robot, same effect), Help_Retrieval* and their relations
S3 outcome table         TurnOutcome, the outcome events and messages, and (--outcome dmn) the DMN chain
"""

import xml.etree.ElementTree as ET

import dmn_table                      # same folder; it puts the repository root on sys.path
from dcrai.chat import outcome as oc  # the rows and the outcome-to-event map: one source for code and graph

# Roles and colours are the builder's; the strings below are names this module owns.
SESSION_GROUP = "Session"
HELP_GROUP = "HelpRetrieval"
GATE_GROUP = "Gate"
OUTCOME_GROUP = "Outcome"
MSG_GROUP = "Msg"

# Existing events that gain an Outcome:<name> group in S3 (they are the pending events of three outcomes).
OUTCOME_GROUPS = (("FAQ_NoMatch", "Outcome:not_covered"), ("FAQ_OutOfScope", "Outcome:out_of_scope"),
                  ("Help_Handover", "Outcome:handover"))

TABLE_EVENT = "OutcomeTable"
TABLE_EXPRESSION = "OutcomeTable-computation"
TURN_START, TURN_RESULT, TURN_OUTCOME = "TurnStart", "TurnResult", "TurnOutcome"

# Texts of the outcome events: the host's current strings (identical wording) and spec 01's WD2 texts.
TEXTS = {
    "Outcome_Confirm": "Is this what you are asking?",
    "Outcome_Clarify": "I found a few questions that may fit. Which one is closest?",
    "Outcome_Offer": "No FAQ answers exactly this. These are on the same topic and may help:",
    "FAQ_Msg_OfferOne": "No FAQ answers exactly this. This one is on the same topic and may help:",
    "FAQ_Msg_ScopeQuestion": "Is your question about handicaptillæg, the SU disability supplement?",
    "FAQ_Msg_Rephrase": "Could you rephrase your question? A few more words about your situation help.",
}

GATE_ITEMS = {  # event id -> (kind, [(label, value)])
    "GateScope": ("strchoice", [("In scope", "in_scope"), ("Out of scope", "out_of_scope"), ("Unsure", "unsure")]),
    "GateSearch": ("strchoice", [("No match", "none"), ("Single match", "single"), ("List of candidates", "list")]),
    "GateRelevance": ("strchoice", [("None kept", "none"), ("Same topic only", "related"),
                                    ("One answers", "one_answers"), ("Several answer", "several")]),
    "GateClarified": ("intchoice", [("No", 0), ("Yes", 1)]),
}
assert tuple(GATE_ITEMS) == dmn_table.NAMES


def declared_groups(variant):
    """Group names this module adds to the graph-level group list."""
    names = [SESSION_GROUP, HELP_GROUP, OUTCOME_GROUP, MSG_GROUP] + ["Outcome:" + o for o in oc.OUTCOMES]
    if variant == "dmn":
        names.append(GATE_GROUP)
    return names


# ------------------------------------------------------------------ S1: session events
def session_events(h):
    h.add_event("Session_Chat", "Chat session started", "Chatbot", "label", 40, 100, (SESSION_GROUP,),
                "<p>Executed once by the chat host when the chat opens. It admits the chat's search input "
                "(FAQ_UserQuestion). The application's help panel never executes it.</p>",
                "Session event. Keeps the chat's search input closed in the application session.", h.AUTO)
    h.add_event("Session_Panel", "Help panel session started", "Chatbot", "label", 40, 220, (SESSION_GROUP,),
                "<p>Executed once by the application host when the application starts. It admits the help panel's "
                "search input (Help_UserQuestion) and the follow-up selector. The chat never executes it, so the "
                "chat cannot fire a determination.</p>",
                "Session event. Keeps the panel's search input and the selector closed in the chat session.", h.AUTO)
    h.relation("condition", "Session_Chat", "FAQ_UserQuestion",
               description="The chat search input opens only in a chat session")
    h.relation("condition", "Session_Panel", "Help_UserQuestion",
               description="The panel search input opens only in an application session")
    h.relation("condition", "Session_Panel", h.SELECTOR,
               description="Determinations are asked in the application session only")


# ------------------------------------------------------------------ S2: the panel's search Robot
def panel_search(h):
    grp = (HELP_GROUP,)
    h.add_event("Help_UserQuestion", "Type your question (help panel)", "Chatbot", "text", 200, 1000, grp,
                "Free-text question from the application's help panel. The host executes this event with the "
                "typed text, after FAQ_Triage = 1 and Session_Panel.",
                "Input event of the help panel. Executing it makes Help_Retrieve pending.", h.INPUT)
    h.add_event("Help_Retrieve", "Retrieve matching FAQ for the help panel (automatic)", "Robot", "text", 520, 1000, grp,
                "Automatic. Calls the FAQ retrieval service through the organisation effect.",
                "Second Robot, same effect as FAQ_Retrieve with its own continuations. Pending only after "
                "Help_UserQuestion executes.",
                ("#666666", "#ffffff", "#434343"),
                effect={"name": h.EFFECT_NAME, "parameters": [
                    ("q", "Help_UserQuestion", "true"),
                    ("ContinueOnTimeout", '"Help_RetrievalTimeout"', "false"),
                    ("ContinueOnFail", '"Help_RetrievalFail"', "false"),
                    ("ContinueOnOk", '"Help_RetrievalOk"', "false")]})
    h.add_event("Help_RetrievalOk", "Help panel retrieval result (automatic)", "System", "text", 840, 960, grp,
                "Receives the service response as its value: JSON text with decision, id, question, answer, "
                "citation and up to three options.",
                "Effect continuation on success. The host reads the result from this value.", h.AUTO)
    h.add_event("Help_RetrievalFail", "Help panel retrieval failed (automatic)", "System", "label", 840, 1060, grp,
                "Effect continuation on failure.", "Effect continuation on failure.", h.AUTO)
    h.add_event("Help_RetrievalTimeout", "Help panel retrieval timed out (automatic)", "System", "label", 840, 1160,
                grp, "Effect continuation on timeout.", "Effect continuation on timeout.", h.AUTO)
    # Not in FAQAnswer: the determination result collector reads that group (retrieval_runtime.py).
    h.add_event("Help_RetrievalUnavailable", "The FAQ search is temporarily unavailable (help panel)", "Chatbot",
                "label", 1160, 1110, grp,
                "<p>The FAQ search is temporarily unavailable. Please try again in a moment.</p>",
                "User-facing message after a failed or timed-out retrieval from the help panel.", h.OUTCOME)
    h.relation("include", "FAQ_Triage", "Help_UserQuestion", guard="FAQ_Triage = 1",
               description="Only an in-scope question may search")
    h.relation("exclude", "FAQ_Triage", "Help_UserQuestion", guard="FAQ_Triage != 1")
    h.relation("response", "Help_UserQuestion", "Help_Retrieve")
    h.relation("response", "Help_RetrievalFail", "Help_RetrievalUnavailable")
    h.relation("response", "Help_RetrievalTimeout", "Help_RetrievalUnavailable")


# ------------------------------------------------------------------ S3: outcome events, TurnOutcome, the DMN
def _add_group(h, eid, name):
    ev = next(e for e in h.events.findall("event") if e.get("id") == eid)
    h.sub(ev.find("custom/groups"), "group", name)


def outcome_events(h):
    """TurnOutcome with one guarded response and co-response per outcome, the new outcome events and messages."""
    h.add_event(TURN_OUTCOME, "Outcome of this question turn", "Chatbot", "strchoice", 1500, 100, (OUTCOME_GROUP,),
                "<p>The host executes this event once per question turn with the outcome as value: answer, confirm, "
                "offer, clarify, not_covered, out_of_scope or handover (the comment holds the table row, where the "
                "outcome came from and the miss count). Each value makes exactly one outcome event pending and "
                "closes the other six.</p>",
                "Host writes the outcome here; DCR admits exactly one outcome event. The table in code or in "
                "OutcomeTable decides the value.", h.INPUT,
                items=[("Answer", "answer"), ("Confirm", "confirm"), ("Offer", "offer"), ("Clarify", "clarify"),
                       ("Not covered", "not_covered"), ("Out of scope", "out_of_scope"), ("Handover", "handover")])
    new = {
        "Outcome_Answer": ("Outcome: show the answer", "",
                           "Pending after outcome answer. No text: the FAQ answer itself is the content."),
        "Outcome_Confirm": ("Outcome: confirm the candidate", TEXTS["Outcome_Confirm"],
                            "Pending after outcome confirm (a list pruned to one FAQ). The host asks yes or no."),
        "Outcome_Offer": ("Outcome: offer related questions", TEXTS["Outcome_Offer"],
                          "Pending after outcome offer (nothing answers, the same topic only; or a second list)."),
        "Outcome_Clarify": ("Outcome: ask which question fits", TEXTS["Outcome_Clarify"],
                            "Pending after outcome clarify (several FAQs answer, or the scope is unsure)."),
    }
    for i, (eid, (label, text, purpose)) in enumerate(new.items()):
        h.add_event(eid, label, "Chatbot", "label", 1500, 260 + 100 * i, (OUTCOME_GROUP, "Outcome:" + eid.split("_")[1].lower()),
                    h.html(text) if text else "", purpose, h.OUTCOME)
    messages = {
        "FAQ_Msg_OfferOne": ("Message: offer one related question", "Text of the offer when one FAQ is offered."),
        "FAQ_Msg_ScopeQuestion": ("Message: scope question", "Text of the scope question (outcome clarify, kind scope)."),
        "FAQ_Msg_Rephrase": ("Message: ask to rephrase", "Text shown after the applicant rejects a candidate."),
    }
    for i, (eid, (label, purpose)) in enumerate(messages.items()):
        h.add_event(eid, label, "Chatbot", "label", 1800, 260 + 100 * i, (MSG_GROUP,), h.html(TEXTS[eid]),
                    purpose + " Read by the host, not executed. No relations.", h.OUTCOME)
    for eid, group in OUTCOME_GROUPS:
        _add_group(h, eid, group)
    for outcome, eid in oc.OUTCOME_EVENT.items():
        h.relation("response", TURN_OUTCOME, eid, guard=f'{TURN_OUTCOME} = "{outcome}"')
        h.relation("coresponse", TURN_OUTCOME, eid, guard=f'{TURN_OUTCOME} != "{outcome}"')


def dmn_element(xml_text):
    """The <definitions> element for the graph: plain tag names, xmlns declared on the element itself.

    ElementTree would hoist namespace declarations to the root and put every unprefixed element of the graph into the
    DMN namespace; the Portal export keeps them on <definitions>, so the names are written as literal strings.
    """
    root = ET.fromstring(xml_text)
    for el in root.iter():
        el.tag = el.tag.rsplit("}", 1)[-1]
        attrib = {}
        for k, v in el.attrib.items():
            if k.startswith("{"):
                ns, local = k[1:].split("}")
                k = "biodi:" + local if ns == dmn_table.BIODI_NS else local
            attrib[k] = v
        el.attrib.clear()
        el.attrib.update(attrib)
        if el.text is not None and not el.text.strip():
            el.text = None
        if el.tail is not None and not el.tail.strip():
            el.tail = None
    attrib = {"xmlns": dmn_table.DMN_NS, "xmlns:biodi": dmn_table.BIODI_NS, **root.attrib}
    root.attrib.clear()
    root.attrib.update(attrib)
    return root


def add_dmn_expr(h, expr_id, names, types, rows):
    """The expression of a DMN event: compiled `value` by the rule of the observed exports, plus <definitions>."""
    assert not any(x.get("id") == expr_id for x in h.expressions), expr_id
    expr = h.sub(h.expressions, "expression", id=expr_id, value=dmn_table.compile_table(names, rows), type="DMN")
    expr.append(dmn_element(dmn_table.definitions_xml(names, types, rows)))
    return expr


def outcome_table(h):
    """TurnStart, the four gate inputs, the DMN Robot and its result label (--outcome dmn only)."""
    names = dmn_table.NAMES
    h.add_event(TURN_START, "Start an outcome table evaluation", "Chatbot", "label", 1500, 700, (GATE_GROUP,),
                "<p>Executed by the host at the start of each outcome table evaluation. It makes the four table "
                "inputs pending, so the table runs once after the last of them.</p>",
                "Resets the table inputs for a new turn (shadow and dcr modes only).", h.AUTO)
    for i, name in enumerate(names):
        kind, items = GATE_ITEMS[name]
        h.add_event(name, "Table input: " + name[4:].lower(), "Chatbot", kind, 1800, 700 + 100 * i, (GATE_GROUP,),
                    "<p>Input " + str(i + 1) + " of the outcome table. Values: "
                    + ", ".join(str(v) for _, v in items) + ".</p>",
                    "DMN input. The event id is the input label of the decision table (alphanumeric by design).",
                    h.AUTO, items=items)
    h.add_event(TABLE_EVENT, "Outcome table (automatic)", "Robot", "none", 2100, 880, (GATE_GROUP,),
                "<p>Automatic. The decision table of the outcome function (nine rows, first match wins). "
                "Runs once after all four inputs are executed. Output: row number and outcome, for example "
                "6:confirm.</p>",
                "DMN computation event. Generated from dcrai/chat/outcome.py ROWS by tools/clean_graph/dmn_table.py.",
                ("#666666", "#ffffff", "#434343"), computation=TABLE_EXPRESSION)
    h.add_event(TURN_RESULT, "Outcome table result", "Chatbot", "label", 2400, 880, (GATE_GROUP,),
                "<p>Receives the text result followed by the table output, for example result 6:confirm. "
                "The host reads it in shadow and dcr modes.</p>",
                "Result of the last evaluation. Written by an update relation from OutcomeTable.", h.OUTCOME)
    for name in names:
        h.relation("response", TURN_START, name)
    for name in names:
        link = f"{name}--condition--{TABLE_EVENT}"
        h.relation("condition", name, TABLE_EVENT, link=link)
        h.relation("milestone", name, TABLE_EVENT, link=link)
        h.relation("response", name, TABLE_EVENT)
    link = f"{TABLE_EVENT}--condition--{TURN_RESULT}"
    h.relation("condition", TABLE_EVENT, TURN_RESULT, link=link)
    h.relation("milestone", TABLE_EVENT, TURN_RESULT, link=link)
    h.relation("update", TABLE_EVENT, TURN_RESULT, value_expression=f'"result " + {TABLE_EVENT}')
    add_dmn_expr(h, TABLE_EXPRESSION, names, dmn_table.TYPES, dmn_table.outcome_rows())


def apply(h):
    """Add every split step to the graph. h.variant is 'dmn' or 'code'."""
    session_events(h)
    panel_search(h)
    outcome_events(h)
    if h.variant == "dmn":
        outcome_table(h)
