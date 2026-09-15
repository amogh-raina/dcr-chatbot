"""Focused demo integration using an offline DCR marking fixture, not live DCR."""
import re
import unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as E
from flask import Flask
import application_runtime as runtime

class Model:
 def __init__(self):
  r=E.parse(Path(__file__).resolve().parents[1]/'xml graphs/SU_handicaptillaeg_FAQ_Application_Demo.xml').getroot()
  self.events={e.get('id'):e for e in r.findall('./specification/resources/events//event')}
  self.labels={m.get('eventId'):m.get('labelId') for m in r.findall('./specification/resources/labelMappings/labelMapping')}
  self.expr={e.get('id'):e.get('value') for e in r.findall('./specification/resources/expressions/expression')}
  self.con=r.find('./specification/constraints');self.values={};self.executed=set()
  self.included={e.get('id') for e in r.findall('./runtime/marking/included/event')};self.pending={e.get('id') for e in r.findall('./runtime/marking/pendingResponses/event')}
 def guard(self,r):
  x=self.expr.get(r.get('expressionId'),'True')
  x=re.sub(r'([\w:]+)@executed',lambda m:str(m[1] in self.executed),x)
  x=re.sub(r'([\w:]+)\s*(!=|=)\s*(true|false|\d+)',lambda m:str((self.values.get(m[1])==m[3]) if m[2]=='=' else (self.values.get(m[1])!=m[3])),x)
  if re.sub(r'True|False|and|or|not|[()\s]','',x):raise AssertionError(x)
  return eval(x,{'__builtins__':{}},{})
 def enabled(self,key):
  return key in self.included and all(r.get('sourceId') not in self.included or r.get('sourceId') in self.executed for r in self.con.findall('./conditions/condition') if r.get('targetId')==key and self.guard(r)) and all(not(r.get('sourceId') in self.included and r.get('sourceId') in self.pending) for r in self.con.findall('./milestones/milestone') if r.get('targetId')==key and self.guard(r))
 def execute(self,state,key,value):
  assert self.enabled(key),key
  self.values[key]=value
  effects={s:[r.get('targetId') for r in self.con.find(s) if r.get('sourceId')==key and self.guard(r)] for s in ['responses','coresponses','includes','excludes']}
  self.executed.add(key);self.pending.discard(key)
  self.pending.difference_update(effects['coresponses']);self.pending.update(effects['responses'])
  self.included.difference_update(effects['excludes']);self.included.update(effects['includes'])
  return True
 def payload(self,state=None):
  return {'events':[dict(id=k,label=self.labels[k],dataType=e.findtext('./custom/eventData/dataType',''),tags=','.join(g.text or '' for g in e.findall('./custom/groups/group')),choiceValues=', '.join(f"{i.get('label')} ({i.get('value')})" for i in e.findall('./custom/eventData/dictionary/item')),included=k in self.included,enabled=self.enabled(k),pending=k in self.pending,executed=k in self.executed,value=self.values.get(k)) for k,e in self.events.items()]}

