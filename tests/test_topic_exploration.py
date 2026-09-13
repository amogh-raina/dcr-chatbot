"""Focused offline checks; this small model is not a DCR import validator."""
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import faq_runtime as runtime

GRAPH = Path(__file__).resolve().parents[1] / 'xml graphs/SU_handicaptillaeg_FAQ_MVP.xml'
TOPICS = {1: [1,2,3], 2: [4,5,6], 3: [7,8,9], 4: [10,11,15,16,17], 5: [12,13,14]}

class Marking:
    def __init__(self, graph=GRAPH):
        root = ET.parse(graph).getroot()
        resources = root.find('./specification/resources')
        self.nodes = {e.get('id'): e for e in resources.findall('./events/event')}
        self.labels = {e.get('eventId'): e.get('labelId') for e in resources.findall('./labelMappings/labelMapping')}
        self.expressions = {e.get('id'): e.get('value') for e in resources.findall('./expressions/expression')}
        self.constraints = root.find('./specification/constraints')
        self.pending = {e.get('id') for e in root.findall('./runtime/marking/pendingResponses/event')}
        self.executed, self.values = set(), {}

    def guard(self, relation):
        text = self.expressions.get(relation.get('expressionId'), 'True')
        text = re.sub(r'(\w+)@executed', lambda m: str(m[1] in self.executed), text)
        text = re.sub(r'(\w+)\s*(!=|=)\s*(\d+)', lambda m: str((self.values.get(m[1]) == m[3]) if m[2] == '=' else (self.values.get(m[1]) != m[3])), text)
        # Only evaluate the deliberately small boolean subset used by this graph.
        if re.sub(r'True|False|and|or|not|[()\s]', '', text):
            raise AssertionError('Unsupported test guard: ' + text)
        return eval(text, {'__builtins__': {}}, {})

    def enabled(self, event):
        return all(r.get('sourceId') in self.executed for r in self.constraints.findall('./conditions/condition') if r.get('targetId') == event and self.guard(r))

    def execute(self, event, value=''):
        assert self.enabled(event), event
        self.values[event] = str(value)
        # Guards evaluated before source is marked executed, deliberately.
        effects = {section: [r.get('targetId') for r in self.constraints.findall('./'+section+'/*') if r.get('sourceId') == event and self.guard(r)] for section in ('responses','coresponses')}
        self.executed.add(event)
        self.pending.discard(event)
        self.pending.difference_update(effects['coresponses'])
        self.pending.update(effects['responses'])
        return True

    def payload(self):
        return {'events': [dict(id=id, label=self.labels[id], description=e.findtext('./custom/eventDescription'),
             tags=','.join(g.text for g in e.findall('./custom/groups/group')),
             choiceValues=', '.join(f"{x.get('label')} ({x.get('value')})" for x in e.findall('./custom/eventData/dictionary/item')),
             dataType='choice' if e.findall('./custom/eventData/dictionary/item') else '',
             included=True, enabled=self.enabled(id), pending=id in self.pending,
             executed='timestamp' if id in self.executed else None, value=self.values.get(id)) for id,e in self.nodes.items()]}

class TopicExplorationTests(unittest.TestCase):
    def answer(self, model, event, value):
        payload = model.payload()
        candidate = next(c for c in runtime.choices(next(e for e in payload['events'] if e['id']==event)) if (c['question']==model.labels[f'FAQ_Answer_{value}'] if event.startswith('FAQ_Menu_') else c['value']==str(value)))
        with patch.object(runtime.repo, 'execute_event', side_effect=lambda state,id,v,ignored: model.execute(id,v)), patch.object(runtime.repo, 'get_raw_events', side_effect=lambda state: model.payload()):
            return runtime.execute({}, candidate, payload)

    def test_all_topics_finish_revisit_review_and_switch(self):
        for topic, answers in TOPICS.items():
            with self.subTest(topic=topic):
                model=Marking()
                menu=f'FAQ_Menu_{topic}'
                done=f'FAQ_Explored_{topic}'
                self.assertFalse(model.enabled(done))
                model.execute('FAQ_Home', topic)
                for index, number in enumerate(answers):
                    result=self.answer(model, menu, number)
                    self.assertEqual(result['answer_event_id'], f'FAQ_Answer_{number}')
                    self.assertNotIn('error_code', result)
                    if index < len(answers)-1:
                        self.assertEqual(model.pending, {menu})
                        shown=runtime.navigation(model.payload())[0]['options']
                        self.assertNotIn(model.labels[f'FAQ_Answer_{number}'], [c['question'] for c in shown])
                        self.assertFalse(model.enabled(done))
                self.assertEqual(model.pending, {done})
                self.assertTrue(result['topic_explored'])
                self.assertIn('You’ve explored all questions', result['follow_up'])
                model.execute(done, 0)
                self.assertEqual(model.pending, {'FAQ_Home'})
                model.execute('FAQ_Home', topic)
                self.assertEqual(model.pending, {done})
                history=set(model.executed)
                model.execute(done, 1)
                self.assertEqual(model.pending, {menu})
                options=runtime.navigation(model.payload())[0]['options']
                self.assertTrue({model.labels[f'FAQ_Answer_{n}'] for n in answers} <= {c['question'] for c in options})
                self.assertTrue(history <= model.executed)
                self.answer(model, menu, answers[0])
                self.assertEqual(model.pending, {done})
                other=next(n for n in TOPICS if n!=topic)
                self.answer(model, 'FAQ_GlobalQuestion', TOPICS[other][0])
                self.assertEqual(model.pending, {f'FAQ_Menu_{other}'})

    def test_empty_suggestions_do_not_invent_completion(self):
        model=Marking()
        model.execute('FAQ_Home', 1)
        model.executed.update(f'FAQ_Answer_{n}' for n in TOPICS[1])
        result=runtime.view({}, model.payload())
        self.assertFalse(result['topic_explored'])
        self.assertEqual(result['event_id'], 'FAQ_Menu_1')

if __name__ == '__main__':
    unittest.main()
