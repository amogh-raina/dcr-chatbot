# Live outcome eval (Help panel)

Graph 2014118, base http://127.0.0.1:8080, expected mode `shadow`, 43 runs.

## Gates

| Gate | Result |
|---|---|
| WRONG answers | 0 |
| Logged row differs from the table, DMN mismatch, mode not in effect | 0 |
| Mechanics scenarios failed | 4 (FAIL) |

## Verdicts

| Verdict | Runs |
|---|---|
| confirm_right | 6 |
| correct | 16 |
| missed | 1 |
| options_miss | 9 |
| partial | 3 |
| shown_options | 8 |

## By group

| Group | confirm_right | correct | missed | options_miss | partial | shown_options |
|---|---|---|---|---|---|---|
| A | 0 | 1 | 0 | 0 | 0 | 2 |
| C | 2 | 3 | 1 | 0 | 0 | 0 |
| F | 2 | 3 | 0 | 7 | 2 | 0 |
| M | 1 | 0 | 0 | 0 | 1 | 0 |
| N | 0 | 3 | 0 | 0 | 0 | 5 |
| O | 0 | 2 | 0 | 0 | 0 | 1 |
| S | 1 | 0 | 0 | 2 | 0 | 0 |
| T | 0 | 4 | 0 | 0 | 0 | 0 |

## Outcome mix

| Outcome | Row | Turns |
|---|---|---|
| answer | 4 | 10 |
| clarify | 7 | 1 |
| confirm | 6 | 6 |
| not_covered | 3 | 1 |
| not_covered | 9 | 3 |
| offer | 5 | 19 |
| out_of_scope | 1 | 3 |

Sources: {'code': 43}. Mismatches: 0. Latency median 2.85 s, p95 4.78 s.

Group O turns ending in row 1: 2 of 3.

## Mechanics

| Scenario | Result | Detail |
|---|---|---|
| second miss carries a handover | FAIL |  |
| person request: can I speak to a caseworker? | pass | status handover |
| person request: I want to talk to somebody | pass | status handover |
| person request: I'd like to talk to a real person | pass | status handover |
| person request: can I call someone about my case | pass | status handover |
| probe (no expectation): I need a human | info | status faq_confirm, outcome confirm |
| probe (no expectation): put me through to an advisor | info | status faq_related, outcome offer |
| probe (no expectation): give me a phone number | info | status faq_no_match, outcome not_covered |
| probe (no expectation): kan jeg tale med en sagsbehandler | info | status faq_out_of_scope, outcome out_of_scope |
| deadline wording gives a handover block once | pass | first True, second False |
| out of scope: what's the weather like in Copenhagen today? | FAIL | status faq_out_of_scope, outcome out_of_scope, row 1, searched True |
| out of scope: how do I apply for housing benefit? | FAIL | status faq_out_of_scope, outcome out_of_scope, row 1, searched True |
| out of scope: will I get the supplement with my condition? | FAIL | status faq_related, outcome offer, row 5, searched True |
| confirm accepted | pass | status question |
| confirm rejected | pass | status faq_none |

Not covered by this run: group V (needs a field on screen), the chat, and Danish input beyond the probe.
