import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import openchat
import faq_runtime as faq
import dcr_repository as repo
import app


def event(id, group, choices='', pending=False, description=''):
    return dict(id=id, label=id, groups=group, choiceValues=choices,
                dataType='choice' if choices else 'label', enabled=True,
                included=True, pending=pending, executed=False, description=description)


def initial():
    return {'events': [event('home', 'FAQHome FAQTopicMenu', 'Topic (1)', True),
        event('global', 'GlobalInterpreter', 'Medical documents? (7), Diagnosis enough? (3), Contact authority? (99)'),
        event('topic', 'FAQTopicMenu', 'Medical documents? (1), Back (0)'),
        event('answer', 'FAQAnswer', description='<p>Exact DCR answer.</p>'),
        dict(event('contact', 'FAQAnswer FallbackContact'), label='Contact authority?')]}


def row(key='global:7', score=.94):
    return dict(candidate_key=key, score=score, reason='Intent matches')


class MatcherTests(unittest.TestCase):
    def test_catalogue_is_api_only_and_reusable(self):
        p=initial();p['events'][1]['executed']=True
        self.assertEqual(len(faq.catalogue(p)),3)
        self.assertEqual(set(faq.catalogue(p)[0]), {'candidate_key','event_id','value','question'})
        with patch.object(repo.ET,'fromstring',side_effect=AssertionError('XML accessed')):
            self.assertIs(repo._prepare_event_payload({'graph_xml':'forbidden'}, p),p)

    def test_repository_tags_are_api_group_metadata(self):
        payload=initial()
        for e in payload['events']:e['tags']=e.pop('groups')
        self.assertTrue(faq.is_faq(payload))
        self.assertEqual(len(faq.catalogue(payload)),3)
        self.assertEqual(len(faq.navigation(payload)),1)

    def test_selector_configuration(self):
        for mutate in [lambda p:p['events'].pop(1), lambda p:p['events'].append(p['events'][1]),
                       lambda p:p['events'][1].update(enabled=False)]:
            p=initial();mutate(p)
            with self.assertRaises(faq.StateError):faq.catalogue(p)

    def test_choices_parentheses_and_duplicates(self):
        self.assertEqual(faq.choices(event('x','', 'What about work (part-time)? (a)'))[0]['question'], 'What about work (part-time)?')
        with self.assertRaises(faq.StateError):faq.choices(event('x','','A (1), B (1)'))

    def test_score_and_margin_boundaries(self):
        for scores, expected in [([.49],'no_match'),([.5],'ambiguous'),([.8,.68],'single_match'),
                                 ([.8,.681],'ambiguous'),([.799],'ambiguous'),([1],'single_match')]:
            rows=[row(str(i),v) for i,v in enumerate(scores)]
            self.assertEqual(openchat.decide(rows,openchat.Settings())[0],expected)

    def test_invalid_rankings(self):
        bad=[{}, {'ranked_matches':[row('unknown')]},
             {'ranked_matches':[row(),row()]}, {'ranked_matches':[row(score=float('nan'))]},
             {'ranked_matches':[row(score=float('inf'))]}, {'ranked_matches':[row(score=-.1)]},
             {'ranked_matches':[row(score=1.1)]}, {'ranked_matches':[row(score=True)]},
             {'ranked_matches':[row(score='0.9')]}]
        for raw in bad:
            with self.subTest(raw=raw),self.assertRaises(openchat.MatchError):
                openchat.validate_ranking(dict(in_scope=True, scope_reason='Relevant', **raw),{'global:7'})

    def test_sdk_payload_context_schema_and_retry(self):
        client=Mock();client.responses.create.side_effect=[
            SimpleNamespace(status='completed',output_text='bad'),
            SimpleNamespace(status='completed',output_text=json.dumps({'in_scope':True, 'scope_reason':'Relevant follow-up', 'ranked_matches':[row()]}),usage=None)]
        candidates=faq.catalogue(initial());candidates[0]['description']='FORBIDDEN ANSWER'
        self.assertEqual(openchat.rank('What about that?', 'Diagnosis enough?', candidates,client)[0], 'single_match')
        self.assertEqual(client.responses.create.call_count,2)
        args=client.responses.create.call_args.kwargs
        payload=json.loads(args['input'])
        self.assertEqual(payload['context'],{'last_confirmed_question':'Diagnosis enough?'})
        self.assertEqual(len(payload['candidates']),3)
        self.assertNotIn('FORBIDDEN',args['input'])
        self.assertEqual(set(payload['candidates'][0]),{'candidate_key','question'})
        self.assertFalse(args['store']);self.assertTrue(args['text']['format']['strict'])

    def test_provider_timeout_and_malformed_stop(self):
        for response in [TimeoutError(),SimpleNamespace(status='incomplete',output_text='')]:
            client=Mock()
            if isinstance(response,Exception):client.responses.create.side_effect=response
            else:client.responses.create.return_value=response
            with self.assertRaises(openchat.MatchError):openchat.rank('x',None,faq.catalogue(initial()),client)
            self.assertEqual(client.responses.create.call_count,1 if isinstance(response,Exception) else 2)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.payload=initial();self.state={'faq_mode':True,'api_key':'test'}
        self.read=patch.object(repo,'get_raw_events',side_effect=lambda s:copy.deepcopy(self.payload)).start()
        self.write=patch.object(repo,'execute_event',return_value=True).start()
        self.rank=patch.object(openchat,'rank',return_value=('single_match',[row()])).start()
        self.legacy=patch.object(app.chatnlp,'create_chat',side_effect=AssertionError('legacy')).start()
        self.addCleanup(patch.stopall)

    def suggest(self):return faq.handle(self.state,{'message':'minimal medical documentation?'})
    def confirmation(self,result,key='global:7'):
        return {'action':'confirm','match_id':result['match_id'],'candidate_key':key}
    def transition(self,id,value,comment):
        for e in self.payload['events']:e['pending']=False
        if id in ('global','topic'):
            self.payload['events'][3]['pending']=True
        elif id=='answer':self.payload['events'][2]['pending']=True
        elif id=='home':self.payload['events'][2]['pending']=True
        return True

    def test_strong_confirmation_answer_acknowledgement(self):
        result=self.suggest();self.write.assert_not_called()
        self.assertEqual(result['status'],'confirm_match');self.assertNotIn('score',str(result))
        self.write.side_effect=lambda state,id,value,comment:self.transition(id,value,comment)
        answer=faq.handle(self.state,self.confirmation(result))
        self.assertEqual(answer['answer'],'<p>Exact DCR answer.</p>')
        self.assertEqual(answer['event_id'],'topic')
        self.assertEqual([c.args[1:3] for c in self.write.call_args_list],[('global','7'),('answer','')])
        self.assertEqual(self.state['last_confirmed_question'],'Medical documents?')
        with self.assertRaises(faq.StateError):faq.handle(self.state,self.confirmation(result))

    def test_ambiguity_only_selected_issued_candidate(self):
        self.rank.return_value=('ambiguous',[row('global:7',.6),row('global:3',.58),row('global:99',.52)])
        result=self.suggest();self.assertEqual(len(result['candidates']),3);self.write.assert_not_called()
        self.write.side_effect=lambda state,id,value,comment:self.transition(id,value,comment)
        faq.handle(self.state,self.confirmation(result,'global:3'))
        self.assertEqual(self.write.call_args_list[0].args[1:3],('global','3'))

    def test_reject_and_no_match_do_not_execute(self):
        result=self.suggest();faq.handle(self.state,{'action':'reject','match_id':result['match_id']})
        self.rank.return_value=('no_match',[]);result=self.suggest()
        self.assertIn('contact',[a['action'] for a in result['actions']]);self.write.assert_not_called()

    def test_forged_and_stale_confirmation(self):
        result=self.suggest()
        with self.assertRaises(faq.StateError):faq.handle(self.state,self.confirmation(result,'global:99'))
        result=self.suggest();self.payload['events'][0]['value']='changed'
        with self.assertRaises(faq.StateError):faq.handle(self.state,self.confirmation(result))
        self.write.assert_not_called()

    def test_fresh_choice_removed_or_disabled(self):
        for mutation in [dict(enabled=False),dict(choiceValues='Diagnosis enough? (3)')]:
            self.payload=initial();result=self.suggest();self.payload['events'][1].update(**mutation)
            with self.assertRaises(faq.StateError):faq.handle(self.state,self.confirmation(result))
        self.write.assert_not_called()

    def test_topic_and_question_buttons_skip_ai(self):
        self.write.side_effect=lambda state,id,value,comment:self.transition(id,value,comment)
        result=faq.handle(self.state,{'event_id':'home','value':'1'})
        self.assertEqual(result['status'],'navigation')
        result=faq.handle(self.state,{'event_id':'topic','value':'1'})
        self.assertEqual(result['status'],'answer');self.rank.assert_not_called()

    def test_global_button_cannot_bypass_confirmation(self):
        with self.assertRaises(faq.StateError):faq.handle(self.state,{'event_id':'global','value':'7'})
        self.write.assert_not_called()

    def test_cross_topic_uses_complete_catalogue(self):
        self.state['last_confirmed_question']='Medical documents?'
        self.payload['events'][0]['pending']=False;self.payload['events'][2]['pending']=True
        faq.handle(self.state,{'message':'Is a diagnosis enough?'})
        self.assertEqual(len(self.rank.call_args.args[2]),3)
        self.assertEqual(self.rank.call_args.args[1],'Medical documents?')

    def test_outage_keeps_buttons_without_legacy(self):
        self.rank.side_effect=openchat.MatchError('offline')
        result=self.suggest();self.assertEqual(result['status'],'no_match')
        self.assertTrue(result['navigation']);self.write.assert_not_called();self.legacy.assert_not_called()

    def test_configuration_fallback(self):
        self.payload['events'][1]['enabled']=False
        self.assertEqual(self.suggest()['error_code'],'configuration_error')
        self.rank.assert_not_called();self.write.assert_not_called()

    def test_multiple_pending_answers_do_not_get_acknowledged(self):
        result=self.suggest();self.payload['events'][3]['pending']=True;self.payload['events'][4]['pending']=True
        # Snapshot is issued before the choice and engine returns broken answer state.
        self.payload=initial();result=self.suggest()
        def broken(*args):
            self.payload['events'][0]['pending']=False
            self.payload['events'][3]['pending']=True;self.payload['events'][4]['pending']=True
            return True
        self.write.side_effect=broken
        with self.assertRaises(faq.StateError):faq.handle(self.state,self.confirmation(result))
        self.assertEqual(self.write.call_count,1)

    def test_raw_execution_does_not_read_xml(self):
        with patch.object(repo.ET,'fromstring',side_effect=AssertionError('XML')),patch.object(repo._session,'post',return_value=Mock(status_code=204)) as post:
            self.assertTrue(repo.execute_raw_event(dict(root_url='https://example/',graph_id=1,simulation_id=2,api_key='test'),'global','7'))
            self.assertEqual(post.call_args.kwargs['json']['eventValue'],'7')

    def test_flask_faq_init_does_not_create_chat(self):
        from xml.etree.ElementTree import Element
        app.tab_sessions.clear()
        with patch.object(repo,'get_graph',return_value=Element('dcrgraph',title='FAQ')),patch.object(repo,'create_simulation',return_value=1),patch.object(repo,'get_events',return_value=self.payload),patch.object(app,'parse_graph_for_review'):
            response=app.app.test_client().post('/init',headers={'X-Session-ID':'faq'},json={'graph_id':'1'})
        self.assertEqual(response.status_code,200);self.assertTrue(response.json['faq']);self.legacy.assert_not_called()


if __name__=='__main__':unittest.main()
