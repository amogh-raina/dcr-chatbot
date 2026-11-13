"""Spec 03 T2 (and later T3, T4): the outcome table as a DMN in the graph.

Generator and parity tests need tools/clean_graph/dmn_table.py; the two export tests also need `xml graphs/`.
The builder and required reference graphs are shared; missing-file guards support partial checkouts.
The release check separately requires the canonical build inputs.
"""
import importlib.util
import itertools
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from dcrai.chat import outcome

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools' / 'clean_graph'
GRAPHS = ROOT / 'xml graphs'
DMN_EXPORT = GRAPHS / 'DMN chatbot - english.xml'
CORONA_EXPORT = GRAPHS / 'Corona - ChatBot SOP.xml'


def load_dmn_table():
    path = TOOLS / 'dmn_table.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('dmn_table', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dmn = load_dmn_table()
needs_tools = unittest.skipIf(dmn is None, 'tools/clean_graph/dmn_table.py is missing')


def local(tag):
    return tag.rsplit('}', 1)[-1]


def export_expression(path, expression_id):
    """(compiled value, the <definitions> element) of a DMN expression in a Portal export."""
    root = ET.parse(path).getroot()
    for el in root.iter():
        if local(el.tag) == 'expression' and el.get('id') == expression_id:
            definitions = next(c for c in el if local(c.tag) == 'definitions')
            return el.get('value'), definitions
    raise AssertionError('%s not found in %s' % (expression_id, path.name))


def valid_inputs():
    for combo in itertools.product(outcome.SCOPES, outcome.SEARCHES, outcome.RELEVANCE, outcome.CLARIFIED):
        try:
            yield combo, outcome.table(*combo)
        except ValueError:
            continue


