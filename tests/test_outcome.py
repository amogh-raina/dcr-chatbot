"""Spec 03 T1: the outcome function. Pure, no model, no DCR."""
import ast
import itertools
import unittest
from pathlib import Path

from dcrai.chat import outcome as oc

SOURCE = Path(oc.__file__)


class TableTests(unittest.TestCase):
    def test_table_nine_rows(self):
        cases = [
            (1, ('out_of_scope', 'none', 'none', 0), 'out_of_scope'),
            (2, ('unsure', 'none', 'none', 0), 'clarify'),
            (3, ('in_scope', 'none', 'none', 1), 'not_covered'),
            (4, ('in_scope', 'single', 'one_answers', 0), 'answer'),
            (5, ('in_scope', 'single', 'related', 0), 'offer'),
            (5, ('in_scope', 'list', 'related', 1), 'offer'),
            (6, ('in_scope', 'list', 'one_answers', 1), 'confirm'),
            (7, ('in_scope', 'list', 'several', 0), 'clarify'),
            (8, ('in_scope', 'list', 'several', 1), 'offer'),
            (9, ('in_scope', 'list', 'none', 0), 'not_covered'),
            (9, ('in_scope', 'single', 'none', 1), 'not_covered'),
        ]
        for row, inputs, outcome in cases:
            with self.subTest(row=row, inputs=inputs):
                self.assertEqual(oc.table(*inputs), (row, outcome))

    def test_first_match_wins(self):
        self.assertEqual(oc.table('out_of_scope', 'list', 'several', 1)[0], 1)
        self.assertEqual(oc.table('in_scope', 'list', 'related', 0)[0], 5)
        self.assertEqual(oc.table('in_scope', 'list', 'one_answers', 1)[0], 6)

    def test_every_row_reachable_and_valid_count(self):
        valid, rows = 0, set()
        for combo in itertools.product(oc.SCOPES, oc.SEARCHES, oc.RELEVANCE, oc.CLARIFIED):
            try:
                rows.add(oc.table(*combo)[0])
                valid += 1
            except ValueError:
                pass
        self.assertEqual(valid, 64)
        self.assertEqual(rows, set(range(1, 10)))

    def test_invalid_values_and_combinations_raise(self):
        for combo in [('in_scope', 'none', 'related', 0), ('in_scope', 'single', 'several', 0),
                      ('in_scope', 'none', 'one_answers', 0), ('in_scope', 'none', 'several', 0),
                      ('maybe', 'none', 'none', 0), ('in_scope', 'many', 'none', 0),
                      ('in_scope', 'none', 'some', 0), ('in_scope', 'none', 'none', 2),
                      ('in_scope', 'none', 'none', True), ('in_scope', 'none', 'none', '0')]:
            with self.subTest(combo=combo):
                with self.assertRaises(ValueError):
                    oc.table(*combo)

    def test_rows_are_the_nine_roadmap_rows_in_order(self):
        self.assertEqual([r[0] for r in oc.ROWS], list(range(1, 10)))
        self.assertTrue(all(r[2] in oc.OUTCOMES and r[2] != 'handover' for r in oc.ROWS))
        self.assertEqual(oc.ROWS[-1][1], (None, None, None, None))


class DeriveTests(unittest.TestCase):
    def test_derive_inputs_matrix(self):
        A, R = 'answers', 'related'
        matrix = [
            ('no_match', [], ('none', 'none')),
            ('single_match', [], ('single', 'none')),
            ('single_match', [A], ('single', 'one_answers')),
            ('single_match', [R], ('single', 'related')),
            ('clarify_match', [], ('list', 'none')),
            ('clarify_match', [A], ('list', 'one_answers')),
            ('clarify_match', [A, R], ('list', 'one_answers')),
            ('clarify_match', [R, A, R], ('list', 'one_answers')),
            ('clarify_match', [A, A], ('list', 'several')),
            ('clarify_match', [A, A, R], ('list', 'several')),
            ('clarify_match', [R], ('list', 'related')),
            ('clarify_match', [R, R], ('list', 'related')),
        ]
        for decision, tiers, expected in matrix:
            with self.subTest(decision=decision, tiers=tiers):
                self.assertEqual(oc.derive_inputs(decision, tiers), expected)

    def test_no_match_with_candidates_and_unknowns_raise(self):
        with self.assertRaises(ValueError):
            oc.derive_inputs('no_match', ['answers'])
        with self.assertRaises(ValueError):
            oc.derive_inputs('maybe_match', [])
        with self.assertRaises(ValueError):
            oc.derive_inputs('clarify_match', ['fits'])

    def test_derive_inputs_never_invalid(self):
        for decision in oc.DECISIONS:
            for n in range(4):
                for tiers in itertools.product(oc.TIERS, repeat=n):
                    if decision == 'no_match' and tiers:
                        continue
                    with self.subTest(decision=decision, tiers=tiers):
                        search, relevance = oc.derive_inputs(decision, list(tiers))
                        for clarified in oc.CLARIFIED:
                            oc.table('in_scope', search, relevance, clarified)   # must not raise

    def test_candidate_dicts_are_accepted(self):
        self.assertEqual(oc.derive_inputs('clarify_match', [{'id': 'FAQ_1', 'tier': 'answers'}]),
                         ('list', 'one_answers'))

    def test_lone_survivor_is_confirm_true_single_is_answer(self):
        rows = [oc.decide('in_scope', d, t).row for d, t in
                [('clarify_match', ['answers']), ('clarify_match', ['answers', 'related']),
                 ('single_match', ['answers'])]]
        self.assertEqual(rows, [6, 6, 4])


