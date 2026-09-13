"""Tests for static DCR information events and their Continue flow."""

import unittest
from unittest.mock import patch

import questions


class InformationEventTests(unittest.TestCase):
    def test_runtime_description_is_rendered_as_safe_text(self):
        event = {
            "id": "A20",
            "dataType": None,
            "description": "<p>Medical documentation must be current.</p><ul><li>Diagnosis</li></ul>",
        }

        self.assertTrue(questions.is_information_event(event))
        self.assertEqual(
            questions.get_information_text(event),
            "Medical documentation must be current.\n\n- Diagnosis",
        )

    def test_labels_are_information_events_but_choices_are_not(self):
        self.assertTrue(questions.is_information_event({"id": "A31", "dataType": "label"}))
        self.assertFalse(questions.is_information_event({"id": "Welcome", "dataType": "choice"}))


class ContinueInformationRouteTests(unittest.TestCase):
    session_id = "static-information-test"

    @classmethod
    def setUpClass(cls):
        import app as chatbot_app
        cls.chatbot_app = chatbot_app

    def setUp(self):
        self.chatbot_app.app.config.update(TESTING=True)
        self.chatbot_app.tab_sessions.clear()
        self.before = {
            "events": [{
                "id": "A20", "label": "Info dump", "dataType": None,
                "description": "<p>Documentation information</p>",
                "enabled": True, "pending": True, "executed": None,
            }]
        }
        self.after = {
            "events": [{
                "id": "A27", "label": "Do you want to learn more?",
                "dataType": "choice", "choiceValues": "Yes (1), No (0)",
                "enabled": True, "pending": True, "executed": None,
            }]
        }
        self.chatbot_app.tab_sessions[self.session_id] = {
            "api_key": "test-key",
            "token": "test-token",
            "root_url": "https://example.test/",
            "graph_id": 2012526,
            "simulation_id": 1,
            "event_id": "A20",
            "execution_history": [],
        }

    @patch("app.dcrrepo.execute_event", return_value=True)
    @patch("app.dcrrepo.get_events")
    def test_continue_executes_information_then_returns_next_question(self, get_events, execute_event):
        get_events.side_effect = [self.before, self.after, self.after]

        response = self.chatbot_app.app.test_client().post(
            "/continue",
            headers={"X-Session-ID": self.session_id},
            json={"event_id": "A20"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["event_id"], "A27")
        self.assertEqual(response.get_json()["response"], "Do you want to learn more?")
        execute_event.assert_called_once_with(
            self.chatbot_app.tab_sessions[self.session_id], "A20", "", ""
        )

    @patch("app.dcrrepo.execute_event")
    def test_stale_continue_does_not_execute(self, execute_event):
        response = self.chatbot_app.app.test_client().post(
            "/continue",
            headers={"X-Session-ID": self.session_id},
            json={"event_id": "A11"},
        )

        self.assertEqual(response.status_code, 409)
        execute_event.assert_not_called()

    @patch("app.dcrrepo.execute_event", return_value=False)
    @patch("app.dcrrepo.get_events")
    def test_failed_continue_does_not_advance(self, get_events, execute_event):
        get_events.return_value = self.before

        response = self.chatbot_app.app.test_client().post(
            "/continue",
            headers={"X-Session-ID": self.session_id},
            json={"event_id": "A20"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.chatbot_app.tab_sessions[self.session_id]["event_id"], "A20")
        execute_event.assert_called_once()


if __name__ == "__main__":
    unittest.main()
