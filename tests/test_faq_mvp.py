import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import app as webapp
import chatnlp


ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "xml graphs/SU_handicaptillaeg_FAQ_MVP.xml"
SELECTOR = "FAQ_SelectQuestion"
FORM = "Form0"


def event_payload(
    event_id,
    *,
    label="",
    description="",
    data_type="",
    choices="",
    included=True,
    enabled=True,
    pending=False,
    executed=False,
):
    return {
        "id": event_id,
        "label": label or event_id,
        "description": description,
        "dataType": data_type,
        "choiceValues": choices,
        "included": included,
        "enabled": enabled,
        "pending": pending,
        "executed": executed,
        "IsProductive": False,
    }


class FAQGraphStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ET.parse(GRAPH).getroot()
        cls.events = cls.root.findall("./specification/resources/events//event")
        cls.by_id = {event.get("id"): event for event in cls.events}
        cls.expressions = {
            expression.get("id"): expression.get("value")
            for expression in cls.root.findall(
                "./specification/resources/expressions/expression"
            )
        }

    def test_flat_graph_has_five_topics_and_global_catalogue(self):
        self.assertEqual(len(self.events), 25)
        self.assertFalse(any(e.get('type') for e in self.events))
        self.assertEqual(len([e for e in self.events if e.get('id').startswith('FAQ_Menu_')]), 5)
        self.assertEqual(len(self.by_id['FAQ_GlobalQuestion'].findall('./custom/eventData/dictionary/item')), 17)

    def test_home_is_initial_pending_and_all_events_reusable(self):
        included = {e.get('id') for e in self.root.findall('./runtime/marking/included/event')}
        pending = {e.get('id') for e in self.root.findall('./runtime/marking/pendingResponses/event')}
        self.assertEqual(included, set(self.by_id))
        self.assertEqual(pending, {'FAQ_Home'})
        self.assertFalse(self.root.findall('./specification/constraints/excludes/*'))

    def test_global_routes_clear_menus_and_return_to_topic(self):
        responses = self.root.findall('./specification/constraints/responses/response')
        cancellations = self.root.findall('./specification/constraints/coresponses/coresponse')
        for number in range(1,18):
            answer = f'FAQ_Answer_{number}'
            route = next(r for r in responses if r.get('sourceId') == 'FAQ_GlobalQuestion' and r.get('targetId') == answer)
            self.assertEqual(self.expressions[route.get('expressionId')], f'FAQ_GlobalQuestion = {number}')
            back = next(r for r in responses if r.get('sourceId') == answer)
            self.assertTrue(back.get('targetId').startswith('FAQ_Menu_'))
        self.assertEqual({r.get('targetId') for r in cancellations if r.get('sourceId') == 'FAQ_GlobalQuestion'},
                         {'FAQ_Home'} | {f'FAQ_Menu_{i}' for i in range(1,6)})

    def test_answer_text_and_sources_live_in_the_dcr_event(self):
        for number in range(1, 18):
            answer = self.by_id[f"FAQ_Answer_{number}"]
            description = answer.findtext("./custom/eventDescription") or ""
            purpose = answer.findtext("./custom/purpose") or ""
            self.assertTrue(description.startswith("<p>"))
            self.assertTrue(purpose)
            self.assertNotIn("undefined", description.lower())

    def test_cross_scope_relations_have_qualified_links(self):
        parents = {}

        def visit(parent, path=()):
            for event in parent.findall("event"):
                event_id = event.get("id")
                parents[event_id] = path
                visit(event, path + (event_id,))

        visit(self.root.find("./specification/resources/events"))
        for section in self.root.findall("./specification/constraints/*"):
            for relation in section:
                source = relation.get("sourceId")
                target = relation.get("targetId")
                if parents[source] != parents[target]:
                    self.assertTrue(relation.get("link"), (source, target))

    def test_api_marker_metadata(self):
        for id, event in self.by_id.items():
            groups = {g.text for g in event.findall('./custom/groups/group')}
            if id.startswith('FAQ_Answer_'):
                self.assertIn('FAQAnswer',groups)
            elif id.startswith('FAQ_Menu_'):
                self.assertIn('FAQTopicMenu',groups)
        self.assertIn('FallbackContact',{g.text for g in self.by_id['FAQ_Answer_17'].findall('./custom/groups/group')})


