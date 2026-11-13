# File inventory at the 2026-11-13 review

This is a snapshot before restaging. `git ls-files` reports the existing index; the candidate list also
includes nonignored new files and omits files removed by the clean frontend build.
No staging, commit or push was performed by the review. Run the commands in the linked review before committing.

[Review and tracking policy](REPOSITORY_REVIEW.md)

Existing index: **156 paths**. Candidate count below excludes this inventory and review if new.

## Existing index

```text
.agents/skills/dcr-xml-builder/SKILL.md
.agents/skills/dcr-xml-builder/agents/openai.yaml
.agents/skills/dcr-xml-builder/assets/full-graph-template.xml
.agents/skills/dcr-xml-builder/references/rest-simulation-api.md
.agents/skills/dcr-xml-builder/references/semantics.md
.agents/skills/dcr-xml-builder/references/xml-patterns.md
.agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py
.dockerignore
.env.example
.gitignore
CLAUDE.md
Dockerfile
README.md
app.py
dcrai/__init__.py
dcrai/application/__init__.py
dcrai/application/application_runtime.py
dcrai/chat/__init__.py
dcrai/chat/faq_runtime.py
dcrai/chat/retrieval_runtime.py
dcrai/dcr/__init__.py
dcrai/dcr/dcr_repository.py
dcrai/legacy/__init__.py
dcrai/legacy/chatnlp.py
dcrai/legacy/questions.py
dcrai/legacy/utility.py
dcrai/llm/__init__.py
dcrai/llm/openchat.py
dcrai/llm/retrieval_llm.py
dcrai/observability/__init__.py
dcrai/observability/interaction_log.py
dcrai/paths.py
dcrai/prompts.py
demo-ui/index.html
demo-ui/package-lock.json
demo-ui/package.json
demo-ui/preview/.gitignore
demo-ui/preview/preview.mjs
demo-ui/preview/serve.mjs
demo-ui/src/App.jsx
demo-ui/src/ApplicationDemo.jsx
demo-ui/src/Icon.jsx
demo-ui/src/SupportChat.jsx
demo-ui/src/ThemeToggle.jsx
demo-ui/src/application.css
demo-ui/src/assets/icons8-bot.gif
demo-ui/src/chat.css
demo-ui/src/main.jsx
demo-ui/src/sessionId.js
demo-ui/src/sessionId.test.mjs
demo-ui/src/styles.css
demo-ui/src/theme.css
demo-ui/vite.config.js
docker-compose.yml
docs/README.md
docs/architecture/INTEGRATION_PLAN.md
docs/architecture/Overview.md
docs/architecture/XHAIL.md
docs/guides/APPLICATION_DEMO.md
docs/guides/DEPLOY.md
docs/handoffs/HANDOFF_2026-10-09_followup_eval.md
docs/handoffs/NEXT_SESSION.md
docs/handoffs/UI_HANDOFF.md
docs/sources/SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md
docs/specs/README.md
evals/README.md
evals/__init__.py
evals/calibrate_thresholds.py
evals/cases/eval_composed_queries.json
evals/cases/eval_followup_queries.json
evals/cases/eval_queries.json
evals/cases/triage_labels.json
evals/diagnose_queries.py
evals/eval_composed.py
evals/eval_followups.py
evals/reports/calibration_report.md
evals/reports/composed_report.md
evals/reports/followup_report.md
evals/runs/eval_scores.json
evals/runs/eval_scores_query.json
evals/runs/followup_results.json
external_scripts/__init__.py
external_scripts/graph_parser.py
faq_search/api.py
faq_search/build_faq_data.py
faq_search/data/faq_embeddings.npy
faq_search/data/faq_embeddings_meta.json
faq_search/data/faq_qa_records.json
faq_search/embed_faq_data.py
faq_search/requirements.txt
faq_search/retriever.py
prompts/README.md
prompts/base/README.md
prompts/followup/pick.txt
prompts/followup/same.txt
prompts/forms/interpret.txt
prompts/forms/rank_system.txt
prompts/judges/README.md
prompts/panel/contextual.txt
prompts/panel/distress.txt
prompts/relevance/fits.txt
prompts/relevance/relevant.txt
prompts/rewrite/panel.txt
prompts/rewrite/rewrite.txt
prompts/routing/route.txt
prompts/triage/contextual.txt
prompts/triage/meta.txt
prompts/triage/reply.txt
requirements.txt
scripts/diagnose_application_entry.py
static/demo/assets/icons8-bot-K3HB9ED8.gif
static/demo/assets/index-BMLDYZF-.js
static/demo/assets/index-BYgjQHef.css
static/demo/assets/index-BabljOgH.css
static/demo/assets/index-Btw1vNpb.css
static/demo/assets/index-C98xnsyZ.js
static/demo/assets/index-CE8JIrr0.js
static/demo/index.html
static/script.js
templates/index.html
tests/test_application_demo.py
tests/test_application_faq.py
tests/test_dcr_choice_runtime.py
tests/test_dcr_simulation_api.py
tests/test_faq_api.py
tests/test_faq_data.py
tests/test_faq_eval.py
tests/test_faq_mvp.py
tests/test_faq_retriever.py
tests/test_faq_scope.py
tests/test_mvp_presentation.py
tests/test_openchat.py
tests/test_pending_event_selection.py
tests/test_retrieval_runtime.py
tests/test_static_information.py
tests/test_structured_application.py
traces/README.md
xml graphs/Corona - ChatBot SOP.xml
xml graphs/DCR-JS Graph.xml
xml graphs/DMN chatbot - english.xml
xml graphs/Pension Toy Example.xml
xml graphs/SU (Handicap) visualization.html
xml graphs/SU (Handicap).xml
xml graphs/SU_FAQ_MVP.xml
xml graphs/SU_chatbot_FAQ_enriched_simple.xml
xml graphs/SU_chatbot_FAQ_part_with_static_chatbot (1).xml
xml graphs/SU_handicap_conversation.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Contact.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Conversational.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Demo.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Flat.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Lean.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Multi.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml
xml graphs/SU_handicaptillaeg_FAQ_MVP.xml
xml graphs/pension_toy.xml
```

