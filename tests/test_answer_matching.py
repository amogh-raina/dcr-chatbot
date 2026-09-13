"""Small mocked-API check for the experimental answer-first graph."""
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import faq_runtime as faq
import openchat
from test_topic_exploration import Marking, TOPICS

GRAPH=Path(__file__).resolve().parents[1]/'xml graphs/SU_handicaptillaeg_FAQ_AnswerMatching.xml'

def row(key,score=.94):return {'candidate_key':key,'score':score,'reason':'The modeled answer addresses the request'}

class AnswerMatchingTests(unittest.TestCase):
    def setUp(self):
        self.model=Marking(GRAPH)
        self.state={'faq_mode':True}
        self.read=patch.object(faq.repo,'get_raw_events',side_effect=lambda state:self.model.payload()).start()
        self.write=patch.object(faq.repo,'execute_event',side_effect=lambda state,id,value,comment:self.model.execute(id,value)).start()
        self.rank=patch.object(openchat,'rank',return_value=('single_match',[row('FAQ_GlobalQuestion:7')])).start()
        self.addCleanup(patch.stopall)

    def ask(self):return faq.handle(self.state,{'message':'What medical documentation do I have to submit?'})
    def feedback(self,result,value):return faq.handle(self.state,dict(action='feedback',feedback_id=result['feedback_id'],value=value))

    def test_strong_match_delivers_verbatim_answer_then_no_opens_full_topic(self):
        result=self.ask()
        self.assertEqual(result['status'],'answer')
        self.assertEqual(result['answer'],self.model.nodes['FAQ_Answer_7'].findtext('./custom/eventDescription'))
        self.assertNotIn('match_id',result)
        self.assertEqual(result['follow_up'],'Did this answer your question?')
        self.assertTrue(result['suppress_suggestions'])
        self.assertEqual(self.model.pending,{'FAQ_Feedback_3'})
        self.assertEqual({c['label'] for c in result['feedback']},{'Yes','No'})
        self.assertIn('answer',self.rank.call_args.args[2][0])
        no=self.feedback(result,'0')
        self.assertEqual(no['event_id'],'FAQ_Menu_3')
        options=no['navigation'][0]['options']
        self.assertEqual(len(options),4) # All three questions, including read one, plus Back.
        self.assertFalse(no.get('suppress_suggestions'))
        self.assertIn('FAQ_Answer_7',self.model.executed)

    def test_all_topics_yes_ready_and_completed_topic_reentry(self):
        for topic,numbers in TOPICS.items():
            with self.subTest(topic=topic):
                self.model=Marking(GRAPH);self.state={'faq_mode':True}
                for number in numbers:
                    self.rank.return_value=('single_match',[row(f'FAQ_GlobalQuestion:{number}')])
                    result=self.ask()
                    self.assertEqual(self.model.pending,{f'FAQ_Feedback_{topic}'})
                    ready=self.feedback(result,'1')
                    self.assertEqual(ready['response'],'Feel free to ask me anything else.')
                    self.assertTrue(ready['suppress_suggestions'])
                    self.assertEqual(self.model.pending,{'FAQ_Ready'})
                faq.handle(self.state,dict(event_id='FAQ_Home',value=str(topic)))
                self.assertEqual(self.model.pending,{f'FAQ_Explored_{topic}'})

    def test_typed_feedback_single_use_and_stale_tokens(self):
        result=self.ask()
        no=faq.handle(self.state,{'message':'No'})
        self.assertEqual(no['event_id'],'FAQ_Menu_3')
        with self.assertRaises(faq.StateError):self.feedback(result,'0')
        result=self.ask()
        self.model.execute('FAQ_Home','2')
        count=self.write.call_count
        with self.assertRaises(faq.StateError):self.feedback(result,'1')
        self.assertEqual(self.write.call_count,count)

    def test_ambiguous_or_no_match_never_autoexecutes(self):
        self.rank.return_value=('ambiguous',[row('FAQ_GlobalQuestion:7',.6),row('FAQ_GlobalQuestion:8',.58)])
        result=self.ask()
        self.assertEqual(result['status'],'clarify_match');self.write.assert_not_called()
        answer=faq.handle(self.state,dict(action='confirm',match_id=result['match_id'],candidate_key='FAQ_GlobalQuestion:8'))
        self.assertEqual(answer['answer_event_id'],'FAQ_Answer_8')
        self.write.reset_mock();self.rank.return_value=('no_match',[])
        self.assertEqual(self.ask()['status'],'no_match');self.write.assert_not_called()

    def test_missing_duplicate_links_and_nonconventional_event_ids(self):
        payload=self.model.payload()
        answer=next(e for e in payload['events'] if e['id']=='FAQ_Answer_7')
        candidate=next(c for c in faq.catalogue(payload) if c['value']=='7')
        answer['id']='arbitrary_medical_evidence_event'
        self.assertEqual(faq.linked_answer(candidate,payload)['id'],answer['id'])
        duplicate=copy.deepcopy(answer);duplicate['id']='another'
        payload['events'].append(duplicate)
        with self.assertRaises(faq.StateError):faq.matching_catalogue(payload,faq.catalogue(payload))
        payload['events'].pop();answer['tags']='FAQAnswer FAQTopic:3'
        self.read.side_effect=lambda state:payload
        self.assertEqual(self.ask()['error_code'],'configuration_error')
        self.write.assert_not_called();self.rank.assert_not_called()

    def test_application_placeholder_remains_available(self):
        home=next(e for e in self.model.payload()['events'] if 'FAQHome' in faq.groups(e))
        choice=next(c for c in faq.choices(home) if c['question']=='Proceed to application')
        result=faq.handle(self.state,dict(event_id=choice['event_id'],value=choice['value']))
        self.assertEqual(result['status'],'answer')
        self.assertNotIn('error_code',result)
        self.rank.assert_not_called()

    def test_changed_state_during_matching_prevents_execution(self):
        def mutate(*args):
            self.model.execute('FAQ_Home','2')
            return 'single_match',[row('FAQ_GlobalQuestion:7')]
        self.rank.side_effect=mutate
        with self.assertRaises(faq.StateError):self.ask()
        self.write.assert_not_called()

    def test_wrong_pending_answer_is_not_displayed_or_acknowledged(self):
        def wrong(state,id,value,comment):
            self.model.execute(id,value)
            self.model.pending={'FAQ_Answer_8'}
            return True
        self.write.side_effect=wrong
        with self.assertRaisesRegex(faq.StateError,'disagrees'):self.ask()
        self.assertEqual(self.write.call_count,1)

class PairPayloadTests(unittest.TestCase):
    def test_sdk_receives_only_question_answer_pair_and_structured_rank_schema(self):
        client=Mock()
        client.responses.create.return_value=SimpleNamespace(status='completed',output_text=json.dumps({'ranked_matches':[row('catalogue:abc')]}),usage=None)
        candidate=dict(candidate_key='catalogue:abc',question='Required evidence?',answer='<p>Recent hospital records.</p>',credentials='MUST NOT SEND')
        decision,_=openchat.rank('Hospital records?',None,[candidate],client=client)
        self.assertEqual(decision,'single_match')
        request=client.responses.create.call_args.kwargs
        sent=json.loads(request['input'])['candidates'][0]
        self.assertEqual(sent,dict(candidate_key='catalogue:abc',question='Required evidence?',answer='<p>Recent hospital records.</p>'))
        self.assertTrue(request['text']['format']['strict']);self.assertFalse(request['store'])

if __name__=='__main__':unittest.main()