class FAQGenericRuntimeTests(unittest.TestCase):
    def tearDown(self):
        webapp.tab_sessions.clear()

    def test_initialization_uses_the_normal_pending_event_path(self):
        graph = ET.parse(GRAPH).getroot()
        selector = event_payload(
            SELECTOR,
            label="What would you like to ask?",
            data_type="choice",
            choices="Question one (1), Proceed to application (18)",
            pending=True,
        )
        session_id = "faq-generic-init"

        with (
            patch.object(webapp.dcrrepo, "get_graph", return_value=graph),
            patch.object(webapp.dcrrepo, "create_simulation", return_value=123),
            patch.object(
                webapp.dcrrepo, "get_events", return_value={"events": [selector]}
            ),
            patch.object(webapp.chatnlp, "create_chat", return_value=456),
            patch.object(webapp, "parse_graph_for_review"),
        ):
            response = webapp.app.test_client().post(
                "/init",
                json={"graph_id": "graph-driven-faq"},
                headers={"X-Session-ID": session_id},
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertNotIn("faq", data)
        self.assertEqual(data["event_id"], SELECTOR)
        self.assertEqual(data["response"], "What would you like to ask?")
        self.assertEqual(data["simulation_id"], 123)

    def test_reusable_executed_selector_is_still_sent_to_chat_nlp(self):
        selector = event_payload(
            SELECTOR,
            label="What would you like to ask?",
            data_type="choice",
            choices="Minimum documentation (7)",
            pending=True,
            executed="earlier",
        )
        state = {
            "graph_id": "graph",
            "chat_id": 1,
            "api_key": "key",
            "token": "token",
            "root_url": "https://example.invalid/",
        }
        with patch.object(
            chatnlp, "reply_to_chat", return_value={"reply": True, "value": "7"}
        ) as interpret:
            value, _, retry, _ = chatnlp.convert_msg_to_value(
                SELECTOR,
                {"events": [selector]},
                "What documents do I need?",
                state,
            )

        self.assertEqual(value, "7")
        self.assertFalse(retry)
        candidates = json.loads(interpret.call_args.args[2])
        self.assertEqual([event["id"] for event in candidates], [SELECTOR])

    def test_previously_executed_noncurrent_question_is_still_interpretable(self):
        current_menu = event_payload(
            "FAQ_Menu_2",
            label="Choose a question about impairment",
            data_type="choice",
            choices="What does permanent impairment mean? (4)",
            pending=True,
        )
        earlier_menu = event_payload(
            "FAQ_Menu_1",
            label="Choose a question about eligibility",
            data_type="choice",
            choices="Which education programmes qualify? (2)",
            pending=False,
            executed="earlier",
        )
        state = {
            "graph_id": "graph",
            "chat_id": 1,
            "api_key": "key",
            "token": "token",
            "root_url": "https://example.invalid/",
        }
        with patch.object(
            chatnlp,
            "reply_to_chat",
            return_value={
                "reply": True,
                "questionid": "FAQ_Menu_1",
                "value": "2",
            },
        ) as interpret:
            value, result, retry, _ = chatnlp.convert_msg_to_value(
                "FAQ_Menu_2",
                {"events": [current_menu, earlier_menu]},
                "Which education programmes qualify?",
                state,
            )

        self.assertEqual(value, "2")
        self.assertFalse(retry)
        self.assertEqual(result["questionid"], "FAQ_Menu_1")
        candidates = json.loads(interpret.call_args.args[2])
        self.assertEqual(
            {event["id"] for event in candidates},
            {"FAQ_Menu_1", "FAQ_Menu_2"},
        )

    def test_free_text_choice_is_confirmed_before_dcr_execution(self):
        choices = (
            "What is the minimum medical documentation? (7), "
            "Proceed to application (18)"
        )
        selector = event_payload(
            SELECTOR,
            label="What would you like to ask?",
            data_type="choice",
            choices=choices,
            pending=True,
        )
        session_id = "faq-confirm"
        webapp.tab_sessions[session_id] = {
            "api_key": "key",
            "token": "token",
            "root_url": "https://example.invalid/",
            "graph_id": "graph",
            "simulation_id": 123,
            "simulation_state": {"events": [selector]},
            "event_id": SELECTOR,
            "question": "What would you like to ask?",
            "graph_language": "en",
            "tentative": 1,
        }

        with (
            patch.object(
                webapp.chatnlp,
                "convert_msg_to_value",
                return_value=(
                    "7",
                    {"reply": True, "questionid": SELECTOR, "value": "7"},
                    False,
                    "",
                ),
            ),
            patch.object(webapp.dcrrepo, "execute_event") as execute,
        ):
            response = webapp.app.test_client().post(
                "/chat",
                json={"message": "What documents are minimally needed?"},
                headers={"X-Session-ID": session_id},
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["confirm"])
        self.assertEqual(
            data["qvalue"], "What is the minimum medical documentation?"
        )
        execute.assert_not_called()

    def test_free_text_match_uses_interpreter_event_for_confirmation_and_execution(self):
        home = event_payload(
            "FAQ_Home",
            label="What would you like help with?",
            data_type="choice",
            choices="Impairment and ability to work (2)",
            pending=True,
        )
        global_question = event_payload(
            "FAQ_GlobalQuestion",
            label="What would you like to ask?",
            data_type="choice",
            choices="Which education programmes qualify? (2)",
            pending=False,
        )
        answer = event_payload(
            "FAQ_Answer_2",
            label="Which education programmes qualify?",
            description="The qualifying programmes are described here.",
            data_type="label",
            pending=True,
        )
        session_id = "faq-global-free-text"
        webapp.tab_sessions[session_id] = {
            "api_key": "key",
            "token": "token",
            "root_url": "https://example.invalid/",
            "graph_id": "graph",
            "simulation_id": 123,
            "simulation_state": {"events": [home, global_question]},
            "event_id": "FAQ_Home",
            "question": "What would you like help with?",
            "graph_language": "en",
            "tentative": 1,
            "inferred_replies": [],
            "execution_history": [],
        }

        client = webapp.app.test_client()
        with (
            patch.object(
                webapp.chatnlp,
                "convert_msg_to_value",
                return_value=(
                    "2",
                    {
                        "reply": True,
                        "questionid": "FAQ_GlobalQuestion",
                        "value": "2",
                    },
                    False,
                    "",
                ),
            ),
            patch.object(webapp.dcrrepo, "execute_event", return_value=True) as execute,
            patch.object(
                webapp.dcrrepo,
                "get_events",
                return_value={
                    "events": [
                        home | {"pending": False},
                        global_question | {"pending": False},
                        answer,
                    ]
                },
            ),
        ):
            suggestion = client.post(
                "/chat",
                json={"message": "Which education programmes qualify?"},
                headers={"X-Session-ID": session_id},
            )

            self.assertEqual(suggestion.status_code, 200)
            suggestion_data = suggestion.get_json()
            self.assertTrue(suggestion_data["confirm"])
            self.assertEqual(suggestion_data["event_id"], "FAQ_GlobalQuestion")
            self.assertEqual(
                suggestion_data["qvalue"], "Which education programmes qualify?"
            )
            execute.assert_not_called()

            confirmation = client.post(
                "/chat",
                json={
                    "message": "Which education programmes qualify?",
                    "value": "2",
                },
                headers={"X-Session-ID": session_id},
            )

        self.assertEqual(confirmation.status_code, 200)
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[1:3], ("FAQ_GlobalQuestion", "2"))
        confirmation_data = confirmation.get_json()
        self.assertEqual(confirmation_data["event_id"], "FAQ_Answer_2")
        self.assertEqual(
            confirmation_data["response"], "The qualifying programmes are described here."
        )

    def test_confirmed_choice_uses_dcr_answer_without_topic_or_question_repeat(self):
        choices = "What is the minimum medical documentation? (7)"
        selector = event_payload(
            SELECTOR,
            label="What would you like to ask?",
            data_type="choice",
            choices=choices,
            pending=True,
        )
        answer_text = (
            "For an application submitted on or after 1 July 2025, attach "
            "medical records for every impairment.\n\nSources\nGuideline sections 4.1-4.4."
        )
        answer = event_payload(
            "FAQ_Answer_7",
            label="What is the minimum medical documentation?",
            description=answer_text,
            data_type="label",
            pending=True,
            executed=False,
        )
        session_id = "faq-answer"
        webapp.tab_sessions[session_id] = {
            "api_key": "key",
            "token": "token",
            "root_url": "https://example.invalid/",
            "graph_id": "graph",
            "simulation_id": 123,
            "simulation_state": {"events": [selector]},
            "event_id": SELECTOR,
            "question": "What would you like to ask?",
            "graph_language": "en",
            "tentative": 1,
            "inferred_replies": [],
            "execution_history": [],
        }

        with (
            patch.object(webapp.dcrrepo, "execute_event", return_value=True),
            patch.object(
                webapp.dcrrepo,
                "get_events",
                return_value={"events": [selector | {"pending": False}, answer]},
            ),
        ):
            response = webapp.app.test_client().post(
                "/chat",
                json={
                    "message": "What is the minimum medical documentation?",
                    "value": "7",
                },
                headers={"X-Session-ID": session_id},
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["information"])
        self.assertEqual(data["event_id"], "FAQ_Answer_7")
        self.assertEqual(data["response"], answer_text)
        self.assertNotIn("topic", data)
        self.assertNotEqual(
            data["response"], "What is the minimum medical documentation?"
        )


if __name__ == "__main__":
    unittest.main()
