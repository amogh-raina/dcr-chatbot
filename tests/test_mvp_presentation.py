import copy
import unittest
from unittest.mock import patch
import faq_runtime as faq

def payload():
 def e(id,tags,label,options='',**state):
  return dict(id=id,tags=tags,label=label,choiceValues=options,dataType='choice' if options else 'label',enabled=True,included=True,pending=False,executed=None,**state)
 p={'events':[
  e('directory','FAQHome FAQTopicMenu','Choose a topic','Documentation (3), Proceed to application (6)'),
  e('catalogue','GlobalInterpreter','Ask any question','Medical records? (50), Translations? (90)'),
  e('medical_menu','FAQTopicMenu FAQHideRead FAQTopic:3','Here are some questions about documentation.','Medical records? (1), Translations? (2), Back to topics (0)'),
  e('record_answer','FAQAnswer FAQTopic:3','Medical records?'),
  e('translation_answer','FAQAnswer FAQTopic:3','Translations?'),
  e('done','FAQTopicMenu FAQTopicExplored FAQTopic:3','You’ve explored all questions in this topic.','Review questions (1), Back to topics (0)')]}
 p['events'][2]['pending']=True
 return p

class MVPPresentationTests(unittest.TestCase):
 def test_read_answer_hidden_but_global_catalogue_preserved(self):
  p=payload();p['events'][3]['executed']='2026-09-13T14:00:00Z'
  result=faq.view({},p)
  self.assertEqual([c['value'] for c in result['navigation'][0]['options']],['2','0'])
  self.assertEqual(len(faq.catalogue(p)),2)
  self.assertEqual(result['topic_name'],'Documentation')
 def test_review_restores_both_questions_without_resetting_history(self):
  p=payload()
  for i in (3,4,5):p['events'][i]['executed']='timestamp'
  p['events'][5]['value']='1'
  self.assertEqual(len(faq.navigation(p)[0]['options']),3)
  self.assertEqual(p['events'][3]['executed'],'timestamp')
 def test_completed_message_requires_dcr_pending_explored_event(self):
  p=payload()
  for i in (3,4):p['events'][i]['executed']='timestamp'
  self.assertFalse(faq.view({},p)['topic_explored'])
  p['events'][2]['pending']=False;p['events'][5]['pending']=True
  self.assertTrue(faq.view({},p)['topic_explored'])
 def test_hidden_old_question_button_is_rejected(self):
  p=payload();p['events'][3]['executed']='timestamp'
  with patch.object(faq.repo,'get_raw_events',return_value=p),patch.object(faq.repo,'execute_event') as write:
   with self.assertRaises(faq.StateError):faq.handle({},dict(event_id='medical_menu',value='1'))
   write.assert_not_called()
 def test_answer_has_topic_heading_metadata_without_repetitive_followup(self):
  p=payload();pending=copy.deepcopy(p);after=copy.deepcopy(p)
  pending['events'][2]['pending']=False;pending['events'][3]['pending']=True
  pending['events'][3]['description']='<p>Verbatim answer.</p>'
  after['events'][3]['executed']='timestamp'
  candidate=faq.choices(p['events'][2])[0]
  with patch.object(faq.repo,'execute_event',return_value=True),patch.object(faq.repo,'get_raw_events',side_effect=[pending,after]):
   result=faq.execute({},candidate,p)
  self.assertEqual(result['answer'],'<p>Verbatim answer.</p>')
  self.assertNotIn('follow_up',result)
  self.assertEqual(result['topic_name'],'Documentation')
  self.assertFalse(result['topic_explored'])
  self.assertEqual([c['value'] for c in result['navigation'][0]['options']],['2','0'])
