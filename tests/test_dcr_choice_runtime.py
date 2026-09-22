import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import dcr_repository as repo
import questions

XML = '''<dcrgraph><specification><resources><events><event id="menu"><custom><eventData><dataType dataSetActivity="robot">choice</dataType></eventData></custom></event></events></resources></specification></dcrgraph>'''

class RuntimeChoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pathpatch = patch.object(repo, '__file__', str(Path(self.tmp.name)/'dcr_repository.py'))
        self.pathpatch.start(); self.addCleanup(self.pathpatch.stop)
        self.state = {'graph_xml': XML, 'graph_id': 'test', 'simulation_id': 'test', 'root_url': 'https://example.test/', 'api_key': 'test'}
        self.payload = {'events': [
            {'id': 'robot', 'executed': 'timestamp', 'value': '[[2,"Medical content"],[6,"Proceed to application"]]'},
            {'id': 'menu', 'dataType': 'choice', 'enabled': True, 'executed': None, 'choiceValues': ''}]}

    def test_resolves_robot_choices_and_preserves_raw_diagnostic(self):
        result = repo._prepare_event_payload(self.state, self.payload)
        self.assertEqual(result['events'][1]['choiceValues'], 'Medical content (2), Proceed to application (6)')
        from utility import get_events_enabled_not_executed
        self.assertEqual(get_events_enabled_not_executed(result)[0]['choiceValues'], result['events'][1]['choiceValues'])
        saved = json.loads(next(Path(self.tmp.name).glob('runtime_traces/*.json')).read_text())
        self.assertEqual(saved[-1]['raw_events'][1]['choiceValues'], '')
        self.assertNotIn('api_key', saved[-1])

    def test_robot_filters_full_repository_enum(self):
        self.payload['events'][1]['choiceValues'] = 'Server option (9)'
        self.assertEqual(repo._prepare_event_payload(self.state, self.payload)['events'][1]['choiceValues'], 'Medical content (2), Proceed to application (6)')

    def test_does_not_invent_choices_for_missing_robot_result(self):
        for value in ['undefined', 'not a list', '[1,2]', '[]']:
            self.payload['events'][0]['value'] = value
            self.assertEqual(repo._prepare_event_payload(self.state, self.payload)['events'][1]['choiceValues'], '')

    def test_undefined_information_falls_back_but_computed_values_remain(self):
        self.assertEqual(questions.get_information_text({'value':'undefined','displayValue':'undefined','description':'<p>Medical records</p>'}), 'Medical records')
        self.assertEqual(questions.get_information_text({'value':'Computed answer','description':'Fallback'}), 'Computed answer')

    @patch.object(repo._session, "post")
    def test_dynamic_selection_uses_explicit_value_api(self, post):
        post.return_value.status_code = 204
        self.assertTrue(repo.execute_event(self.state, "menu", "2", ""))
        self.assertTrue(post.call_args.args[0].endswith("/sims/test/events/menu"))
        self.assertIn('value="2"', post.call_args.kwargs["json"]["DataXML"])
        self.assertIn('type="int"', post.call_args.kwargs["json"]["DataXML"])

    def test_unexecuted_robot_is_not_used(self):
        self.payload['events'][0]['executed'] = None
        self.assertEqual(repo._prepare_event_payload(self.state, self.payload)['events'][1]['choiceValues'], '')

if __name__ == '__main__': unittest.main()
