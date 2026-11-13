# Outcome table through the Portal

| Check | Result |
|---|---|
| F1: the REST event list shows the result | yes |
| Each input set in a fresh simulation | 11 of 11 correct |
| All input sets in one simulation (F4) | 11 of 11 correct |

| Run | Inputs | Want | Got | Pending after TurnOutcome | OK |
|---|---|---|---|---|---|
| isolated | out_of_scope, none, none, 0 | result 1:out_of_scope | result 1:out_of_scope | ['FAQ_OutOfScope'] | ok |
| isolated | unsure, none, none, 0 | result 2:clarify | result 2:clarify | ['Outcome_Clarify'] | ok |
| isolated | in_scope, none, none, 0 | result 3:not_covered | result 3:not_covered | ['FAQ_NoMatch'] | ok |
| isolated | in_scope, single, one_answers, 0 | result 4:answer | result 4:answer | ['Outcome_Answer'] | ok |
| isolated | in_scope, list, related, 0 | result 5:offer | result 5:offer | ['Outcome_Offer'] | ok |
| isolated | in_scope, list, one_answers, 0 | result 6:confirm | result 6:confirm | ['Outcome_Confirm'] | ok |
| isolated | in_scope, list, several, 0 | result 7:clarify | result 7:clarify | ['Outcome_Clarify'] | ok |
| isolated | in_scope, list, several, 1 | result 8:offer | result 8:offer | ['Outcome_Offer'] | ok |
| isolated | in_scope, list, none, 0 | result 9:not_covered | result 9:not_covered | ['FAQ_NoMatch'] | ok |
| isolated | in_scope, single, related, 0 | result 5:offer | result 5:offer | ['Outcome_Offer'] | ok |
| isolated | in_scope, single, none, 0 | result 9:not_covered | result 9:not_covered | ['FAQ_NoMatch'] | ok |
| sequential | out_of_scope, none, none, 0 | result 1:out_of_scope | result 1:out_of_scope | ['FAQ_OutOfScope'] | ok |
| sequential | unsure, none, none, 0 | result 2:clarify | result 2:clarify | ['Outcome_Clarify'] | ok |
| sequential | in_scope, none, none, 0 | result 3:not_covered | result 3:not_covered | ['FAQ_NoMatch'] | ok |
| sequential | in_scope, single, one_answers, 0 | result 4:answer | result 4:answer | ['Outcome_Answer'] | ok |
| sequential | in_scope, list, related, 0 | result 5:offer | result 5:offer | ['Outcome_Offer'] | ok |
| sequential | in_scope, list, one_answers, 0 | result 6:confirm | result 6:confirm | ['Outcome_Confirm'] | ok |
| sequential | in_scope, list, several, 0 | result 7:clarify | result 7:clarify | ['Outcome_Clarify'] | ok |
| sequential | in_scope, list, several, 1 | result 8:offer | result 8:offer | ['Outcome_Offer'] | ok |
| sequential | in_scope, list, none, 0 | result 9:not_covered | result 9:not_covered | ['FAQ_NoMatch'] | ok |
| sequential | in_scope, single, related, 0 | result 5:offer | result 5:offer | ['Outcome_Offer'] | ok |
| sequential | in_scope, single, none, 0 | result 9:not_covered | result 9:not_covered | ['FAQ_NoMatch'] | ok |
