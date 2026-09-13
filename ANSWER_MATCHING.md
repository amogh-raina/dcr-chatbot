# Question-and-answer matching experiment

Branch: `experiment/faq-answer-matching`. Import `xml graphs/SU_handicaptillaeg_FAQ_AnswerMatching.xml` as a separate graph, then open `http://localhost:8080/?graphid=YOUR_NEW_GRAPH_ID` after restarting the Python app. Keep `SU_handicaptillaeg_FAQ_MVP.xml` for the previous flow. The demo UI supports this experiment too: use `/demo?graphid=YOUR_NEW_GRAPH_ID`. Its default graph remains the MVP (2012661), so specify the experimental graph ID explicitly.

| Events | Role/type | Initial included/pending | Reusable | Purpose |
|---|---|---|---|---|
| Existing Home, selectors, answers, explored prompts | Existing | Unchanged; only Home pending | Yes | Existing content/navigation |
| FAQ_Feedback_1 … FAQ_Feedback_5 | Chatbot / integer choice | Included / not pending | Yes | Yes=1, No=0 after the topic's answer |
| FAQ_Ready | Chatbot / integer choice | Included / not pending | Yes | “Feel free to ask me anything else.”; Back to topics=0 |

Each answer acknowledgement responds to its topic's feedback instead of directly to the menu/explored prompt. No responds to the original topic menu and the UI shows its entire catalogue. Yes responds to Ready. Ready's Back choice responds to Home. Home and global questions cancel stale feedback/Ready obligations. Home still uses answer execution history to route completed topics to their explored prompts, whose Review choice remains available. There are no automatic Robots; the application acknowledges exactly the answer returned pending by DCR. Navigation remains an obligation, as in the original graph.

Question–answer links use explicit API-visible group tags on answer events: `FAQChoice:<selector event ID>:<choice value>`. The graph authoring step derives these from existing guarded response relations; the runtime never reads XML or guesses event names. `FAQAnswerMatching` on the global selector opts into this experiment. Each canonical choice must have exactly one enabled FAQAnswer with that link and a nonempty description. Missing, duplicate or inconsistent links fail closed. Changing modeled routing requires updating the matching tag too; the runtime verifies the actual pending answer agrees with the link before acknowledging it.

OpenAI receives only candidate keys, questions and their verbatim modeled answers, with the latest question and previous delivered canonical question as context. It ranks answer relevance without generating or rewriting answers. The current default direct-match threshold is 0.80 with a 0.12 lead over the second candidate; environment settings may override these. A single strong match is revalidated against fresh DCR state, then executed directly; ambiguous candidates still require clarification, and weak matches use fallback.

After an answer the UI shows only Yes/No plus persistent navigation. Feedback uses an expiring, single-use server token tied to the DCR marking. Typed Yes/No also works while that feedback is current. No opens the full topic catalogue, including viewed questions; Yes shows Ready without question suggestions. Questions can switch topics at any time. Old graphs without the feature marker retain question-only ranking and confirmation.

The experimental XML now includes the current MVP navigation wording while retaining answer-first feedback relations. The repository XML in `xml graphs/` is authoritative; older project output copies have not been updated by this refresh.

Validation is local: XML structure plus a focused mocked-API flow check. Live Portal import, tag serialization and real matching quality still need checking with the new graph ID. No dependencies or model change is required, and no environment file is read during development checks.

The SDK structured JSON output follows the [official OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs). Scores remain heuristic, not calibrated probabilities.
