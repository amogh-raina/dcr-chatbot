# Topic exploration graph change

| Events | Initial inclusion/pending | Repeatability | Purpose |
|---|---|---|---|
| Existing Home/global/menu/answer events | Unchanged: all included; only Home pending | Reusable | Existing FAQ flow |
| FAQ_Explored_1 … FAQ_Explored_5 | Included, not pending; disabled until all topic answers executed | Reusable | DCR-controlled topic completion and explicit review/back choices |

Completion means an answer was displayed and acknowledged, not that the user meets an eligibility condition. Execution history lasts for the current simulation and is not reset by Review.

Changed relation effects:
- Each existing answer→menu response is guarded by at least one OTHER topic answer remaining unexecuted.
- A complementary answer→explored response creates the completion obligation when every OTHER topic answer has executed. Omitting the source from the guard avoids relying on guard evaluation timing for the current execution.
- Conditions from every topic answer to its explored event prevent premature execution of the completion choice.
- Home→menu is guarded by the topic not yet being fully explored. Home→explored under the complementary guard reopens completed-topic navigation.
- Explored=1 (Review questions) responds to the existing topic menu; Explored=0 responds to Home. The explored event itself is fulfilled by execution.
- Home co-responds to all unselected explored events; the global selector co-responds to every explored event to cancel stale completion prompts on cross-topic questions.

The UI uses API metadata and executed answer labels to hide read suggestions. Review mode is identified from the executed, graph-issued Review choice plus the pending original topic menu; completion is never inferred from a UI count.

New group tags: FAQTopic:N joins each topic menu, its answers and its completion event; FAQHideRead selects history-aware presentation; FAQTopicExplored identifies the completion event. Existing static menu/global values and all canonical answer descriptions stay unchanged.

Serialization follows existing full Portal custom/groups, choice dictionaries and condition/response/co-response patterns. Boolean @executed guards occur in the existing project fixtures. Local structural/semantic checks do not substitute for import into the target DCR engine.
