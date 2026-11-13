"""Registry: settings table, version id, snapshot file, readers (spec 02, T1 and T2). No model call."""
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dcrai import paths, prompts, registry
from dcrai.llm import openchat
import dcrai.llm.retrieval_llm as llm

ROOT = Path(paths.ROOT)

# Written out on purpose: the defaults must equal the values that were hard-coded before the registry (spec 02, R3).
EXPECTED_DEFAULTS = {
    'DECISIONS_ENABLED': False, 'DECISIONS_MODEL': 'gpt-6-luna', 'DECISIONS_TIMEOUT_SECONDS': 10.0,
    'DECISIONS_TRIAGE_MIN': 0.6, 'DECISIONS_REPLY_MIN': 0.6, 'DECISIONS_CONTEXT_MIN': 0.7,
    'DECISIONS_RELEVANT_MIN': 0.5, 'DECISIONS_FOLLOWUP_MIN': 0.7, 'DECISIONS_DISTRESS_MIN': 0.7,
    'FAQ_MATCH_MODEL': 'gpt-4.1-mini-2025-04-14', 'FAQ_SINGLE_THRESHOLD': 0.80, 'FAQ_MIN_THRESHOLD': 0.50,
    'FAQ_MARGIN_THRESHOLD': 0.12, 'FAQ_MAX_CANDIDATES': 3, 'FAQ_MATCH_TIMEOUT_SECONDS': 15.0,
    'USE_LOCAL_RETRIEVER': True, 'FAQ_QUERY_PROMPT': '',
    'CONFIRM_LONE_SURVIVOR': True, 'RELEVANCE_TIERS': True, 'PANEL_FALLBACK_REWRITE': False,
    'DECISIONS_ANSWERS_MIN': 0.5, 'DECISIONS_TOPIC_MIN': 0.5,
    'BASE_LAYER_DECISIONS': False, 'PANEL_CONTEXT_IN_DCR': True,
    'OUTCOME_MODE': 'code', 'FOLLOWUP_SURFACE': 'panel', 'PANEL_TRIAGE': True,
    'PROMPT_TTL': 1800, 'MISSES_BEFORE_HANDOVER': 2, 'ANSWER_PREVIEW_CHARS': 300,
    'INTERACTION_LOG': '1', 'INTERACTION_LOG_DIR': 'traces/interactions', 'RUNTIME_TRACE_DIR': 'traces/runtime',
    'APPLICATION_ENABLED_FALLBACK': False, 'FAQ_API_PORT': 8090, 'ROOT_URL': None,
}
SECRETS = ['FAQ_API_EXTRA_KEYS', 'FAQ_API_KEY', 'OPENAI_API_KEY', 'API_KEY', 'TOKEN']


def clean_env(**extra):
    """An environment with no registered setting set, plus `extra`."""
    env = {k: v for k, v in os.environ.items() if k not in registry.SETTINGS}
    env.update(extra)
    return patch.dict(os.environ, env, clear=True)