class DecideTests(unittest.TestCase):
    def test_decide_handover_rules(self):
        d = oc.decide('in_scope', 'no_match', [], asked_person=True)
        self.assertEqual((d.outcome, d.row, d.handover_reason), ('handover', None, 1))
        d = oc.decide('in_scope', 'no_match', [], misses=0)
        self.assertEqual((d.outcome, d.row, d.handover_reason), ('not_covered', 3, None))
        d = oc.decide('in_scope', 'no_match', [], misses=1)
        self.assertEqual((d.outcome, d.row, d.table_outcome, d.handover_reason), ('handover', 3, 'not_covered', 2))
        d = oc.decide('in_scope', 'no_match', [], misses=1, handover_shown=True)
        self.assertEqual((d.outcome, d.handover_reason), ('not_covered', None))
        d = oc.decide('out_of_scope', None, [], misses=5)
        self.assertEqual((d.outcome, d.row), ('out_of_scope', 1))

    def test_asked_person_wins_over_everything(self):
        d = oc.decide('out_of_scope', None, None, handover_shown=True, asked_person=True)
        self.assertEqual((d.outcome, d.handover_reason), ('handover', 1))

    def test_decide_row_9_also_hands_over(self):
        d = oc.decide('in_scope', 'clarify_match', [], misses=1)
        self.assertEqual((d.outcome, d.row, d.handover_reason), ('handover', 9, 2))

    def test_decide_clarify_kind_and_label(self):
        cases = [
            (('unsure', None, []), 2, 'scope', None),
            (('in_scope', 'clarify_match', ['answers', 'answers']), 7, 'candidates', None),
            (('in_scope', 'single_match', ['related']), 5, None, 'related'),
            (('in_scope', 'clarify_match', ['answers', 'answers']), 8, None, 'may_fit'),
        ]
        for args, row, kind, label in cases:
            with self.subTest(row=row):
                d = oc.decide(*args, clarified=1 if row == 8 else 0)
                self.assertEqual((d.row, d.clarify_kind, d.label), (row, kind, label))

    def test_decide_records_inputs_and_skips_search_when_not_in_scope(self):
        d = oc.decide('unsure', 'clarify_match', ['answers', 'answers'], clarified=1)
        self.assertEqual(d.inputs, ('unsure', 'none', 'none', 1))
        d = oc.decide('in_scope', 'clarify_match', ['answers'], clarified=0)
        self.assertEqual(d.inputs, ('in_scope', 'list', 'one_answers', 0))
        self.assertEqual(d.outcome, d.table_outcome)

    def test_decide_in_scope_without_decision_raises(self):
        with self.assertRaises(ValueError):
            oc.decide('in_scope', None, [])

    def test_decide_agrees_with_table_for_every_valid_input(self):
        for combo in itertools.product(oc.SCOPES, oc.SEARCHES, oc.RELEVANCE, oc.CLARIFIED):
            try:
                row, out = oc.table(*combo)
            except ValueError:
                continue
            with self.subTest(combo=combo):
                scope, search, relevance, clarified = combo
                if scope != 'in_scope':
                    d = oc.decide(scope, None, [], clarified=clarified)
                else:
                    tiers = {'none': [], 'related': ['related'], 'one_answers': ['answers'],
                             'several': ['answers', 'answers']}[relevance]
                    decision = {'none': 'no_match', 'single': 'single_match', 'list': 'clarify_match'}[search]
                    if search == 'single' and relevance == 'several':
                        continue
                    d = oc.decide(scope, decision, tiers, clarified=clarified)
                self.assertEqual((d.row, d.outcome), (row, out))

    def test_shown_for(self):
        a1, a2, r1, r2 = ({'id': i, 'tier': t} for i, t in [('a1', 'answers'), ('a2', 'answers'),
                                                            ('r1', 'related'), ('r2', 'related')])
        self.assertEqual(oc.shown_for(4, [a1]), [a1])
        self.assertEqual(oc.shown_for(6, [r1, a1, r2]), [a1])
        self.assertEqual(oc.shown_for(5, [r1, r2]), [r1, r2])
        self.assertEqual(oc.shown_for(7, [r1, a1, a2]), [a1, a2, r1])
        self.assertEqual(oc.shown_for(8, [r1, a1, a2, r2]), [a1, a2, r1, r2])
        for row in (1, 2, 3, 9, None):
            self.assertEqual(oc.shown_for(row, [a1, r1]), [])