@needs_tools
class GeneratorTests(unittest.TestCase):
    def check_export(self, path, expression_id):
        if not path.exists():
            self.skipTest('%s is missing' % path.name)
        value, definitions = export_expression(path, expression_id)
        names, _, rows, _ = dmn.parse_definitions(definitions)
        self.assertEqual(dmn.compile_table(names, rows), value)
        return names, rows, value, definitions

    def test_generator_reproduces_dmn_chatbot_export(self):
        names, rows, value, definitions = self.check_export(DMN_EXPORT, 'DMN-computation')
        self.assertEqual(names, ('Country', 'Age'))
        self.assertEqual(len(rows), 7)
        # The compiled form and the table agree on a grid of inputs.
        for country, age in itertools.product(('Denmark', 'USA', 'Slovakia', 'UK', 'Sweden', 'Chad'), range(0, 25)):
            env = {'Country': country, 'Age': age}
            with self.subTest(env=env):
                self.assertEqual(dmn.evaluate_compiled(value, env), dmn.evaluate_definitions(definitions, env))
        self.assertEqual(dmn.evaluate_compiled(value, {'Country': 'Denmark', 'Age': 20}), 'Yes')
        self.assertEqual(dmn.evaluate_compiled(value, {'Country': 'Denmark', 'Age': 17}),
                         'No. But you can purchase wine and beer')
        self.assertEqual(dmn.evaluate_compiled(value, {'Country': 'Denmark', 'Age': 10}), 'No')

    def test_generator_reproduces_corona_closecontact(self):
        names, rows, value, definitions = self.check_export(CORONA_EXPORT, 'CloseContact-computation')
        self.assertEqual(names, ('LiveWith', 'PhysicalContactWith', 'OneMeter'))
        for env_values in itertools.product((0, 1), repeat=3):
            env = dict(zip(names, env_values))
            with self.subTest(env=env):
                self.assertEqual(dmn.evaluate_compiled(value, env), dmn.evaluate_definitions(definitions, env))

    def test_compile_rule_on_small_cases(self):
        self.assertEqual(dmn.test_expr('A', None), 'true')
        self.assertEqual(dmn.test_expr('A', 'x'), '(A = "x")')
        self.assertEqual(dmn.test_expr('A', 0), '(A = 0)')
        self.assertEqual(dmn.test_expr('A', '>=18'), '((A = 18) OR (A > 18))')
        self.assertEqual(dmn.cond_expr(['A', 'B', 'C'], [None, 1, 'z']), '(true AND ((B = 1) AND (C = "z")))')
        self.assertEqual(dmn.compile_table(['A'], [(('x',), 'one')]),
                         '( If( (A = "x") ) THEN ( "one" ) ELSE ( null ) )')

    def test_compiled_value_is_the_one_in_the_spec(self):
        value = dmn.compiled_value()
        self.assertEqual(len(value), 1136)
        self.assertTrue(value.startswith('( If( ((GateScope = "out_of_scope") AND (true AND (true AND true))) ) '
                                         'THEN ( "1:out_of_scope" ) ELSE ('))
        self.assertTrue(value.endswith('THEN ( "9:not_covered" ) ELSE ( null ) ) ) ) ) ) ) ) ) ) ) ) ) ) ) ) ) )'))

    def test_compiled_matches_table_on_all_valid_inputs(self):
        value = dmn.compiled_value()
        combos = list(valid_inputs())
        self.assertEqual(len(combos), 64)
        for combo, (row, out) in combos:
            env = dict(zip(dmn.NAMES, combo))
            with self.subTest(env=env):
                self.assertEqual(dmn.evaluate_compiled(value, env), '%d:%s' % (row, out))

    def test_compiled_accepts_the_clarified_value_as_text(self):
        value = dmn.compiled_value()
        env = {'GateScope': 'in_scope', 'GateSearch': 'list', 'GateRelevance': 'several', 'GateClarified': '1'}
        self.assertEqual(dmn.evaluate_compiled(value, env), '8:offer')

    def test_definitions_match_table(self):
        xml = dmn.definitions_xml(dmn.NAMES, dmn.TYPES, dmn.outcome_rows())
        for combo, (row, out) in valid_inputs():
            env = dict(zip(dmn.NAMES, combo))
            with self.subTest(env=env):
                self.assertEqual(dmn.evaluate_definitions(xml, env), '%d:%s' % (row, out))

    def test_definitions_shape(self):
        xml = dmn.definitions_xml(dmn.NAMES, dmn.TYPES, dmn.outcome_rows())
        root = ET.fromstring(xml)
        self.assertEqual(local(root.tag), 'definitions')
        table = next(e for e in root.iter() if local(e.tag) == 'decisionTable')
        self.assertEqual(table.get('hitPolicy'), 'FIRST')
        inputs = [e for e in table if local(e.tag) == 'input']
        self.assertEqual([i.get('label') for i in inputs], ['GateScope', 'GateSearch', 'GateRelevance', 'GateClarified'])
        self.assertEqual([next(c for c in i.iter() if local(c.tag) == 'inputExpression').get('typeRef') for i in inputs],
                         ['string', 'string', 'string', 'integer'])
        outputs = [e for e in table if local(e.tag) == 'output']
        self.assertEqual([o.get('label') for o in outputs], ['OutcomeTable'])
        self.assertEqual(outputs[0].get('typeRef'), 'string')
        rules = [e for e in table if local(e.tag) == 'rule']
        self.assertEqual(len(rules), 9)
        names, types, rows, hit = dmn.parse_definitions(xml)
        self.assertEqual(hit, 'FIRST')
        self.assertEqual(rows[-1][0], (None, None, None, None))
        table_outcomes = set(outcome.OUTCOMES) - {'handover'}
        for n, (entries, output) in enumerate(rows, start=1):
            row, name = output.split(':')
            self.assertEqual(int(row), n)
            self.assertIn(name, table_outcomes)
        # Every rule has one entry per input and a description starting with its row number.
        for n, rule in enumerate(rules, start=1):
            self.assertEqual(len([c for c in rule if local(c.tag) == 'inputEntry']), 4)
            self.assertTrue(next(c for c in rule if local(c.tag) == 'description').text.startswith('Row %d:' % n))

    def test_definitions_round_trip_to_the_outcome_rows(self):
        xml = dmn.definitions_xml(dmn.NAMES, dmn.TYPES, dmn.outcome_rows())
        names, types, rows, _ = dmn.parse_definitions(xml)
        self.assertEqual(names, dmn.NAMES)
        self.assertEqual(types, dmn.TYPES)
        self.assertEqual([(tuple(e), o) for e, o in rows], [(tuple(e), o) for e, o in dmn.outcome_rows()])
        # compile of the parsed rows is the compile of the source rows
        self.assertEqual(dmn.compile_table(names, rows), dmn.compiled_value())

    def test_gate_names_are_alphanumeric_event_ids(self):
        for name in dmn.NAMES:
            self.assertRegex(name, r'^[A-Za-z][A-Za-z0-9]*$')

    def test_rows_come_from_outcome_rows(self):
        self.assertEqual(len(dmn.outcome_rows()), len(outcome.ROWS))
        for (entries, out), (row, cond, name) in zip(dmn.outcome_rows(), outcome.ROWS):
            self.assertEqual(out, '%d:%s' % (row, name))
            self.assertEqual(tuple(entries), tuple(cond))

    def test_evaluator_rejects_garbage_and_trailing_tokens(self):
        for text in ('', '( If( (A = 1) ) THEN ( 5 ) ELSE ( null ) )', '( If( (A = 1) ) THEN ( "x" ) ELSE ( null ) ) )',
                     '( If( (A ~ 1) ) THEN ( "x" ) ELSE ( null ) )'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    dmn.evaluate_compiled(text, {'A': 1})

    def test_no_match_gives_none(self):
        self.assertIsNone(dmn.evaluate_compiled('( If( (A = 1) ) THEN ( "x" ) ELSE ( null ) )', {'A': 2}))

    def test_output_with_xml_special_characters_survives(self):
        rows = [(('a<b',), 'x & "y" > z'.replace('"', ''))]
        xml = dmn.definitions_xml(['A'], ['string'], rows, descriptions={})
        names, _, parsed, _ = dmn.parse_definitions(xml)
        self.assertEqual(parsed, [(('a<b',), 'x & y > z')])


# ---------------------------------------------------------------------------------------------------------------
# The built graph (T3 and T4). The builder runs into a temporary folder, once per variant; nothing is read from
# `xml graphs/` except the Structured source the builder starts from.

import atexit
import functools
import json
import subprocess
import sys
import tempfile

BUILDER = TOOLS / 'build_clean_graph.py'
SIMULATOR = TOOLS / 'simulate_clean_graph.py'
VALIDATOR = ROOT / '.agents' / 'skills' / 'dcr-xml-builder' / 'scripts' / 'validate_dcr_xml.py'
SOURCE = GRAPHS / 'SU_handicaptillaeg_FAQ_Application_Structured.xml'
RECORDS = ROOT / 'faq_search' / 'data' / 'faq_qa_records.json'
DETERMINATIONS = TOOLS / 'determinations.json'
BASELINE = ROOT / 'tests' / 'fixtures' / 'clean_graph_event_ids_2026-10-10.json'
CAN_BUILD = all(p.exists() for p in (BUILDER, SIMULATOR, SOURCE, RECORDS, DETERMINATIONS))
needs_build = unittest.skipUnless(CAN_BUILD, 'the builder, its source graph or its data is missing (gitignored)')

_BUILD_DIR = tempfile.TemporaryDirectory(prefix='clean_graph_test_')
atexit.register(_BUILD_DIR.cleanup)


@functools.lru_cache(maxsize=None)
def build(variant):
    """(path of the with-effect graph, path of the NoEffect graph) built with --outcome <variant>."""
    out = Path(_BUILD_DIR.name)
    effect, plain = out / ('Clean_%s.xml' % variant), out / ('NoEffect_%s.xml' % variant)
    run = subprocess.run([sys.executable, str(BUILDER), '--with-effect', '--outcome', variant, str(SOURCE),
                          str(effect), str(plain), str(DETERMINATIONS), str(RECORDS)],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-800:]
    return effect, plain


class Graph:
    def __init__(self, path):
        self.root = ET.parse(path).getroot()
        res = self.root.find('specification/resources')
        self.events = {e.get('id'): e for e in res.find('events').iter('event')}
        self.expressions = {x.get('id'): x for x in res.find('expressions')}
        self.relations = {k.tag: [dict(c.attrib) for c in k] for k in self.root.find('specification/constraints')}
        self.included = {e.get('id') for e in self.root.find('runtime/marking/included')}
        self.pending = {e.get('id') for e in self.root.find('runtime/marking/pendingResponses')}

    def groups(self, eid):
        return [g.text for g in self.events[eid].findall('custom/groups/group')]

    def role(self, eid):
        return self.events[eid].findtext('custom/roles/role')

    PLURAL = {'response': 'responses', 'condition': 'conditions', 'coresponse': 'coresponses', 'include': 'includes',
              'exclude': 'excludes', 'milestone': 'milestones', 'update': 'updates'}

    def rels(self, kind, source=None, target=None):
        return [r for r in self.relations[self.PLURAL[kind]]
                if (source is None or r['sourceId'] == source) and (target is None or r['targetId'] == target)]

    def guard(self, rel):
        expr = rel.get('expressionId')
        return self.expressions[expr].get('value') if expr else None


@needs_build
class SplitTests(unittest.TestCase):
    variants = ('dmn', 'code')

    def graphs(self):
        for variant in self.variants:
            for name, path in zip(('effect', 'plain'), build(variant)):
                yield '%s/%s' % (variant, name), Graph(path)

    def test_split_keeps_every_event_id(self):
        baseline = set(json.loads(BASELINE.read_text(encoding='utf-8'))['event_ids'])
        self.assertGreater(len(baseline), 40)
        self.assertIn('Panel_Context', baseline)
        for name, g in self.graphs():
            with self.subTest(name):
                self.assertEqual(baseline - set(g.events), set())

    def test_shared_core_is_single(self):
        core = ['FAQ_Triage', 'FAQ_Scope', 'FAQ_OutOfScope', 'FAQ_NoMatch', 'FAQ_Goodbye', 'Help_Escalate',
                'Help_Handover']
        allowed_help = {'Help_Escalate', 'Help_Handover', 'Help_UserQuestion', 'Help_Retrieve', 'Help_RetrievalOk',
                        'Help_RetrievalFail', 'Help_RetrievalTimeout', 'Help_RetrievalUnavailable'}
        for name, g in self.graphs():
            ids = [e.get('id') for e in g.root.find('specification/resources/events').iter('event')]
            with self.subTest(name):
                self.assertEqual(len(ids), len(set(ids)), 'duplicate event ids')
                for eid in core:
                    self.assertEqual(ids.count(eid), 1, eid)
                self.assertEqual({i for i in ids if i.startswith('Help_')} - allowed_help, set())
                self.assertEqual(len([i for i in ids if i.startswith('Help_Triage') or i.startswith('Help_Scope')]), 0)

    def test_session_events_gate_the_inputs_and_the_selector(self):
        for name, g in self.graphs():
            with self.subTest(name):
                for session in ('Session_Chat', 'Session_Panel'):
                    self.assertEqual(g.role(session), 'Chatbot')
                    self.assertIn(session, g.included)
                    self.assertNotIn(session, g.pending)
                self.assertEqual(len(g.rels('condition', 'Session_Chat')), 1)
                self.assertEqual(len(g.rels('condition', 'Session_Chat', 'FAQ_UserQuestion')), 1)
                self.assertEqual(sorted(r['targetId'] for r in g.rels('condition', 'Session_Panel')),
                                 ['FAQ_DeterminationSelector', 'Help_UserQuestion'])

    def test_panel_search_events_and_relations(self):
        for name, g in self.graphs():
            with self.subTest(name):
                self.assertEqual([g.role(e) for e in ('Help_UserQuestion', 'Help_Retrieve', 'Help_RetrievalOk',
                                                      'Help_RetrievalFail', 'Help_RetrievalTimeout',
                                                      'Help_RetrievalUnavailable')],
                                 ['Chatbot', 'Robot', 'System', 'System', 'System', 'Chatbot'])
                self.assertNotIn('Help_UserQuestion', g.included)       # waits for triage like FAQ_UserQuestion
                self.assertNotIn('FAQ_UserQuestion', g.included)
                inc = g.rels('include', 'FAQ_Triage', 'Help_UserQuestion')
                exc = g.rels('exclude', 'FAQ_Triage', 'Help_UserQuestion')
                self.assertEqual([g.guard(r) for r in inc], ['FAQ_Triage = 1'])
                self.assertEqual([g.guard(r) for r in exc], ['FAQ_Triage != 1'])
                self.assertEqual(len(g.rels('response', 'Help_UserQuestion', 'Help_Retrieve')), 1)
                for src in ('Help_RetrievalFail', 'Help_RetrievalTimeout'):
                    self.assertEqual(len(g.rels('response', src, 'Help_RetrievalUnavailable')), 1)
                # Not in FAQAnswer: the determination collector reads that group.
                self.assertNotIn('FAQAnswer', g.groups('Help_RetrievalUnavailable'))
                self.assertIn('HelpRetrieval', g.groups('Help_RetrievalUnavailable'))

    def test_effect_on_both_robots_only_in_the_with_effect_graph(self):
        for variant in self.variants:
            effect, plain = (Graph(p) for p in build(variant))
            for robot, q, ok in (('FAQ_Retrieve', 'FAQ_UserQuestion', 'FAQ_RetrievalOk'),
                                 ('Help_Retrieve', 'Help_UserQuestion', 'Help_RetrievalOk')):
                with self.subTest(variant=variant, robot=robot):
                    self.assertEqual(effect.events[robot].findtext('custom/eventType'), 'handicap-faq-v2')
                    params = {p.get('title'): p.get('value') for p in effect.events[robot].findall(
                        'custom/eventTypeData/parameter')}
                    self.assertEqual(params['q'], q)
                    self.assertEqual(params['ContinueOnOk'], '"%s"' % ok)
                    self.assertEqual(params['ContinueOnFail'], '"%s"' % ok.replace('Ok', 'Fail'))
                    self.assertEqual(params['ContinueOnTimeout'], '"%s"' % ok.replace('Ok', 'Timeout'))
                    self.assertFalse(plain.events[robot].findtext('custom/eventType'))
                    self.assertEqual(plain.events[robot].findall('custom/eventTypeData/parameter'), [])

    def test_form0_relations_and_marking_are_unchanged(self):
        source = Graph(SOURCE)

        def form_relations(g):
            return sorted((k, r['sourceId'], r['targetId'], g.guard(r)) for k, rs in g.relations.items() for r in rs
                          if r['sourceId'].startswith('Form0') and r['targetId'].startswith('Form0'))
        for name, g in self.graphs():
            with self.subTest(name):
                self.assertEqual(form_relations(g), form_relations(source))
                form = {e for e in g.events if e.startswith('Form0')}
                self.assertEqual(g.included & form, source.included & form)
                self.assertEqual(g.pending & form, set())
                crossing = [(k, r['sourceId'], r['targetId']) for k, rs in g.relations.items() for r in rs
                            if r['targetId'].startswith('Form0') != r['sourceId'].startswith('Form0')]
                self.assertEqual(crossing, [])

    def test_panel_context_and_escalation_are_untouched(self):
        for name, g in self.graphs():
            with self.subTest(name):
                self.assertEqual(g.groups('Panel_Context'), ['FAQContext', 'PanelContext'])
                self.assertEqual(g.rels('response', 'Help_Escalate', 'Help_Handover')[0]['sourceId'], 'Help_Escalate')
                self.assertEqual([r for k, rs in g.relations.items() for r in rs
                                  if 'Panel_Context' in (r['sourceId'], r['targetId'])], [])

    def test_declared_groups_cover_the_groups_in_use(self):
        for name, g in self.graphs():
            declared = {x.text for x in g.root.find('specification/resources/custom/groups')}
            used = {t for e in g.events for t in g.groups(e) if t}
            with self.subTest(name):
                self.assertEqual(used - declared, set())

    def test_validator_accepts_both_variants(self):
        if not VALIDATOR.exists():
            self.skipTest('validator is missing')
        for variant in self.variants:
            for path in build(variant):
                with self.subTest(variant=variant, file=path.name):
                    run = subprocess.run([sys.executable, str(VALIDATOR), str(path)], capture_output=True, text=True)
                    self.assertIn('OK: 0 errors, 0 warning(s)', run.stdout, run.stdout[-500:])

    def test_simulator_passes_on_both_variants(self):
        for variant in self.variants:
            plain = build(variant)[1]
            with self.subTest(variant=variant):
                run = subprocess.run([sys.executable, str(SIMULATOR), str(plain)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr[-500:])
                self.assertIn('FAILURES: 0', run.stdout, '\n'.join(l for l in run.stdout.splitlines() if l.startswith('FAIL')))


@needs_build
@needs_tools
class OutcomeTableGraphTests(unittest.TestCase):
    """T4: TurnOutcome, the outcome events and (--outcome dmn) the decision table inside the graph."""
    DMN_ONLY = ('TurnStart', 'GateScope', 'GateSearch', 'GateRelevance', 'GateClarified', 'OutcomeTable', 'TurnResult')
    HOST_TEXTS = {   # identical wording to the host's current strings (retrieval_runtime.py) and spec 01's WD2 texts
        'Outcome_Confirm': 'Is this what you are asking?',
        'Outcome_Clarify': 'I found a few questions that may fit. Which one is closest?',
        'Outcome_Offer': 'No FAQ answers exactly this. These are on the same topic and may help:',
        'FAQ_Msg_OfferOne': 'No FAQ answers exactly this. This one is on the same topic and may help:',
        'FAQ_Msg_ScopeQuestion': 'Is your question about handicaptillæg, the SU disability supplement?',
        'FAQ_Msg_Rephrase': 'Could you rephrase your question? A few more words about your situation help.'}

    def graph(self, variant, effect=False):
        return Graph(build(variant)[0 if effect else 1])

    def items(self, g, eid):
        return [(i.get('label'), i.get('value')) for i in g.events[eid].findall('custom/eventData/dictionary/item')]

    def definitions(self, g):
        expr = g.expressions['OutcomeTable-computation']
        return expr, next(c for c in expr if local(c.tag) == 'definitions')

    def test_built_graph_dmn_is_in_step(self):
        for effect in (False, True):
            g = self.graph('dmn', effect)
            expr, definitions = self.definitions(g)
            names, types, rows, hit = dmn.parse_definitions(definitions)
            with self.subTest(effect=effect):
                self.assertEqual(expr.get('type'), 'DMN')
                self.assertEqual(expr.get('value'), dmn.compiled_value())
                self.assertEqual(expr.get('value'), dmn.compile_table(names, rows))
                self.assertEqual((names, types, hit), (dmn.NAMES, dmn.TYPES, 'FIRST'))
                self.assertEqual([(tuple(e), o) for e, o in rows], [(tuple(e), o) for e, o in dmn.outcome_rows()])
                for name in names:      # every input label is an event id of the graph
                    self.assertIn(name, g.events)
                self.assertEqual(g.events['OutcomeTable'].get('computation'), 'OutcomeTable-computation')

    def test_definitions_in_the_graph_decide_like_the_function(self):
        _, definitions = self.definitions(self.graph('dmn'))
        for combo, (row, out) in valid_inputs():
            with self.subTest(combo=combo):
                self.assertEqual(dmn.evaluate_definitions(definitions, dict(zip(dmn.NAMES, combo))),
                                 '%d:%s' % (row, out))

    def test_dmn_namespace_is_declared_on_definitions_only(self):
        for path in build('dmn'):
            text = Path(path).read_text(encoding='utf-8')
            with self.subTest(file=Path(path).name):
                self.assertEqual(text.count('xmlns='), 1)
                self.assertEqual(text.count('xmlns:biodi='), 1)
                self.assertIn('<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/"', text)
                self.assertNotIn('{', ET.parse(path).getroot().tag)

    def test_dmn_wiring_follows_the_portal_export(self):
        g = self.graph('dmn')
        self.assertEqual(g.role('OutcomeTable'), 'Robot')
        self.assertEqual(list(g.events['OutcomeTable'].find('custom/eventData')), [])   # as the export: no data
        for name in dmn.NAMES:
            link = '%s--condition--OutcomeTable' % name
            with self.subTest(gate=name):
                self.assertEqual([r.get('link') for r in g.rels('condition', name, 'OutcomeTable')], [link])
                self.assertEqual([r.get('link') for r in g.rels('milestone', name, 'OutcomeTable')], [link])
                self.assertEqual(len(g.rels('response', name, 'OutcomeTable')), 1)
                self.assertEqual(len(g.rels('response', 'TurnStart', name)), 1)
                self.assertEqual(g.role(name), 'Chatbot')
        link = 'OutcomeTable--condition--TurnResult'
        self.assertEqual([r.get('link') for r in g.rels('condition', 'OutcomeTable', 'TurnResult')], [link])
        self.assertEqual([r.get('link') for r in g.rels('milestone', 'OutcomeTable', 'TurnResult')], [link])
        updates = g.rels('update', 'OutcomeTable', 'TurnResult')
        self.assertEqual([u['valueExpressionId'] for u in updates], ['OutcomeTable-path-TurnResult--update--value'])
        self.assertEqual(g.expressions['OutcomeTable-path-TurnResult--update--value'].get('value'),
                         '"result " + OutcomeTable')
        for eid in self.DMN_ONLY:   # initial marking: all included, nothing pending
            self.assertIn(eid, g.included)
        self.assertEqual(g.pending, set())

    def test_gate_dictionaries_are_the_input_domains(self):
        g = self.graph('dmn')
        self.assertEqual([v for _, v in self.items(g, 'GateScope')], list(outcome.SCOPES))
        self.assertEqual([v for _, v in self.items(g, 'GateSearch')], list(outcome.SEARCHES))
        self.assertEqual([v for _, v in self.items(g, 'GateRelevance')], list(outcome.RELEVANCE))
        self.assertEqual([v for _, v in self.items(g, 'GateClarified')], [str(c) for c in outcome.CLARIFIED])
        self.assertEqual(g.events['GateClarified'].find('custom/eventData/dataType').get('format'), 'int')
        self.assertEqual(g.events['GateScope'].find('custom/eventData/dataType').get('format'), 'string')

    def test_code_variant_has_no_dmn_machinery(self):
        for effect in (False, True):
            g = self.graph('code', effect)
            with self.subTest(effect=effect):
                for eid in self.DMN_ONLY:
                    self.assertNotIn(eid, g.events)
                self.assertNotIn('OutcomeTable-computation', g.expressions)
                self.assertEqual(g.relations['milestones'] and [r for r in g.relations['milestones']
                                                                if not r['sourceId'].startswith('Form0')], [])
                self.assertEqual(g.relations['updates'], [])
                self.assertNotIn('Gate', {x.text for x in g.root.find('specification/resources/custom/groups')})
                for eid in ('TurnOutcome', 'Outcome_Confirm', 'FAQ_Msg_Rephrase'):
                    self.assertIn(eid, g.events)

    def test_turnoutcome_dictionary_equals_outcomes(self):
        for variant in ('dmn', 'code'):
            g = self.graph(variant)
            with self.subTest(variant=variant):
                self.assertEqual([v for _, v in self.items(g, 'TurnOutcome')], list(outcome.OUTCOMES))
                self.assertEqual(g.events['TurnOutcome'].find('custom/eventData/dataType').get('format'), 'string')
                self.assertEqual(g.role('TurnOutcome'), 'Chatbot')
                self.assertIn('TurnOutcome', g.included)

    def test_each_outcome_has_one_guarded_response_and_one_co_response(self):
        for variant in ('dmn', 'code'):
            g = self.graph(variant)
            for name, event in outcome.OUTCOME_EVENT.items():
                with self.subTest(variant=variant, outcome=name):
                    self.assertIn(event, g.events)
                    self.assertEqual([g.guard(r) for r in g.rels('response', 'TurnOutcome', event)],
                                     ['TurnOutcome = "%s"' % name])
                    self.assertEqual([g.guard(r) for r in g.rels('coresponse', 'TurnOutcome', event)],
                                     ['TurnOutcome != "%s"' % name])
                    self.assertIn('Outcome:%s' % name, g.groups(event))
            self.assertEqual(len(g.rels('response', 'TurnOutcome')), len(outcome.OUTCOMES))
            self.assertEqual(len(g.rels('coresponse', 'TurnOutcome')), len(outcome.OUTCOMES))
            # no outcome event is pending at the start
            self.assertEqual(g.pending & set(outcome.OUTCOME_EVENT.values()), set())

    def test_outcome_texts_equal_the_host_strings(self):
        for variant in ('dmn', 'code'):
            g = self.graph(variant)
            for eid, text in self.HOST_TEXTS.items():
                with self.subTest(variant=variant, event=eid):
                    desc = g.events[eid].findtext('custom/eventDescription')
                    self.assertEqual(re.sub(r'<[^>]+>', '', desc), text)
                    self.assertEqual(g.role(eid), 'Chatbot')
                    self.assertIn(eid, g.included)
            self.assertEqual(g.events['Outcome_Answer'].findtext('custom/eventDescription'), '')

    def test_message_events_have_no_relations_and_the_texts_match_the_runtime_constants(self):
        g = self.graph('dmn')
        for eid in ('FAQ_Msg_OfferOne', 'FAQ_Msg_ScopeQuestion', 'FAQ_Msg_Rephrase'):
            self.assertEqual([r for rs in g.relations.values() for r in rs if eid in (r['sourceId'], r['targetId'])], [])
        import dcrai.chat.retrieval_runtime as rt
        for const, eid in (('CONFIRM_TEXT', 'Outcome_Confirm'), ('RELATED_ONE', 'FAQ_Msg_OfferOne'),
                           ('RELATED_MANY', 'Outcome_Offer')):
            if hasattr(rt, const):
                self.assertEqual(getattr(rt, const), self.HOST_TEXTS[eid], const)

    def test_existing_message_events_gain_their_outcome_group_and_keep_their_text(self):
        g = self.graph('dmn')
        for eid, group in (('FAQ_NoMatch', 'Outcome:not_covered'), ('FAQ_OutOfScope', 'Outcome:out_of_scope'),
                           ('Help_Handover', 'Outcome:handover')):
            self.assertIn(group, g.groups(eid))
        self.assertIn('FAQNoMatch', g.groups('FAQ_NoMatch'))
        self.assertIn('FAQHandover', g.groups('Help_Handover'))
        self.assertIn('I could not find an answer', g.events['FAQ_NoMatch'].findtext('custom/eventDescription'))

    def test_outcome_function_and_graph_share_one_row_source(self):
        # the graph's DMN is built from outcome.ROWS; changing a row changes the compiled text
        base = dmn.compile_table(dmn.NAMES, dmn.outcome_rows())
        changed = dmn.compile_table(dmn.NAMES, [(c, o) for c, o in dmn.outcome_rows()][:-1] + [(
            (None, None, None, None), '9:answer')])
        self.assertNotEqual(base, changed)
        self.assertEqual(base, self.graph('dmn').expressions['OutcomeTable-computation'].get('value'))


if __name__ == '__main__':
    unittest.main()