class RegistryVersionTests(unittest.TestCase):
    def setUp(self):
        prompts.get.cache_clear()
        self.addCleanup(prompts.get.cache_clear)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = clean_env()
        env.start()
        self.addCleanup(env.stop)

    def test_version_is_stable_and_twelve_hex(self):
        first = registry.version()
        self.assertEqual(first, registry.version())
        self.assertRegex(first, r'^[0-9a-f]{12}$')

    def test_version_changes_with_a_prompt_file(self):
        copy = self.tmp / 'prompts'
        shutil.copytree(ROOT / 'prompts', copy)
        with patch.object(paths, 'PROMPTS', copy):
            prompts.get.cache_clear()
            before = registry.version()
            target = copy / 'triage' / 'meta.txt'
            original = target.read_text(encoding='utf-8')
            target.write_text(original + ' extra', encoding='utf-8')
            prompts.get.cache_clear()
            self.assertNotEqual(before, registry.version())
            target.write_text(original, encoding='utf-8')
            prompts.get.cache_clear()
            self.assertEqual(before, registry.version())

    def test_version_changes_with_a_threshold_and_ignores_float_spelling(self):
        unset = registry.version()
        with patch.dict(os.environ, {'DECISIONS_RELEVANT_MIN': '0.6'}):
            short = registry.version()
        with patch.dict(os.environ, {'DECISIONS_RELEVANT_MIN': '0.60'}):
            long = registry.version()
        self.assertEqual(short, long)
        self.assertNotEqual(short, unset)

    def test_version_changes_with_a_flag_a_model_and_a_retrieval_setting(self):
        unset = registry.version()
        for name, value in [('CONFIRM_LONE_SURVIVOR', '0'), ('DECISIONS_MODEL', 'other-model'),
                            ('FAQ_QUERY_PROMPT', 'Query:')]:
            with self.subTest(name), patch.dict(os.environ, {name: value}):
                self.assertNotEqual(unset, registry.version())

    def test_version_ignores_ops_and_secrets(self):
        unset = registry.version()
        env = {'INTERACTION_LOG_DIR': '/elsewhere', 'OPENAI_API_KEY': 'sk-test-123', 'FAQ_API_PORT': '9999',
               'ROOT_URL': 'https://example.test/', 'API_KEY': 'k', 'TOKEN': 't', 'INTERACTION_LOG': '0'}
        with patch.dict(os.environ, env):
            self.assertEqual(unset, registry.version())

    def test_version_changes_with_faq_data(self):
        data = self.tmp / 'data'
        data.mkdir()
        records, meta = data / 'faq_qa_records.json', data / 'faq_embeddings_meta.json'
        records.write_text('[1]', encoding='utf-8')
        meta.write_text('{"a": 1}', encoding='utf-8')
        with patch.object(paths, 'FAQ_DATA', data):
            base = registry.version()
            for n, target in enumerate([records, meta], start=1):
                with self.subTest(target.name):
                    target.write_bytes(target.read_bytes().replace(b'1', b'2'))
                    os.utime(target, ns=(n * 10**9, n * 10**9))   # same size: force a new (mtime, size) key
                    changed = registry.version()
                    self.assertNotEqual(base, changed)
                    base = changed

    def test_missing_data_file_is_a_stable_marker_not_an_error(self):
        with patch.object(paths, 'FAQ_DATA', self.tmp / 'nowhere'):
            snap = registry.snapshot()
        self.assertEqual(snap['data'], {'faq_records': 'missing', 'faq_embeddings_meta': 'missing'})


