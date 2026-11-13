#!/usr/bin/env python3
"""Local relation simulator and checks for SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml.

Usage: python tools/clean_graph/simulate_clean_graph.py "xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml"

Models conditions, milestones, responses, co-responses, includes, excludes, guards and a Robot whose effect
continuation runs with a fake result. It is a sanity check, not a replacement for the Portal simulator.
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dmn_table  # evaluator for the compiled DMN expression

class G:
    def __init__(self, path):
        r = ET.parse(path).getroot()
        res = r.find("specification/resources")
        self.expr = {x.get("id"): x.get("value") for x in res.find("expressions")}
        self.ev = [e.get("id") for e in res.find("events").iter("event")]
        self.rel = {}
        for kind in r.find("specification/constraints"):
            self.rel[kind.tag] = [dict(c.attrib) for c in kind]
        self.included = {e.get("id") for e in r.find("runtime/marking/included")}
        self.pending, self.executed, self.value = set(), set(), {}
        self.roles = {e.get("id"): [x.text for x in e.findall("custom/roles/role")] for e in res.find("events").iter("event")}
        self.effect = {e.get("id"): e.find("custom/effects") for e in res.find("events").iter("event")}
        self.computation = {e.get("id"): e.get("computation") for e in res.find("events").iter("event") if e.get("computation")}
        self.table_runs = []   # results of the DMN Robot, in order

    def ev_guard(self, expr):
        if expr is None: return True
        py = expr
        py = re.sub(r"([A-Za-z0-9_:]+)@executed", lambda m: f"({m.group(1)!r} in EX)", py)
        py = py.replace("!=", " NE ").replace(" and ", " and ").replace(" or ", " or ")
        py = re.sub(r"not\(", "not (", py)
        def val(tok):
            return f"V.get({tok!r})"
        py = re.sub(r"\b(?!and\b|or\b|not\b|true\b|false\b|NE\b)([A-Za-z_][A-Za-z0-9_:]*)\b(?=\s*(=|NE))", lambda m: val(m.group(1)), py)
        py = re.sub(r"(?<![=!<>])=(?!=)", "==", py)
        py = py.replace("NE", "!=").replace("true", "True").replace("false", "False")
        return bool(eval(py, {}, {"V": self.value, "EX": self.executed}))

    def g(self, rel):
        return self.ev_guard(self.expr.get(rel["expressionId"])) if rel.get("expressionId") else True

    def executable(self, e):
        if e not in self.included: return False
        for c in self.rel["conditions"]:
            if c["targetId"] == e and c["sourceId"] in self.included and c["sourceId"] not in self.executed: return False
        for m in self.rel["milestones"]:
            if m["targetId"] == e and m["sourceId"] in self.included and m["sourceId"] in self.pending: return False
        return True

    def run(self, e, value=None):
        assert self.executable(e), f"{e} not executable"
        if value is not None: self.value[e] = value
        self.executed.add(e); self.pending.discard(e)
        for k, f in (("responses", lambda t: self.pending.add(t)), ("coresponses", lambda t: self.pending.discard(t)),
                     ("includes", lambda t: self.included.add(t)), ("excludes", lambda t: self.included.discard(t))):
            for r in self.rel[k]:
                if r["sourceId"] == e and self.g(r): f(r["targetId"])
        self.robots()

    def robots(self):
        for _ in range(10):
            ran = False
            for e in self.ev:
                if "Robot" in self.roles[e] and e in self.pending and e in self.included and self.executable(e):
                    ran = True
                    self.run_robot(e)
            if not ran: break

    def run_robot(self, e):
        if e in self.computation:
            return self.run_dmn(e)
        # model: effect executes and its continuation event runs with the service result as value
        self.executed.add(e); self.pending.discard(e)
        for k, f in (("responses", lambda t: self.pending.add(t)), ("coresponses", lambda t: self.pending.discard(t))):
            for r in self.rel[k]:
                if r["sourceId"] == e and self.g(r): f(r["targetId"])
        self.last_outcome = getattr(self, "next_outcome", "FAQ_RetrievalOk")
        # each search Robot has its own continuations: FAQ_Retrieve -> FAQ_Retrieval*, Help_Retrieve -> Help_Retrieval*
        cont = ("Help_" if e.startswith("Help_") else "FAQ_") + self.last_outcome.split("_", 1)[1]
        assert "System" in self.roles[cont]
        self.value[cont] = '{"decision":"single_match"}'
        self.run(cont)

def run_dmn(self, e):
        # a DMN Robot: evaluate the compiled expression on the input events' values, keep the result as its value,
        # run its update relations (value expression  "text " + Event), then its responses and co-responses
        self.executed.add(e); self.pending.discard(e)
        result = dmn_table.evaluate_compiled(self.expr[self.computation[e]], self.value)
        self.value[e] = result
        self.table_runs.append(result)
        for r in self.rel.get("updates", []):
            if r["sourceId"] == e:
                m = re.fullmatch(r'"([^"]*)" \+ ([A-Za-z0-9_:]+)', self.expr[r["valueExpressionId"]])
                assert m, self.expr[r["valueExpressionId"]]
                self.value[r["targetId"]] = m.group(1) + str(self.value.get(m.group(2)))
        for k, f in (("responses", lambda t: self.pending.add(t)), ("coresponses", lambda t: self.pending.discard(t))):
            for r in self.rel[k]:
                if r["sourceId"] == e and self.g(r): f(r["targetId"])

G.run_dmn = run_dmn

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: check.bad += 1
check.bad = 0


P = sys.argv[1]
S = "FAQ_DeterminationSelector"
g = G(P)
g.rel.setdefault("excludes", [])
for k in ("responses", "coresponses", "includes", "excludes", "conditions", "milestones"):
    g.rel.setdefault(k, [])

check("FAQ_Retrieve" not in g.pending, "robot not pending initially")
check(not g.pending, "no pending responses initially (accepting)")
check("FAQ_Answered" in g.included and g.executable("FAQ_Answered"), "context event available")
check(all(f"Det{n}_Ask" not in g.included for n in ("05b", "09", "31", "42")), "Ask events start excluded")
check(not g.executable("FAQ_UserQuestion"), "question not executable before triage")
g.run("FAQ_Triage", 5)
check(not g.executable("FAQ_UserQuestion") and "FAQ_OutOfScope" in g.pending, "triage=5: no search, out-of-scope message pending")
g.run("FAQ_OutOfScope")
g.run("FAQ_Triage", 2)
check(not g.executable("FAQ_UserQuestion"), "triage=2 (reply): no search")
g.run("FAQ_Triage", 4)
check("FAQ_Goodbye" in g.pending and not g.executable("FAQ_UserQuestion"), "triage=4: goodbye pending, no search")
g.run("FAQ_Goodbye")
g.run("FAQ_Triage", 1)
SESSIONS = "Session_Chat" in g.ev   # graphs from before the split (2014078) have no session events
if SESSIONS:
    check(not g.executable("FAQ_UserQuestion"), "chat: triage=1 does not admit the question before Session_Chat")
    g.run("Session_Chat")
check(g.executable("FAQ_UserQuestion"), "triage=1 admits the question")
g.run("FAQ_UserQuestion", "can I get SU abroad")
check("FAQ_Retrieve" in g.executed and "FAQ_Retrieve" not in g.pending, "robot ran once, no longer pending")
check("FAQ_RetrievalOk" in g.executed and "FAQ_RetrievalUnavailable" not in g.pending, "ok continuation, no unavailable message")
g.next_outcome = "FAQ_RetrievalFail"; g.run("FAQ_UserQuestion", "again")
check("FAQ_RetrievalUnavailable" in g.pending, "fail -> unavailable message pending")
g.run("FAQ_RetrievalUnavailable"); g.next_outcome = "FAQ_RetrievalTimeout"; g.run("FAQ_UserQuestion", "third")
check("FAQ_RetrievalUnavailable" in g.pending, "timeout -> unavailable message pending")
g.run("FAQ_RetrievalUnavailable"); g.next_outcome = "FAQ_RetrievalOk"

check(not g.executable("Det05b_Ask"), "Ask not executable before selection")
if SESSIONS:
    check(not g.executable(S), "chat session: the follow-up selector is closed (the chat fires no determination)")
    g.run("Session_Panel")   # the determination mechanics below are checked as in an application session
g.run(S, 1)
check("Det05b_Ask" in g.pending and g.executable("Det05b_Ask"), "05b: selector=1 opens question")
check(not any(f"Det{n}_Ask" in g.included for n in ("09", "31", "42")), "others stay closed")
g.run("Det05b_Ask", True)
check("Det05b_Yes" in g.pending and "Det05b_No" not in g.pending, "yes -> yes outcome only")
g.run("Det05b_Ask", False)
check("Det05b_No" in g.pending and "Det05b_Yes" not in g.pending, "edited to no -> stale yes closed")
g.run("Det05b_No")
g.run(S, 4)
check("Det05b_Ask" not in g.included and "Det42_Ask" in g.pending, "selector=4 closes 05b, opens 42")
g.run(S, 3)
check("Det42_Ask" not in g.included and "Det31_Ask" in g.pending, "selector=3 drops unanswered 42")
for n, p in ((2, "Det09"), (3, "Det31"), (4, "Det42")):
    h = G(P)
    for k in ("excludes",): h.rel.setdefault(k, [])
    if SESSIONS: h.run("Session_Panel")
    h.run(S, n); h.run(p + "_Ask", False)
    check(p + "_No" in h.pending, f"{p}: full path to No")
# session events: the two search inputs and the selector open per interface (spec 03, R8 and R10)
def fresh():
    x = G(P)
    for k in ("responses", "coresponses", "includes", "excludes", "conditions", "milestones", "updates"):
        x.rel.setdefault(k, [])
    return x
if SESSIONS:
    c = fresh()
    c.run("Session_Chat"); c.run("FAQ_Triage", 1)
    check(c.executable("FAQ_UserQuestion") and not c.executable("Help_UserQuestion"),
          "Session_Chat only: the chat input is open, the panel input is not")
    c.run("FAQ_UserQuestion", "a chat question")
    check("FAQ_Retrieve" in c.executed and "Help_Retrieve" not in c.executed, "chat question runs FAQ_Retrieve only")
    q = fresh()
    q.run("FAQ_Triage", 1)
    check(not q.executable("Help_UserQuestion") and not q.executable("FAQ_UserQuestion"),
          "triage=1 alone admits neither input (no session event yet)")
    q.run("Session_Panel")
    check(q.executable("Help_UserQuestion") and not q.executable("FAQ_UserQuestion"),
          "Session_Panel only: the panel input is open, the chat input is not")
    q.run("Help_UserQuestion", "a panel question")
    check("Help_Retrieve" in q.executed and "Help_Retrieve" not in q.pending and "FAQ_Retrieve" not in q.executed,
          "panel question runs Help_Retrieve once, not FAQ_Retrieve")
    check("Help_RetrievalOk" in q.executed and "Help_RetrievalUnavailable" not in q.pending,
          "panel ok continuation, no unavailable message")
    q.next_outcome = "FAQ_RetrievalFail"; q.run("Help_UserQuestion", "again")
    check("Help_RetrievalUnavailable" in q.pending and "FAQ_RetrievalUnavailable" not in q.pending,
          "panel fail -> its own unavailable message pending")
    q.run("Help_RetrievalUnavailable"); q.next_outcome = "FAQ_RetrievalTimeout"; q.run("Help_UserQuestion", "third")
    check("Help_RetrievalUnavailable" in q.pending, "panel timeout -> unavailable message pending")
    q.run("FAQ_Triage", 5)
    check("Help_UserQuestion" not in q.included, "triage=5 closes the panel input")
    s2 = fresh()
    check(not s2.executable(S), "selector is closed without Session_Panel")
    s2.run("Session_Panel")
    check(s2.executable(S), "selector is open after Session_Panel")
    check(not any(r["targetId"].startswith("Form0") for k, rs in g.rel.items() for r in rs
                  if r["sourceId"] in ("Session_Chat", "Session_Panel")), "session events have no relation into Form0")
# application session (separate simulation of this graph): Form0 is open from the start, one field at a time
t = G(P)
for k in ("responses", "coresponses", "includes", "excludes", "conditions", "milestones"):
    t.rel.setdefault(k, [])
open_fields = sorted(e for e in t.included if e.startswith("Form0:"))
check(open_fields == ["Form0:Email"] and t.executable("Form0:Email"),
      f"application session: only the first field is open ({open_fields})")
t.run("Form0:Email", "a@b.dk")
check("Form0:Phone" in t.included and "Form0:Phone" in t.pending, "form chain continues inside subprocess")
into_form = [(r["sourceId"], k, r["targetId"]) for k, rs in t.rel.items() for r in rs
             if r["targetId"].startswith("Form0") and not r["sourceId"].startswith("Form0")]
check(not into_form, f"no relation from the FAQ layer into Form0: {into_form}")
roles = {e: g.roles[e] for e in g.ev}
robots = [e for e, r in roles.items() if "Robot" in r]
expected_robots = ["FAQ_Retrieve"] + (["Help_Retrieve"] if SESSIONS else []) + (["OutcomeTable"] if "OutcomeTable" in g.ev else [])
check(sorted(robots) == sorted(expected_robots), f"Robot events are the search Robots and the table: {robots}")
expected_system = ["FAQ_RetrievalFail", "FAQ_RetrievalOk", "FAQ_RetrievalTimeout"] + (
    ["Help_RetrievalFail", "Help_RetrievalOk", "Help_RetrievalTimeout"] if SESSIONS else [])
check(sorted(e for e, r in roles.items() if "System" in r) == sorted(expected_system), "System events are the effect continuations")
check(not any(e.startswith("FAQ_Menu") or e.startswith("FAQ_Answer_") or e == "FAQ_Home" for e in g.ev), "no menu / answer / home events")
# field help and handover (2026-10-08)
root = ET.parse(P).getroot()
form_ev = {e.get("id"): e for e in root.iter("event") if (e.get("id") or "").startswith("Form0:")
           and e.find("custom") is not None}
fields = [k for k in form_ev if k not in ("Form0:Complete", "Form0:Declined")]
check(all((form_ev[k].findtext("custom/eventDescription") or "").strip() for k in fields),
      f"every Form0 field has help text ({len(fields)} fields)")
a2 = [i.get("label") for i in form_ev["Form0:A2"].iter("item")]
check(not any(l.startswith("item ") for l in a2), f"A2 option labels are real ({a2})")
topics = {k: [x.text for x in form_ev[k].findall("custom/groups/group") if x.text.startswith("Topic:")] for k in fields}
check(all(len(v) == 1 for v in topics.values()), "every field has exactly one Topic tag")
h = G(P)
for k in ("responses", "coresponses", "includes", "excludes", "conditions", "milestones"):
    h.rel.setdefault(k, [])
form_before = ({e for e in h.included if e.startswith("Form0")}, {e for e in h.pending if e.startswith("Form0")})
check(h.executable("Help_Escalate") and "Help_Handover" not in h.pending, "handover idle at start")
h.run("Help_Escalate", 3)
check("Help_Handover" in h.pending, "escalation makes the handover message pending")
h.run("Help_Handover")
form_after = ({e for e in h.included if e.startswith("Form0")}, {e for e in h.pending if e.startswith("Form0")})
check(form_before == form_after, "escalation leaves Form0 untouched")
h.run("Help_Escalate", 1)
check("Help_Handover" in h.pending, "escalation can repeat")
welcome = next((e for e in root.iter("event") if e.get("id") == "FAQ_Welcome" and e.find("custom") is not None), None)
check(welcome is not None and "I am still learning" in (welcome.findtext("custom/eventDescription") or ""),
      "welcome event with the onboarding text")
examples = [g.text.split(":", 1)[1] for g in welcome.findall("custom/groups/group") if g.text.startswith("Example:")]
check(len(examples) == 3, f"three example questions ({examples})")
check("FAQ_Welcome" in g.included and not any("FAQ_Welcome" in (r["sourceId"], r["targetId"])
                                             for rs in g.rel.values() for r in rs), "welcome is included, no relations")
# outcome events (spec 03, R16): TurnOutcome makes exactly one outcome event pending
OUTCOME_EVENT = {"answer": "Outcome_Answer", "confirm": "Outcome_Confirm", "offer": "Outcome_Offer",
                 "clarify": "Outcome_Clarify", "not_covered": "FAQ_NoMatch", "out_of_scope": "FAQ_OutOfScope",
                 "handover": "Help_Handover"}
if "TurnOutcome" in g.ev:
    pending_outcomes = lambda x: sorted(x.pending & set(OUTCOME_EVENT.values()))
    for outcome, event in OUTCOME_EVENT.items():
        x = fresh()
        x.run("TurnOutcome", outcome)
        check(pending_outcomes(x) == [event], f"TurnOutcome={outcome}: exactly {event} is pending ({pending_outcomes(x)})")
    x = fresh()
    x.run("TurnOutcome", "confirm"); x.run("TurnOutcome", "offer")
    check(pending_outcomes(x) == ["Outcome_Offer"], f"confirm then offer, nothing acknowledged: only Outcome_Offer ({pending_outcomes(x)})")
    x.run("TurnOutcome", "not_covered")
    check(pending_outcomes(x) == ["FAQ_NoMatch"], "a later outcome closes the earlier ones")
    check(not any(r["targetId"].startswith("Form0") for r in x.rel["responses"] + x.rel["coresponses"]
                  if r["sourceId"] == "TurnOutcome"), "TurnOutcome has no relation into Form0")
    dictionary = [i.get("value") for i in ET.parse(P).getroot().find("specification/resources/events").iter("event")
                  if i.get("id") == "TurnOutcome" for i in i.iter("item")]
    check(sorted(dictionary) == sorted(OUTCOME_EVENT), f"TurnOutcome dictionary is the seven outcomes ({dictionary})")

# the outcome table as a DMN Robot (spec 03, R15): runs once, after the last input, on every turn
ROWS = [  # row, (GateScope, GateSearch, GateRelevance, GateClarified), TurnResult, outcome event after TurnOutcome
    (1, ("out_of_scope", "none", "none", 0), "result 1:out_of_scope", "FAQ_OutOfScope"),
    (2, ("unsure", "none", "none", 0), "result 2:clarify", "Outcome_Clarify"),
    (3, ("in_scope", "none", "none", 0), "result 3:not_covered", "FAQ_NoMatch"),
    (4, ("in_scope", "single", "one_answers", 0), "result 4:answer", "Outcome_Answer"),
    (5, ("in_scope", "list", "related", 0), "result 5:offer", "Outcome_Offer"),
    (6, ("in_scope", "list", "one_answers", 0), "result 6:confirm", "Outcome_Confirm"),
    (7, ("in_scope", "list", "several", 0), "result 7:clarify", "Outcome_Clarify"),
    (8, ("in_scope", "list", "several", 1), "result 8:offer", "Outcome_Offer"),
    (9, ("in_scope", "list", "none", 0), "result 9:not_covered", "FAQ_NoMatch")]
GATES = ["GateScope", "GateSearch", "GateRelevance", "GateClarified"]
if "OutcomeTable" in g.ev:
    d = fresh()
    check("OutcomeTable" not in d.executed and "OutcomeTable" not in d.pending, "table idle at start")
    d.run("TurnStart")
    check(all(x in d.pending for x in GATES), "TurnStart makes the four inputs pending")
    for gate, value in list(zip(GATES, ROWS[5][1]))[:3]:
        d.run(gate, value)
    check("OutcomeTable" in d.pending and "OutcomeTable" not in d.executed,
          "after three inputs the table is pending but has not run (milestones)")
    d.run("GateClarified", 0)
    check(d.table_runs == ["6:confirm"] and "OutcomeTable" not in d.pending, f"table ran once after the fourth input ({d.table_runs})")
    check(d.value.get("TurnResult") == "result 6:confirm", f"TurnResult holds the result ({d.value.get('TurnResult')})")
    # all nine rows in one simulation: the table runs again on each turn, and TurnOutcome then opens one event
    d = fresh()
    for row, inputs, result, event in ROWS:
        runs_before = len(d.table_runs)
        d.run("TurnStart")
        for gate, value in zip(GATES, inputs):
            d.run(gate, value)
        check(len(d.table_runs) == runs_before + 1 and d.value.get("TurnResult") == result,
              f"row {row}: table ran once more, TurnResult {d.value.get('TurnResult')!r} (want {result!r})")
        d.run("TurnOutcome", result.split(":")[1])
        check(pending_outcomes(d) == [event], f"row {row}: after TurnOutcome only {event} is pending ({pending_outcomes(d)})")
    check(len(d.table_runs) == 9, "nine turns, nine table runs")
    # the compiled expression and the host's table agree with the definitions inside the same expression
    expr = next(x for x in ET.parse(P).getroot().iter("expression") if x.get("id") == g.computation["OutcomeTable"])
    defs = next(c for c in expr if c.tag.endswith("definitions"))
    check(all(dmn_table.evaluate_definitions(defs, dict(zip(GATES, i))) == r[7:] for _, i, r, _ in ROWS),
          "definitions inside the expression agree with the compiled value on the nine rows")
else:
    check("TurnStart" not in g.ev and not any(e.startswith("Gate") for e in g.ev) and "TurnResult" not in g.ev,
          "code build: no DMN machinery (TurnStart, gates, OutcomeTable, TurnResult)")
print("FAILURES:", check.bad)