class CounterTests(unittest.TestCase):
    # signal: (clarified, misses) after the signal, from a start of clarified 1 and misses 1
    EXPECTED = {
        'clarify_candidates': (1, 1), 'scope_question': (1, 1),
        'answered': (0, 0), 'accepted': (0, 0), 'chose': (0, 0),
        'not_covered': (1, 2), 'none_of_these': (1, 2), 'rejected': (1, 2),
        'handover': (1, 0),
        'out_of_scope': (0, 1), 'end': (0, 1),
        'rephrase': (1, 1), 'offer': (1, 1), 'confirm_shown': (1, 1),
    }

    def test_counter_rules(self):
        for signal, (clarified, misses) in self.EXPECTED.items():
            with self.subTest(signal=signal):
                self.assertEqual(oc.next_clarified(1, signal), clarified)
                self.assertEqual(oc.next_misses(1, signal), misses)

    def test_clarify_candidates_sets_the_flag_from_zero(self):
        self.assertEqual(oc.next_clarified(0, 'clarify_candidates'), 1)
        self.assertEqual(oc.next_clarified(0, 'scope_question'), 0)
        self.assertEqual(oc.next_clarified(0, 'rephrase'), 0)

    def test_unknown_signal_raises(self):
        with self.assertRaises(ValueError):
            oc.next_clarified(0, 'whatever')
        with self.assertRaises(ValueError):
            oc.next_misses(0, 'whatever')

    def test_second_miss_in_a_row_hands_over_once(self):
        misses, shown = 0, False
        d = oc.decide('in_scope', 'no_match', [], misses=misses, handover_shown=shown)
        self.assertEqual(d.outcome, 'not_covered')
        misses = oc.next_misses(misses, 'not_covered')
        d = oc.decide('in_scope', 'no_match', [], misses=misses, handover_shown=shown)
        self.assertEqual(d.outcome, 'handover')
        misses, shown = oc.next_misses(misses, 'handover'), True
        misses = oc.next_misses(misses, 'not_covered')
        misses = oc.next_misses(misses, 'not_covered')
        d = oc.decide('in_scope', 'no_match', [], misses=misses, handover_shown=shown)
        self.assertEqual(d.outcome, 'not_covered')

    def test_an_answer_resets_the_miss_run(self):
        misses = oc.next_misses(oc.next_misses(0, 'not_covered'), 'answered')
        self.assertEqual(misses, 0)


class ModuleTests(unittest.TestCase):
    def test_no_candidate_count_branch_in_runtimes(self):
        # R6: which outcome a turn ends in is decided by the table, never by counting candidates in the runtimes.
        import re
        root = SOURCE.parent.parent
        for path in (root / 'chat' / 'retrieval_runtime.py', root / 'application' / 'application_runtime.py'):
            text = path.read_text(encoding='utf-8')
            with self.subTest(path.name):
                self.assertIsNone(re.search(r'len\(found\)\s*==\s*1', text))
                self.assertNotIn('interim_outcome', text)

    def test_outcome_event_map_covers_outcomes(self):
        self.assertEqual(set(oc.OUTCOME_EVENT), set(oc.OUTCOMES))
        self.assertEqual(len(set(oc.OUTCOME_EVENT.values())), len(oc.OUTCOMES))

    def test_outcome_module_has_no_io(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                modules.add((node.module or '').split('.')[0])
        self.assertLessEqual(modules, {'typing', 'collections'})
        self.assertNotIn('dcrai', modules)


if __name__ == '__main__':
    unittest.main()
