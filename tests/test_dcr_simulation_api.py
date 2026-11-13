"""dcr_repository uses only the /simulation/ engine and sends each event's role."""
import unittest
from unittest.mock import Mock, patch

import dcrai.dcr.dcr_repository as repo

ROOT = 'https://example.test/'


def state():
    return {'root_url': ROOT, 'graph_id': 2013928, 'simulation_id': 77, 'api_key': 'k'}


EVENTS = {'events': [
    {'id': 'FAQ_UserQuestion', 'roles': 'Chatbot'},
    {'id': 'FAQ_Retrieve', 'roles': 'Robot, Admin'},
    {'id': 'Form0:Email', 'roles': ''},
]}


class SimulationApiTests(unittest.TestCase):
    def test_create_uses_simulation_route(self):
        s = state()
        resp = Mock(status_code=201, headers={'X-DCR-simulation-ID': '123'})
        with patch.object(repo._session, 'post', return_value=resp) as post:
            self.assertEqual(repo.create_simulation(s), 123)
        self.assertEqual(post.call_args.args[0], f'{ROOT}api/graphs/2013928/simulation')

    def test_create_failure_returns_zero(self):
        with patch.object(repo._session, 'post', return_value=Mock(status_code=409, text='err', headers={})):
            self.assertEqual(repo.create_simulation(state()), 0)

    def test_reading_events_uses_simulation_route_and_caches_roles(self):
        s = state()
        resp = Mock(status_code=200); resp.json.return_value = EVENTS
        with patch.object(repo._session, 'get', return_value=resp) as get:
            repo.get_raw_events(s)
        self.assertEqual(get.call_args.args[0], f'{ROOT}api/graphs/2013928/simulation/77/event')
        self.assertEqual(s['event_roles'], {'FAQ_UserQuestion': 'Chatbot', 'FAQ_Retrieve': 'Robot', 'Form0:Email': ''})

    def test_execute_sends_event_role(self):
        s = state(); s['event_roles'] = {'FAQ_UserQuestion': 'Chatbot'}
        with patch.object(repo._session, 'post', return_value=Mock(status_code=204)) as post:
            self.assertTrue(repo.execute_raw_event(s, 'FAQ_UserQuestion', 'q?'))
        self.assertEqual(post.call_args.args[0], f'{ROOT}api/graphs/2013928/simulation/77/event')
        self.assertEqual(post.call_args.kwargs['json'],
                         {'eventId': 'FAQ_UserQuestion', 'eventValue': 'q?', 'comment': '', 'isNull': False, 'role': 'Chatbot'})

    def test_execute_without_role_omits_it(self):
        s = state(); s['event_roles'] = {'Form0:Email': ''}
        with patch.object(repo._session, 'post', return_value=Mock(status_code=204)) as post:
            repo.execute_raw_event(s, 'Form0:Email', 'a@b.dk')
        self.assertNotIn('role', post.call_args.kwargs['json'])

    def test_explicit_role_wins(self):
        s = state(); s['event_roles'] = {'FAQ_Retrieve': 'Robot'}
        with patch.object(repo._session, 'post', return_value=Mock(status_code=204)) as post:
            repo.execute_raw_event(s, 'FAQ_Retrieve', '', role='Other')
        self.assertEqual(post.call_args.kwargs['json']['role'], 'Other')

    def test_failed_execute_returns_false(self):
        with patch.object(repo._session, 'post', return_value=Mock(status_code=500, text='Value cannot be null.')):
            self.assertFalse(repo.execute_raw_event(state(), 'FAQ_UserQuestion', 'q'))

    def test_new_simulation_clears_role_cache(self):
        s = state(); s['event_roles'] = {'x': 'y'}
        with patch.object(repo._session, 'post', return_value=Mock(status_code=201, headers={'X-DCR-simulation-ID': '5'})):
            repo.create_simulation(s)
        self.assertNotIn('event_roles', s)

    def test_no_legacy_sims_route_in_module(self):
        import inspect
        source = inspect.getsource(repo)
        self.assertNotIn("/sims/{", source)
        self.assertNotIn("}/sims", source)


if __name__ == '__main__':
    unittest.main()