## Current nonignored files

```text
.agents/skills/dcr-xml-builder/SKILL.md
.agents/skills/dcr-xml-builder/agents/openai.yaml
.agents/skills/dcr-xml-builder/assets/full-graph-template.xml
.agents/skills/dcr-xml-builder/references/rest-simulation-api.md
.agents/skills/dcr-xml-builder/references/semantics.md
.agents/skills/dcr-xml-builder/references/xml-patterns.md
.agents/skills/dcr-xml-builder/scripts/validate_dcr_xml.py
.dockerignore
.env.example
.gitattributes
.github/workflows/checks.yml
.gitignore
AGENTS.md
CLAUDE.md
Dockerfile
README.md
app.py
dcrai/__init__.py
dcrai/application/__init__.py
dcrai/application/application_runtime.py
dcrai/application/panel_context.py
dcrai/chat/__init__.py
dcrai/chat/faq_runtime.py
dcrai/chat/outcome.py
dcrai/chat/outcome_runtime.py
dcrai/chat/retrieval_runtime.py
dcrai/dcr/__init__.py
dcrai/dcr/dcr_repository.py
dcrai/legacy/__init__.py
dcrai/legacy/chatnlp.py
dcrai/legacy/questions.py
dcrai/legacy/utility.py
dcrai/llm/__init__.py
dcrai/llm/openchat.py
dcrai/llm/retrieval_llm.py
dcrai/observability/__init__.py
dcrai/observability/interaction_log.py
dcrai/observability/redaction.py
dcrai/observability/trace_reader.py
dcrai/observability/turn_trace.py
dcrai/paths.py
dcrai/prompts.py
dcrai/registry.py
demo-ui/eslint.config.js
demo-ui/index.html
demo-ui/package-lock.json
demo-ui/package.json
demo-ui/preview/.gitignore
demo-ui/preview/preview.mjs
demo-ui/preview/serve.mjs
demo-ui/preview/thread.mjs
demo-ui/src/App.jsx
demo-ui/src/ApplicationDemo.jsx
demo-ui/src/Icon.jsx
demo-ui/src/SupportChat.jsx
demo-ui/src/ThemeToggle.jsx
demo-ui/src/application.css
demo-ui/src/assets/icons8-bot.gif
demo-ui/src/chat.css
demo-ui/src/main.jsx
demo-ui/src/sessionId.js
demo-ui/src/sessionId.test.mjs
demo-ui/src/styles.css
demo-ui/src/theme.css
demo-ui/vite.config.js
docker-compose.yml
docs/README.md
docs/architecture/INTEGRATION_PLAN.md
docs/architecture/Overview.md
docs/architecture/XHAIL.md
docs/guides/APPLICATION_DEMO.md
docs/guides/DCR_SKILL.md
docs/guides/DEPLOY.md
docs/handoffs/APPLICATION_DEMO_before_2026-11-13.md
docs/handoffs/ARCHITECTURE_before_2026-11-13.md
docs/handoffs/HANDOFF_2026-10-09_followup_eval.md
docs/handoffs/NEXT_SESSION.md
docs/handoffs/PROJECT_HISTORY_through_2026-10-12.md
docs/handoffs/UI_HANDOFF.md
docs/sources/Question_upmapping_chatbot.docx
docs/sources/SU_handicaptillaeg_FAQ_Expanded_Questions_Answers.md
docs/specs/00-brief.md
docs/specs/00-scope-and-roadmap.md
docs/specs/01-stop-wrong-answers.md
docs/specs/02-registry-and-trace-record.md
docs/specs/03-graph-split-outcome-table-dmn.md
docs/specs/README.md
evals/README.md
evals/__init__.py
evals/calibrate_thresholds.py
evals/cases/eval_composed_queries.json
evals/cases/eval_followup_queries.json
evals/cases/eval_queries.json
evals/cases/triage_labels.json
evals/diagnose_queries.py
evals/eval_composed.py
evals/eval_followups.py
evals/eval_live.py
evals/reports/calibration_report.md
evals/reports/composed_report.md
evals/reports/followup_report.md
evals/reports/live_outcome_report.md
evals/reports/live_table_report.md
evals/runs/eval_scores.json
evals/runs/eval_scores_query.json
evals/runs/followup_results.json
evals/runs/live_outcome_results.json
external_scripts/__init__.py
external_scripts/graph_parser.py
faq_search/answer_edits.json
faq_search/api.py
faq_search/build_faq_data.py
faq_search/data/faq_embeddings.npy
faq_search/data/faq_embeddings_meta.json
faq_search/data/faq_qa_records.json
faq_search/embed_faq_data.py
faq_search/requirements.txt
faq_search/retriever.py
prompts/README.md
prompts/base/README.md
prompts/base/decisions.txt
prompts/followup/pick.txt
prompts/followup/same.txt
prompts/forms/interpret.txt
prompts/forms/rank_system.txt
prompts/judges/README.md
prompts/panel/contextual.txt
prompts/panel/distress.txt
prompts/relevance/answers.txt
prompts/relevance/fits.txt
prompts/relevance/relevant.txt
prompts/relevance/same_topic.txt
prompts/relevance/tiers.txt
prompts/rewrite/panel.txt
prompts/rewrite/rewrite.txt
prompts/routing/route.txt
prompts/triage/contextual.txt
prompts/triage/meta.txt
prompts/triage/reply.txt
pyproject.toml
requirements-dev.txt
requirements.txt
scripts/check_repo.py
scripts/diagnose_application_entry.py
scripts/install_dcr_skill.py
static/demo/assets/icons8-bot-K3HB9ED8.gif
static/demo/assets/index-BOsD2B7s.js
static/demo/assets/index-D6oZJEFY.css
static/demo/index.html
static/script.js
templates/index.html
tests/__init__.py
tests/fixtures/clean_graph_event_ids_2026-10-10.json
tests/fixtures/followup_results_2026-10-09.json
tests/fixtures/trace_interaction_sample.jsonl
tests/test_application_demo.py
tests/test_application_faq.py
tests/test_dcr_choice_runtime.py
tests/test_dcr_simulation_api.py
tests/test_eval_followups.py
tests/test_eval_live.py
tests/test_faq_api.py
tests/test_faq_data.py
tests/test_faq_eval.py
tests/test_faq_mvp.py
tests/test_faq_retriever.py
tests/test_faq_scope.py
tests/test_mvp_presentation.py
tests/test_openchat.py
tests/test_outcome.py
tests/test_outcome_runtime.py
tests/test_outcome_table_graph.py
tests/test_panel_context.py
tests/test_pending_event_selection.py
tests/test_registry.py
tests/test_release_helpers.py
tests/test_retrieval_runtime.py
tests/test_static_information.py
tests/test_structured_application.py
tests/test_trace_hooks.py
tests/test_trace_integrity.py
tests/test_trace_reader.py
tests/test_turn_trace.py
tools/clean_graph/build_clean_graph.py
tools/clean_graph/determinations.json
tools/clean_graph/dmn_table.py
tools/clean_graph/field_help.json
tools/clean_graph/simulate_clean_graph.py
tools/clean_graph/split_steps.py
traces/README.md
xml graphs/Corona - ChatBot SOP.xml
xml graphs/DCR-JS Graph.xml
xml graphs/DMN chatbot - english.xml
xml graphs/Pension Toy Example.xml
xml graphs/SU (Handicap) visualization.html
xml graphs/SU (Handicap).xml
xml graphs/SU_FAQ_MVP.xml
xml graphs/SU_chatbot_FAQ_enriched_simple.xml
xml graphs/SU_chatbot_FAQ_part_with_static_chatbot (1).xml
xml graphs/SU_handicap_conversation.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Contact.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Conversational.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Demo.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Flat.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Lean.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Multi.xml
xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml
xml graphs/SU_handicaptillaeg_FAQ_MVP.xml
xml graphs/SU_handicaptillaeg_FAQ_Retrieval_Clean_NoEffect.xml
xml graphs/pension_toy.xml
```
