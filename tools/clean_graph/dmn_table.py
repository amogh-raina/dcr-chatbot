"""Generator for the outcome table as a DCR DMN expression (spec 03, T2).

Source of the rows is dcrai.chat.outcome.ROWS, so the table in code and the table in the graph cannot drift.

compile_table(names, rows)   the compiled `value` of the expression, by the rule the Portal exports show
definitions_xml(...)         the <definitions> element (decision table) that goes inside the expression
evaluate_compiled(text, env) a small evaluator for exactly the compiled grammar (tests, local simulator)
parse_definitions(...)       names and rows read back from a <definitions> element (observed exports too)
evaluate_definitions(...)    first-match evaluation of a <definitions> element

A row is (entries, output) where entries has one item per input: None is a dash (matches anything), an int or str is
an equality test, a str starting with '>=' is a lower bound. `output` is the plain string (no quotes).
Compile rule, reproduced byte for byte on `DMN-computation` of "DMN chatbot - english.xml" and
`CloseContact-computation` of "Corona - ChatBot SOP.xml": each rule becomes
`( If( COND ) THEN ( "out" ) ELSE ( NEXT ) )`, COND is a right-nested AND chain of per-input tests, `-` is `true`,
and the chain ends in `null`.
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

# Make `dcrai` importable when this file is loaded straight from tools/clean_graph.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

NAMES = ('GateScope', 'GateSearch', 'GateRelevance', 'GateClarified')   # event ids, alphanumeric by design
TYPES = ('string', 'string', 'string', 'integer')
OUTPUT_LABEL = 'OutcomeTable'
DMN_NS = 'https://www.omg.org/spec/DMN/20191111/MODEL/'
BIODI_NS = 'http://bpmn.io/schema/dmn/biodi/2.0'

ROW_DESCRIPTIONS = {
    1: 'Row 1: out of scope',
    2: 'Row 2: scope unsure, ask whether the question is about handicaptillaeg',
    3: 'Row 3: the API found nothing',
    4: 'Row 4: a true single match that answers',
    5: 'Row 5: nothing answers, same topic only, offer as related',
    6: 'Row 6: lone survivor of a list, confirm',
    7: 'Row 7: several answer, not yet clarified, clarify',
    8: 'Row 8: several answer, already clarified, offer the best',
    9: 'Row 9: nothing usable left, or fail closed',
}


def lit(v):
    return str(v) if isinstance(v, int) else '"%s"' % v


def test_expr(name, entry):
    if entry is None:
        return 'true'
    if isinstance(entry, str) and entry.startswith('>='):
        return '((%s = %s) OR (%s > %s))' % (name, entry[2:], name, entry[2:])
    return '(%s = %s)' % (name, lit(entry))


def cond_expr(names, entries):
    parts = [test_expr(n, e) for n, e in zip(names, entries)]
    s = parts[-1]
    for p in reversed(parts[:-1]):
        s = '(%s AND %s)' % (p, s)
    return s


def compile_table(names, rows):
    """rows: [(entries, output string)]"""
    def go(i):
        if i == len(rows):
            return 'null'
        entries, out = rows[i][0], rows[i][1]
        return '( If( %s ) THEN ( "%s" ) ELSE ( %s ) )' % (cond_expr(names, entries), out, go(i + 1))
    return go(0)


def outcome_rows():
    """The rows of the outcome function as [(entries, '<row>:<outcome>')]."""
    from dcrai.chat import outcome
    return [(cond, '%d:%s' % (row, out)) for row, cond, out in outcome.ROWS]


def compiled_value():
    return compile_table(NAMES, outcome_rows())


# ---------------------------------------------------------------------------------------------------------------
# <definitions>

def _entry_text(entry):
    if entry is None:
        return '-'
    if isinstance(entry, str) and entry.startswith('>='):
        return entry
    return lit(entry)


def _row_number(output):
    m = re.match(r'(\d+):', output)
    return int(m.group(1)) if m else None


def definitions_xml(names=NAMES, types=TYPES, rows=None, output_label=OUTPUT_LABEL, descriptions=None):
    """The <definitions> element of the DMN expression, shape copied from "DMN chatbot - english.xml"."""
    rows = outcome_rows() if rows is None else rows
    descriptions = ROW_DESCRIPTIONS if descriptions is None else descriptions
    out = ['<definitions xmlns="%s" xmlns:biodi="%s" id="definitions_outcome" name="definitions" '
           'namespace="http://camunda.org/schema/1.0/dmn" exporter="dmn-js (https://demo.bpmn.io/dmn)" '
           'exporterVersion="11.0.1">' % (DMN_NS, BIODI_NS),
           '<decision id="decision_outcome" name="">',
           '<decisionTable id="decisionTable_outcome" hitPolicy="FIRST">']
    for i, (name, typ) in enumerate(zip(names, types), start=1):
        out.append('<input id="input_%d" label=%s biodi:width="150"><inputExpression id="expr_%d" typeRef=%s>'
                   '<text/></inputExpression></input>' % (i, quoteattr(name), i, quoteattr(typ)))
    out.append('<output id="output_outcome" label=%s name="" typeRef="string" biodi:width="150"/>'
               % quoteattr(output_label))
    for n, row in enumerate(rows, start=1):
        entries, output = row[0], row[1]
        desc = descriptions.get(_row_number(output), '') if isinstance(descriptions, dict) else ''
        out.append('<rule id="rule_%d"><description>%s</description>' % (n, escape(desc)))
        for i, entry in enumerate(entries, start=1):
            out.append('<inputEntry id="r%d_in%d"><text>%s</text></inputEntry>' % (n, i, escape(_entry_text(entry))))
        out.append('<outputEntry id="r%d_out"><text>%s</text></outputEntry></rule>' % (n, escape('"%s"' % output)))
    out.append('</decisionTable></decision></definitions>')
    return '\n'.join(out)


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _children(el, name):
    return [c for c in el if _local(c.tag) == name]


def _parse_entry(text):
    text = (text or '').strip()
    if text in ('', '-'):
        return None
    if text.startswith('>='):
        return text
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return int(text)


def parse_definitions(source):
    """(names, types, rows, hit_policy) from a <definitions> element or its XML text."""
    el = ET.fromstring(source) if isinstance(source, str) else source
    table = next(e for e in el.iter() if _local(e.tag) == 'decisionTable')
    inputs = _children(table, 'input')
    names = tuple(i.get('label') for i in inputs)
    types = tuple(next(c for c in i.iter() if _local(c.tag) == 'inputExpression').get('typeRef') for i in inputs)
    rows = []
    for rule in _children(table, 'rule'):
        entries = tuple(_parse_entry(next(c for c in e if _local(c.tag) == 'text').text)
                        for e in _children(rule, 'inputEntry'))
        output = next(c for c in _children(rule, 'outputEntry')[0] if _local(c.tag) == 'text').text.strip()
        rows.append((entries, output[1:-1] if output.startswith('"') and output.endswith('"') else output))
    return names, types, rows, table.get('hitPolicy')


def _match(entry, value):
    if entry is None:
        return True
    if isinstance(entry, str) and entry.startswith('>='):
        return _num(value) >= int(entry[2:])
    if isinstance(entry, int):
        return _num(value) == entry
    return value == entry


def _num(value):
    return int(value) if isinstance(value, str) and re.fullmatch(r'-?\d+', value) else value


def evaluate_definitions(source, env):
    """First-match evaluation of a <definitions> element: the output string of the first rule that matches."""
    names, _, rows, _ = parse_definitions(source)
    for entries, output in rows:
        if all(_match(e, env[n]) for n, e in zip(names, entries)):
            return output
    return None


# ---------------------------------------------------------------------------------------------------------------
# Evaluator for the compiled expression. Grammar (exactly what compile_table writes):
#   expr := '(' 'If' '(' cond ')' 'THEN' '(' STRING ')' 'ELSE' '(' (expr | 'null') ')' ')'
#   cond := 'true' | '(' NAME ('=' | '>') (STRING | INT) ')' | '(' cond ('AND' | 'OR') cond ')'

_TOKEN = re.compile(r'\s*("[^"]*"|-?\d+|[A-Za-z_][A-Za-z0-9_:]*|[()=>])')


def _tokens(text):
    out, pos, text = [], 0, text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError('cannot tokenize at %r' % text[pos:pos + 20])
        out.append(m.group(1))
        pos = m.end()
    return out


class _Parser:
    def __init__(self, text):
        self.t, self.i = _tokens(text), 0

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else None

    def take(self, expected=None):
        tok = self.peek()
        if tok is None or (expected is not None and tok != expected):
            raise ValueError('expected %r, got %r at token %d' % (expected, tok, self.i))
        self.i += 1
        return tok

    def expr(self):
        self.take('(')
        self.take('If')
        self.take('(')
        cond = self.cond()
        self.take(')')
        self.take('THEN')
        self.take('(')
        out = self.take()
        if not (out.startswith('"') and out.endswith('"')):
            raise ValueError('output must be a string literal, got %r' % out)
        self.take(')')
        self.take('ELSE')
        self.take('(')
        if self.peek() == 'null':
            self.take()
            rest = None
        else:
            rest = self.expr()
        self.take(')')
        self.take(')')
        return ('if', cond, out[1:-1], rest)

    def cond(self):
        if self.peek() == 'true':
            self.take()
            return ('true',)
        self.take('(')
        if self.peek() != 'true' and self.peek(1) in ('=', '>'):
            name, op, rhs = self.take(), self.take(), self.take()
            self.take(')')
            value = rhs[1:-1] if rhs.startswith('"') else int(rhs)
            return ('cmp', name, op, value)
        left = self.cond()
        op = self.take()
        if op not in ('AND', 'OR'):
            raise ValueError('expected AND or OR, got %r' % op)
        right = self.cond()
        self.take(')')
        return (op.lower(), left, right)


def parse_compiled(text):
    p = _Parser(text)
    tree = p.expr()
    if p.peek() is not None:
        raise ValueError('trailing tokens after the expression')
    return tree


def _cond_value(node, env):
    kind = node[0]
    if kind == 'true':
        return True
    if kind == 'cmp':
        _, name, op, rhs = node
        value = env[name]
        if isinstance(rhs, int):
            value = _num(value)
        return value == rhs if op == '=' else value > rhs
    left, right = _cond_value(node[1], env), _cond_value(node[2], env)
    return (left and right) if kind == 'and' else (left or right)


def evaluate_compiled(text, env):
    """Result of the compiled expression for `env` (input name -> value); None when no rule matches."""
    node = parse_compiled(text) if isinstance(text, str) else text
    while node is not None:
        _, cond, out, rest = node
        if _cond_value(cond, env):
            return out
        node = rest
    return None