class RegistryReadTests(unittest.TestCase):
    def setUp(self):
        env = clean_env()
        env.start()
        self.addCleanup(env.stop)

    def test_every_env_name_in_product_code_is_registered(self):
        patterns = [r'getenv\(\s*[\'"]([A-Z][A-Z0-9_]+)[\'"]', r'environ\[\s*[\'"]([A-Z][A-Z0-9_]+)[\'"]\s*\]',
                    r'environ\.get\(\s*[\'"]([A-Z][A-Z0-9_]+)[\'"]', r'_threshold\(\s*[\'"]([A-Z][A-Z0-9_]+)[\'"]',
                    r'registry\.(?:get|flag)\(\s*[\'"]([A-Z][A-Z0-9_]+)[\'"]', r'\bflag\(\s*[\'"]([A-Z][A-Z0-9_]+)[\'"]']
        files = [ROOT / 'app.py'] + sorted((ROOT / 'dcrai').rglob('*.py')) + sorted((ROOT / 'faq_search').rglob('*.py'))
        found = {}
        for path in files:
            text = path.read_text(encoding='utf-8')
            for pattern in patterns:
                for name in re.findall(pattern, text):
                    found.setdefault(name, set()).add(path.relative_to(ROOT).as_posix())
        self.assertTrue(found, 'the scan found nothing; the patterns are broken')
        missing = {n: sorted(f) for n, f in found.items() if n not in registry.SETTINGS}
        self.assertEqual(missing, {}, 'environment names read but not in dcrai/registry.py SETTINGS')

    def test_defaults_equal_previous_values(self):
        for name, expected in EXPECTED_DEFAULTS.items():
            with self.subTest(name):
                self.assertEqual(registry.get(name), expected)
                self.assertIs(type(registry.get(name)), type(expected))

    def test_table_covers_the_expected_names_and_classes(self):
        self.assertEqual(set(registry.SETTINGS), set(EXPECTED_DEFAULTS) | set(SECRETS))
        for name in SECRETS:
            self.assertEqual(registry.SETTINGS[name].cls, 'secret')
        for setting in registry.SETTINGS.values():
            self.assertIn(setting.cls, registry.VERSIONED | {'ops', 'secret'})
            self.assertTrue(setting.description)

    def test_unparsable_value_falls_back_with_a_warning(self):
        with patch.dict(os.environ, {'DECISIONS_CONTEXT_MIN': 'abc'}):
            with self.assertLogs('dcrai.registry', level=logging.WARNING) as logged:
                self.assertEqual(registry.get('DECISIONS_CONTEXT_MIN'), 0.7)
        self.assertEqual(len(logged.records), 1)
        with patch.dict(os.environ, {'FAQ_MAX_CANDIDATES': 'two'}):
            with self.assertLogs('dcrai.registry', level=logging.WARNING):
                self.assertEqual(registry.get('FAQ_MAX_CANDIDATES'), 3)

    def test_settings_are_read_at_call_time(self):
        self.assertEqual(registry.get('DECISIONS_RELEVANT_MIN'), 0.5)
        with patch.dict(os.environ, {'DECISIONS_RELEVANT_MIN': '0.8'}):
            self.assertEqual(registry.get('DECISIONS_RELEVANT_MIN'), 0.8)
        self.assertEqual(registry.get('DECISIONS_RELEVANT_MIN'), 0.5)

    def test_flags_are_true_only_for_the_string_one(self):
        for raw, expected in [('1', True), ('0', False), ('true', False), ('', False), (' 1', False)]:
            with self.subTest(raw), patch.dict(os.environ, {'DECISIONS_ENABLED': raw}):
                self.assertIs(registry.flag('DECISIONS_ENABLED'), expected)
        with patch.dict(os.environ, {'USE_LOCAL_RETRIEVER': ''}):
            self.assertFalse(registry.flag('USE_LOCAL_RETRIEVER'))   # as `os.getenv(..., '1') == '1'` was
        with self.assertRaises(TypeError):
            registry.flag('DECISIONS_MODEL')

    def test_unknown_name_raises_key_error(self):
        with self.assertRaises(KeyError):
            registry.get('NOPE')
        with self.assertRaises(KeyError):
            registry.flag('NOPE')

    def test_constants_have_no_environment_override(self):
        with patch.dict(os.environ, {'PROMPT_TTL': '5', 'MISSES_BEFORE_HANDOVER': '9', 'ANSWER_PREVIEW_CHARS': '1'}):
            self.assertEqual((registry.get('PROMPT_TTL'), registry.get('MISSES_BEFORE_HANDOVER'),
                              registry.get('ANSWER_PREVIEW_CHARS')), (1800, 2, 300))

    def test_secrets_are_not_readable_through_the_registry(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test-123'}):
            with self.assertRaises(KeyError):
                registry.get('OPENAI_API_KEY')

    def test_threshold_and_decisions_enabled_shims(self):
        self.assertEqual(llm._threshold('DECISIONS_REPLY_MIN', '9'), 0.6)
        self.assertFalse(llm.decisions_enabled())
        with patch.dict(os.environ, {'DECISIONS_ENABLED': '1', 'DECISIONS_REPLY_MIN': '0.9'}):
            self.assertTrue(llm.decisions_enabled())
            self.assertEqual(llm._threshold('DECISIONS_REPLY_MIN', '0.6'), 0.9)
        with patch.dict(os.environ, {'DECISIONS_REPLY_MIN': 'bad'}):
            self.assertEqual(llm._threshold('DECISIONS_REPLY_MIN', '0.6'), 0.6)

    def test_constants_in_modules_equal_the_registry(self):
        import dcrai.chat.retrieval_runtime as rt
        import dcrai.application.application_runtime as app
        self.assertEqual(llm.ANSWER_PREVIEW_CHARS, 300)
        self.assertEqual(rt.PROMPT_TTL, 1800)
        self.assertEqual(app.MISSES_BEFORE_HANDOVER, 2)

    def test_matcher_settings_from_env_unchanged(self):
        self.assertEqual(openchat.Settings.from_env(), openchat.Settings())
        with patch.dict(os.environ, {'FAQ_SINGLE_THRESHOLD': '0.9', 'FAQ_MAX_CANDIDATES': '2'}):
            got = openchat.Settings.from_env()
        self.assertEqual((got.single, got.maximum), (0.9, 2))
        with patch.dict(os.environ, {'FAQ_MIN_THRESHOLD': '0.95'}):
            with self.assertRaises(openchat.MatchError):
                openchat.Settings.from_env()

    def test_retriever_query_prompt_comes_from_the_registry(self):
        text = (ROOT / 'faq_search' / 'retriever.py').read_text(encoding='utf-8')
        self.assertIn('registry.get("FAQ_QUERY_PROMPT")', text)
        self.assertNotIn('getenv("FAQ_QUERY_PROMPT"', text)

    def test_spec01_settings_are_registered(self):
        expected = {'CONFIRM_LONE_SURVIVOR': (True, 'flag'), 'RELEVANCE_TIERS': (True, 'flag'),
                    'PANEL_FALLBACK_REWRITE': (False, 'flag'), 'DECISIONS_ANSWERS_MIN': (0.5, 'threshold'),
                    'DECISIONS_TOPIC_MIN': (0.5, 'threshold')}
        for name, (default, cls) in expected.items():
            with self.subTest(name):
                self.assertEqual(registry.get(name), default)
                self.assertEqual(registry.SETTINGS[name].cls, cls)

    def test_rr_flag_matches_registry(self):
        import dcrai.chat.retrieval_runtime as rt
        if not hasattr(rt, 'flag'):
            self.skipTest('rr.flag does not exist yet')
        for name in ['CONFIRM_LONE_SURVIVOR', 'RELEVANCE_TIERS', 'PANEL_FALLBACK_REWRITE']:
            for value in ['0', '1']:
                with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}):
                    self.assertEqual(rt.flag(name, value), registry.flag(name))

    def test_describe_lists_every_setting_and_no_secret_value(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test-123', 'API_KEY': 'k-456'}):
            rows = registry.describe()
        self.assertEqual([r['name'] for r in rows], list(registry.SETTINGS))
        self.assertNotIn('sk-test-123', json.dumps(rows))
        self.assertNotIn('k-456', json.dumps(rows))
        self.assertTrue(all('value' not in r for r in rows if r['cls'] == 'secret'))


class RegistrySnapshotTests(unittest.TestCase):
    def setUp(self):
        prompts.get.cache_clear()
        self.addCleanup(prompts.get.cache_clear)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = clean_env()
        env.start()
        self.addCleanup(env.stop)

    def test_prompts_version_keeps_its_definition(self):
        registry_map = prompts.registry()
        expected = hashlib.sha256(json.dumps(registry_map, sort_keys=True).encode('utf-8')).hexdigest()[:12]
        self.assertEqual(prompts.version(), expected)
        snap = registry.snapshot()
        self.assertEqual(snap['prompts_version'], expected)
        self.assertEqual(snap['prompts'], registry_map)
        self.assertEqual(prompts.digest('triage/meta'), registry_map['triage/meta'])

    def test_snapshot_shape(self):
        snap = registry.snapshot()
        self.assertEqual(set(snap), {'version', 'prompts_version', 'schema', 'prompts', 'settings', 'data'})
        self.assertEqual(snap['schema'], 1)
        self.assertEqual(snap['settings']['DECISIONS_RELEVANT_MIN'], 0.5)
        self.assertNotIn('INTERACTION_LOG_DIR', snap['settings'])     # ops
        self.assertNotIn('OPENAI_API_KEY', snap['settings'])          # secret
        self.assertEqual(set(snap['data']), {'faq_records', 'faq_embeddings_meta'})

    def test_write_snapshot_writes_once_with_full_texts(self):
        first = registry.write_snapshot(self.tmp)
        self.assertEqual(first.name, registry.version() + '.json')
        body = json.loads(first.read_text(encoding='utf-8'))
        self.assertEqual(set(body['prompt_texts']), set(prompts.names()))
        self.assertEqual(body['prompt_texts']['triage/meta'], prompts.get('triage/meta'))
        os.utime(first, (1, 1))
        second = registry.write_snapshot(self.tmp)
        self.assertEqual(second, first)
        self.assertEqual(first.stat().st_mtime, 1)
        self.assertEqual([p.name for p in self.tmp.iterdir()], [first.name])

    def test_write_snapshot_defaults_to_the_registry_folder_of_paths(self):
        with patch.object(paths, 'REGISTRY_SNAPSHOTS', self.tmp / 'registry'):
            target = registry.write_snapshot()
        self.assertEqual(target.parent, self.tmp / 'registry')
        self.assertTrue(target.exists())

    def test_secret_value_is_in_no_snapshot(self):
        env = {'OPENAI_API_KEY': 'sk-test-123', 'API_KEY': 'k-456', 'TOKEN': 'tok-789', 'FAQ_API_KEY': 'faq-000'}
        with patch.dict(os.environ, env):
            text = json.dumps(registry.snapshot())
            written = registry.write_snapshot(self.tmp).read_text(encoding='utf-8')
        for secret in env.values():
            self.assertNotIn(secret, text)
            self.assertNotIn(secret, written)

    def test_paths_has_the_registry_folder(self):
        self.assertEqual(paths.REGISTRY_SNAPSHOTS, paths.TRACES / 'registry')


class BaseLayerTests(unittest.TestCase):
    """Spec 02 R7: BASE_LAYER_DECISIONS prefixes every Decisions question; off, the request body is unchanged."""

    class Http:
        def __init__(self):
            self.sent = None

        def post(self, url, **kwargs):
            from unittest.mock import Mock
            self.sent = kwargs['json']
            names = [q['name'] for q in kwargs['json']['questions']]
            return Mock(status_code=200, json=lambda: {'answers': [{'name': n, 'type': 'predicate', 'probability': 0.5}
                                                                   for n in names]})

    QUESTIONS = [{'type': 'predicate', 'name': 'a', 'instructions': 'First question.'},
                 {'type': 'choice', 'name': 'b', 'instructions': 'Second question.',
                  'choices': [{'value': '1', 'description': 'one'}]}]

    def setUp(self):
        env = clean_env(OPENAI_API_KEY='sk-test-123')
        env.start()
        self.addCleanup(env.stop)

    def questions(self):
        return json.loads(json.dumps(self.QUESTIONS))

    def test_base_layer_off_leaves_the_request_byte_identical(self):
        http = self.Http()
        llm._decide('Evidence text', self.questions(), http)
        expected = {'model': 'gpt-6-luna', 'input': 'Evidence text', 'questions': self.QUESTIONS}
        self.assertEqual(json.dumps(http.sent, sort_keys=True), json.dumps(expected, sort_keys=True))

    def test_base_layer_on_prefixes_every_question(self):
        http = self.Http()
        with patch.dict(os.environ, {'BASE_LAYER_DECISIONS': '1'}):
            llm._decide('Evidence text', self.questions(), http)
        base = prompts.get('base/decisions')
        for sent, original in zip(http.sent['questions'], self.QUESTIONS):
            self.assertEqual(sent['instructions'], base + ' ' + original['instructions'])
            self.assertEqual({k: v for k, v in sent.items() if k != 'instructions'},
                             {k: v for k, v in original.items() if k != 'instructions'})
        self.assertEqual(http.sent['input'], 'Evidence text')

    def test_the_callers_question_list_is_not_modified(self):
        questions = self.questions()
        with patch.dict(os.environ, {'BASE_LAYER_DECISIONS': '1'}):
            llm._decide('E', questions, self.Http())
        self.assertEqual(questions, self.QUESTIONS)

    def test_recorded_call_shows_the_text_as_sent_and_the_flag(self):
        from tests.test_turn_trace import TraceCase
        import dcrai.observability.turn_trace as tt

        class Case(TraceCase):
            def runTest(self):
                pass
        case = Case()
        case.setUp()
        self.addCleanup(case.doCleanups)
        state = case.started(interface='chat')

        @tt.turn('chat')
        def request(state, data):
            llm._decide('E', self_questions(), BaseLayerTests.Http())
            with patch.dict(os.environ, {'BASE_LAYER_DECISIONS': '1'}):
                llm._decide('E', self_questions(), BaseLayerTests.Http())
            return {}
        self_questions = self.questions
        request(state, {'message': 'm'})
        off, on = case.lines(state, 'turn')[0]['calls']
        self.assertIs(off['base_layer'], False)
        self.assertIs(on['base_layer'], True)
        self.assertEqual(off['questions'], self.QUESTIONS)
        self.assertTrue(all(q['instructions'].startswith(prompts.get('base/decisions') + ' ') for q in on['questions']))

    def test_base_prompt_follows_the_editing_rules(self):
        raw = (ROOT / 'prompts' / 'base' / 'decisions.txt').read_text(encoding='utf-8')
        self.assertTrue(raw.endswith('\n') and not raw.endswith('\n\n'))
        self.assertEqual([line for line in raw.split('\n') if line != line.rstrip()], [])
        self.assertEqual(prompts.get('base/decisions'), raw[:-1])
        self.assertIn('base/decisions', prompts.names())
        self.assertNotIn('\u2014', raw)

    def test_the_flag_and_the_file_enter_the_registry_version(self):
        off = registry.version()
        with patch.dict(os.environ, {'BASE_LAYER_DECISIONS': '1'}):
            self.assertNotEqual(off, registry.version())
        self.assertIs(registry.get('BASE_LAYER_DECISIONS'), False)
        self.assertIn('base/decisions', registry.snapshot()['prompts'])


if __name__ == '__main__':
    unittest.main()
