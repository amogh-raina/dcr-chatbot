"""Regression checks for corrupt traces and evaluation counts."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from dcrai.observability import trace_reader as reader
from dcrai.observability import turn_trace


class TraceIntegrityTests(unittest.TestCase):
    def test_empty_and_malformed_files_fail_validation(self):
        for content in ('', '{broken\n', '{"kind":"start","schema":2}\nnot json\n'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'trace.jsonl'
                path.write_text(content)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(reader.main(['--check', str(path)]), 1)

    def test_duplicate_and_orphan_reactions_cannot_inflate_acceptance(self):
        lines = [dict(kind='faq_outcome', turn=1, outcome='confirm'),
                 dict(kind='faq_reaction', turn=1, next_action='accepted', outcome='confirm'),
                 dict(kind='faq_reaction', turn=1, next_action='accepted', outcome='confirm'),
                 dict(kind='faq_reaction', turn=99, next_action='accepted', outcome='confirm')]
        self.assertEqual(reader.confirm_accept_counts(lines), (1, 1))

    def test_outcomes_are_deduplicated_in_either_order(self):
        lines = [dict(kind='turn', turn=1, outcome='confirm'),
                 dict(kind='faq_outcome', turn=1, outcome='confirm')]
        self.assertEqual(reader.confirm_accept_counts(lines), (0, 1))

    def test_duplicate_turn_numbers_fail_validation(self):
        row = dict(kind='turn', turn=1, registry_version='x', graph_revision='g')
        self.assertTrue(any('repeats' in p for p in reader.check([row, row])))

    def test_many_short_items_are_bounded_and_marked(self):
        data, truncated = turn_trace._limit(dict(turn=1, calls=[{'input': 'a' * 100} for _ in range(10000)]))
        self.assertTrue(truncated)
        self.assertLess(len(json.dumps(data).encode()), turn_trace.MAX_LINE)
        self.assertIn('calls', data['omitted_fields'])
        self.assertEqual(data['turn'], 1)

    def test_markdown_escapes_html_and_preserves_turn_context(self):
        lines = [dict(kind='start', interaction_id='synthetic', graph_revision='g@v', registry_version='v'),
                 dict(kind='turn', turn=1, interface='chat', entry='message', message='<script>alert(1)</script>',
                      outcome='confirm', faq_ids=['FAQ_16'], searches=[dict(query='work', kept=['FAQ_16'])])]
        result = reader.markdown(lines, 'sample')
        self.assertIn('Turn 1', result)
        self.assertIn('FAQ_16', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertNotIn('<script>', result)


if __name__ == '__main__':
    unittest.main()
