import unittest

import utility


def pending_event(event_id, event_type="", data_type=""):
    return {
        "id": event_id,
        "type": event_type,
        "dataType": data_type,
        "enabled": True,
        "pending": True,
        "executed": False,
        "IsProductive": False,
    }


class PendingEventSelectionTests(unittest.TestCase):
    def test_pending_subprocess_is_skipped_for_its_atomic_child(self):
        state = {
            "events": [
                pending_event("FAQ_Topic1", "Subprocess"),
                pending_event("FAQ_Menu_1", data_type="choice"),
            ]
        }

        self.assertEqual(utility.get_pending_event(state)["id"], "FAQ_Menu_1")

    def test_next_pending_event_skips_all_structural_container_types(self):
        state = {
            "events": [
                pending_event("CurrentQuestion", data_type="choice"),
                pending_event("Topic", "subprocess"),
                pending_event("Section", "NESTING"),
                pending_event("Application", "Form"),
                pending_event("Answer", data_type="label"),
            ]
        }

        result = utility.get_next_pending_event(state, "CurrentQuestion")
        self.assertEqual(result["id"], "Answer")


if __name__ == "__main__":
    unittest.main()