class ApplicationTests(unittest.TestCase):
 def setUp(self):
  self.model=Model();self.state={}
  self.read=patch.object(runtime.repo,'get_raw_events',side_effect=self.model.payload).start()
  self.write=patch.object(runtime.repo,'execute_raw_event',side_effect=self.model.execute).start();self.addCleanup(patch.stopall)
 def run_path(self,overrides):
  result=runtime.start(self.state);seen=[]
  default={'A1_1':'2026-10-01','A2':'Fictional impairment','Impairment_type':'1','Time_limited':'false','Prev_work':'false','Plan_work_studies':'false','Samtykke':'true','A5':'statement.pdf','A11':'records.pdf','A10':'send','Impairment_definition':'1','A14':'false','A17':'true','A15':'4.5','A16':'3'}
  for _ in range(20):
   if result['status'] in ('complete','declined'):return result,seen
   key=result['field']['id'].split(':')[1];seen.append(key)
   result=runtime.answer(self.state,dict(prompt_id=result['prompt_id'],value=overrides.get(key,default[key])))
  self.fail('Application did not terminate')
 def test_congenital_and_no_previous_work_still_asks_planned_work(self):
  result,seen=self.run_path({})
  self.assertEqual(result['status'],'complete');self.assertIn('Plan_work_studies',seen);self.assertNotIn('A15',seen)
  self.assertIn('e-Boks',result['response']);self.assertIn('Nothing was submitted',result['demo_notice'])
 def test_acquired_permanent_and_work(self):
  result,seen=self.run_path({'Impairment_type':'2','Prev_work':'true','Plan_work_studies':'true'})
  self.assertEqual(result['status'],'complete');self.assertIn('A16',seen);self.assertNotIn('A14',seen)
 def test_uncertain_impairment_extension_and_declined_consent(self):
  result,seen=self.run_path({'Impairment_type':'2','Impairment_definition':'3','Time_limited':'true','Samtykke':'false'})
  self.assertEqual(result['status'],'declined');self.assertIn('A14',seen);self.assertIn('A17',seen);self.assertNotIn('A10',seen)
 def test_forged_prompt_and_invalid_date_do_not_execute(self):
  result=runtime.start(self.state);self.write.reset_mock()
  for data in [dict(prompt_id='forged',value='2026-10-01'),dict(prompt_id=result['prompt_id'],value='2026-02-30')]:
   with self.assertRaises(runtime.ApplicationError):runtime.answer(self.state,data)
  self.write.assert_not_called()
 def test_replay_does_not_execute_twice(self):
  result=runtime.start(self.state);data=dict(prompt_id=result['prompt_id'],value='2026-10-01');runtime.answer(self.state,data);self.write.reset_mock()
  with self.assertRaises(runtime.ApplicationError):runtime.answer(self.state,data)
  self.write.assert_not_called()
 def test_entry_requires_demo_continue(self):
  app=Flask(__name__);runtime.install(app,{},lambda:{})
  response=app.test_client().post('/application/init',json={'graph_id':'1'},headers={'X-Session-ID':'demo'})
  self.assertEqual(response.status_code,400)
 def test_numeric_and_file_validation(self):
  with self.assertRaises(runtime.ApplicationError):runtime.validated(dict(type='float',hours=True),'nan')
  with self.assertRaises(runtime.ApplicationError):runtime.validated(dict(type='float',hours=True),'169')
  with self.assertRaises(runtime.ApplicationError):runtime.validated(dict(type='demo_file'),'/secret/file.pdf')
  self.assertEqual(runtime.validated(dict(type='demo_file'),'fictional.pdf')[0],'fictional.pdf')

 def test_form_api_without_pending_flags_can_complete(self):
  def payload_without_pending(state):
   payload=self.model.payload(state)
   for event in payload['events']:
    if event['id'].startswith('Form0:'):event['pending']=False
   return payload
  self.read.side_effect=payload_without_pending
  result,seen=self.run_path({})
  self.assertEqual(result['status'],'complete')
  self.assertEqual(seen[0],'A1_1')
  self.assertIn('A10',seen)
 def test_nonpending_fallback_rejects_multiple_available_fields(self):
  runtime.start(self.state)
  payload=self.model.payload()
  for event in payload['events']:
   event['pending']=False
   if event['id']=='Form0:A2':event.update(included=True,enabled=True)
  self.write.reset_mock()
  with self.assertRaises(runtime.ApplicationError):runtime.view(self.state,payload)
  self.write.assert_not_called()
 def test_nonpending_fallback_does_not_select_excluded_or_disabled_field(self):
  for flags in [dict(included=False),dict(enabled=False)]:
   payload=self.model.payload()
   for event in payload['events']:
    event['pending']=False
    if event['id']=='Form0:A1_1':
     event.update(included=True,enabled=True)
     event.update(flags)
   with self.assertRaises(runtime.ApplicationError):runtime.view(self.state,payload)
