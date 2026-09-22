"""Tests verifying the clean, structured DCR XML model and tag-decoupled runtime."""
import os
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from unittest.mock import patch

import application_runtime as runtime
import dcr_repository as repo


class StructuredApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.xml_path = Path(__file__).resolve().parents[1] / 'xml graphs/SU_handicaptillaeg_FAQ_Application_Structured.xml'
        with open(cls.xml_path, 'r', encoding='utf-8') as f:
            cls.raw_xml = f.read()
        cls.root = ET.fromstring(cls.raw_xml)

    def test_subprocess_container_exists(self):
        """Form0 should be a true DCR subprocess container enclosing application events."""
        subprocess_event = self.root.find(".//events//event[@id='Form0']")
        self.assertIsNotNone(subprocess_event, "Form0 event must exist")
        self.assertEqual(subprocess_event.get('type'), 'subprocess', "Form0 must have type='subprocess'")
        
        # Verify children events are nested inside Form0
        child_events = subprocess_event.findall("./event")
        self.assertGreaterEqual(len(child_events), 15, "Form0 subprocess must contain the application events")
        child_ids = [e.get('id') for e in child_events]
        self.assertIn("Form0:Email", child_ids)
        self.assertIn("Form0:A1_1", child_ids)
        self.assertIn("Form0:A2", child_ids)
        self.assertIn("Form0:A10", child_ids)

    def test_brittle_tags_removed_from_xml(self):
        """No brittle tags (ApplicationField, ApplicationStart, ApplicationMulti, ApplicationDemoFile) should exist."""
        all_groups = [g.text for g in self.root.findall(".//groups/group") if g.text]
        for tag in all_groups:
            self.assertNotEqual(tag, "ApplicationField", "ApplicationField tag should be removed")
            self.assertNotEqual(tag, "ApplicationMulti", "ApplicationMulti tag should be removed")
            self.assertNotEqual(tag, "ApplicationDemoFile", "ApplicationDemoFile tag should be removed")
            self.assertFalse(tag.startswith("ApplicationStart:"), f"Routing tag {tag} should be removed")

    def test_native_multiple_on_functional_impairment_choice(self):
        """A2 should have multiple='true' directly on dataType."""
        a2_event = self.root.find(".//events//event[@id='Form0:A2']")
        self.assertIsNotNone(a2_event)
        datatype = a2_event.find("./custom/eventData/dataType")
        self.assertIsNotNone(datatype)
        self.assertEqual(datatype.get("multiple"), "true")
        self.assertEqual(datatype.text, "choice")

    def test_file_datatype_has_no_multiple_in_xml(self):
        """In DCR standard, file data type has no multiple attribute (only choice has it)."""
        a11_event = self.root.find(".//events//event[@id='Form0:A11']")
        self.assertIsNotNone(a11_event)
        datatype = a11_event.find("./custom/eventData/dataType")
        self.assertIsNotNone(datatype)
        self.assertIsNone(datatype.get("multiple"))
        self.assertEqual(datatype.text, "file")

    def test_entry_condition_from_faq_home_to_email(self):
        """There should be a condition linking FAQ_Home to Form0:Email with initial inclusion."""
        condition = self.root.find(".//conditions/condition[@sourceId='FAQ_Home'][@targetId='Form0:Email']")
        self.assertIsNotNone(condition, "Entry condition from FAQ_Home to Form0:Email must exist")
        
        # Form0:Email should be in initially included marking
        included_email = self.root.find(".//runtime/marking/included/event[@id='Form0:Email']")
        self.assertIsNotNone(included_email, "Form0:Email must be initially included to receive obligation")

    def test_dcr_repository_enriches_multiple_from_xml(self):
        """_enrich_events_from_xml should populate multiple='true' from XML without tags."""
        state = {"graph_xml": self.raw_xml}
        raw_payload = {
            "events": [
                {"id": "Form0:A2", "dataType": "choice", "enabled": True, "included": True},
                {"id": "Form0:Email", "dataType": "email", "enabled": True, "included": True}
            ]
        }
        enriched = repo._enrich_events_from_xml(state, raw_payload)
        a2 = next(e for e in enriched["events"] if e["id"] == "Form0:A2")
        email = next(e for e in enriched["events"] if e["id"] == "Form0:Email")
        self.assertEqual(a2.get("multiple"), "true")
        self.assertIsNone(email.get("multiple"))

    def test_is_application_event_recognizes_form0_prefix_without_tags(self):
        """Untagged Form0 events are recognized as application events."""
        event_without_tags = {"id": "Form0:A1_1", "label": "Start date", "groups": ""}
        self.assertTrue(runtime.is_application_event(event_without_tags))
        
        # Subprocess container itself is not a field event
        container_event = {"id": "Form0", "label": "Form0", "groups": ""}
        self.assertFalse(runtime.is_application_event(container_event))

        # Unrelated event
        faq_event = {"id": "FAQ_Home", "label": "FAQ Home", "groups": "FAQHome"}
        self.assertFalse(runtime.is_application_event(faq_event))

    def test_describe_reads_multiple_and_file_cleanly(self):
        """describe() supports native multiple and standard file datatype without tags."""
        choice_mult = {
            "id": "Form0:A2",
            "label": "Functional impairments",
            "dataType": "choice",
            "multiple": "true",
            "choiceValues": "Vision (1), Hearing (2)",
            "groups": ""
        }
        described = runtime.describe(choice_mult)
        self.assertTrue(described.get("multiple"))
        self.assertEqual(described["type"], "choice")
        self.assertEqual(len(described["options"]), 2)

        file_ev = {
            "id": "Form0:A5",
            "label": "Medical statement",
            "dataType": "file",
            "groups": ""
        }
        described_file = runtime.describe(file_ev)
        self.assertEqual(described_file["type"], "file")
        self.assertFalse(described_file.get("multiple", False))
        self.assertEqual(described_file["max_files"], 1)
        self.assertIn(".pdf", described_file["extensions"])

        a11_ev = {
            "id": "Form0:A11",
            "label": "Medical records",
            "dataType": "file",
            "groups": ""
        }
        described_a11 = runtime.describe(a11_ev)
        self.assertEqual(described_a11["type"], "file")
        self.assertTrue(described_a11.get("multiple"))
        self.assertEqual(described_a11["max_files"], 8)
        self.assertIn(".pdf", described_a11["extensions"])

    def test_dynamic_start_without_application_start_tag(self):
        """start() dynamically finds the application choice on FAQ_Home when no tag is present."""
        fake_payload = {
            "events": [
                {
                    "id": "FAQ_Home",
                    "label": "FAQ Home",
                    "dataType": "choice",
                    "enabled": True,
                    "included": True,
                    "groups": "FAQHome",
                    "choiceValues": "Eligibility (1), Application questions (2), Proceed to application (6)"
                },
                {
                    "id": "Form0:Email",
                    "label": "Email",
                    "dataType": "email",
                    "enabled": True,
                    "included": True,
                    "pending": True,
                    "groups": ""
                }
            ]
        }
        state = {"application_answers": [], "graph_id": "123", "simulation_id": "456"}
        with patch.object(repo, "get_raw_events", return_value=fake_payload), \
             patch.object(repo, "execute_raw_event", return_value=True) as mock_exec:
            res = runtime.start(state)
            mock_exec.assert_called_once_with(state, "FAQ_Home", "6")
            self.assertEqual(res["status"], "question")
    def test_sole_unanswered_fallback_when_pending_is_empty(self):
        """When DCR drops pending obligations, answered events are ignored and the next unexecuted field is selected."""
        fake_payload = {
            "events": [
                {
                    "id": "Form0:Email",
                    "label": "Email",
                    "dataType": "email",
                    "enabled": True,
                    "included": True,
                    "pending": False,
                    "executed": "2026-09-16T02:32:18.4826619+02:00",
                    "groups": ""
                },
                {
                    "id": "Form0:Phone",
                    "label": "Phone",
                    "dataType": "text",
                    "enabled": True,
                    "included": True,
                    "pending": False,
                    "executed": None,
                    "groups": ""
                }
            ]
        }
        state = {"application_answers": [], "graph_id": "2012794", "simulation_id": "2101950"}
        res = runtime.view(state, fake_payload)
        self.assertEqual(res["status"], "question")
    def test_edit_replays_simulation_and_selects_next_step(self):
        """Editing an earlier answer creates a fresh simulation and replays prior answers."""
        state = {
            "graph_id": "2012794",
            "simulation_id": 100,
            "application_answers": [
                {"id": "Form0:Email", "label": "Email", "value": "test@example.com", "raw": "test@example.com"},
                {"id": "Form0:Phone", "label": "Phone", "value": "+45 11 22 33 44", "raw": "+45 11 22 33 44"},
                {"id": "Form0:A1_1", "label": "Start date", "value": "2026-10-01", "raw": "2026-10-01"}
            ]
        }
        # Payload when editing Phone:
        payload_after_replay = {
            "events": [
                {"id": "FAQ_Home", "label": "Home", "dataType": "choice", "enabled": True, "included": True, "groups": "FAQHome", "choiceValues": "Proceed to application (6)"},
                {"id": "Form0:Email", "label": "Email", "dataType": "email", "enabled": True, "included": True, "groups": "", "executed": "2026-09-16..."},
                {"id": "Form0:Phone", "label": "Phone", "dataType": "text", "enabled": True, "included": True, "groups": "", "executed": "2026-09-16..."},
                {"id": "Form0:A1_1", "label": "Start date", "dataType": "date", "enabled": True, "included": True, "groups": "", "executed": None}
            ]
        }
        with patch.object(repo, "create_simulation", return_value=101), \
             patch.object(repo, "get_raw_events", return_value=payload_after_replay), \
             patch.object(repo, "execute_raw_event", return_value=True) as mock_exec:
            res = runtime.edit(state, {"field_id": "Form0:Phone", "value": "+45 99 88 77 66"})
            self.assertEqual(state["simulation_id"], 101, "Simulation ID must be updated to new simulation")
            self.assertEqual(res["status"], "question")
            self.assertEqual(res["field"]["id"], "Form0:A1_1")
            self.assertEqual(len(state["application_answers"]), 2)
            self.assertEqual(state["application_answers"][1]["value"], "+45 99 88 77 66")


if __name__ == '__main__':
    unittest.main()
