import copy
import json
import os
import tempfile
import threading
import unittest
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import MagicMock, patch
from reviewflow.context import initial_state, update_state, rewrite
from reviewflow.knowledge import KnowledgeBase
from reviewflow.decision import JevDecisionModel, RuleBasedDecisionModel, configured_model, safe_evaluate, questions, validate_response
from reviewflow.synthesis import GenerativeLLM
from reviewflow.policy import load_policy, route
from reviewflow.workspace import Workspace
from reviewflow.web import make_handler
from reviewflow.benchmark import compression_experiment, synthetic_benchmark


def jev_response(kind='gate'):
    qs=questions(kind); answers={}
    for key,q in qs.items():
        if q['type']=='choice':
            selected=list(q['criteria'])[0]
            answers[key]=dict(type='choice',choice=selected,probabilities={x:float(x==selected) for x in q['criteria']},confidence=.99)
        elif q['type']=='score':
            answers[key]=dict(type='score',score=0,probabilities={str(i):float(i==0) for i in range(len(q['criteria']))},confidence=.99,legend={str(i):x for i,x in enumerate(q['criteria'])})
        else: answers[key]=dict(type='noul',noul=.99 if key=='evidence_sufficient' else .01)
    return dict(model='jev-1.13.0',answers=answers,usage={'input_tokens':100,'output_tokens':20})

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.kb=KnowledgeBase();self.llm=GenerativeLLM();self.llm.model=''
        self.w=Workspace(self.tmp.name,self.kb,RuleBasedDecisionModel(),self.llm)
        self.s=self.w.create()
    def tearDown(self):self.tmp.cleanup()
    def investigate(self,proposal=None):
        if proposal:self.s=self.w.create(proposal)
        self.s=self.w.ask(self.s['id'],'Assess novelty. Exclude patents.',self.s['revision'],intent='novelty')
        return self.s
    def test_ambiguous_input_requires_clarification(self):
        s=self.w.ask(self.s['id'],'Check this research. Exclude patents.',0)
        self.assertTrue(s['clarification']['required']);self.assertIsNone(s['review'])
        self.assertEqual(len(s['clarification']['choices']),6)
    def test_state_retains_constraints_across_turns(self):
        s=self.w.ask(self.s['id'],'Check this research. Exclude patents.',0)
        s=self.w.ask(s['id'],'Evaluate novelty from 2024 to 2026. Internal only.',1)
        self.assertEqual(s['state']['excluded_sources'],['patent'])
        self.assertEqual(s['state']['scope'],'internal')
        self.assertEqual(s['state']['time_range'],{'start':2024,'end':2026})
    def test_query_visible_and_constraints_enforced(self):
        s=self.investigate();q=s['review']['rewritten_query']
        self.assertIn('2023–2026',q);self.assertIn('patent',q)
        self.assertTrue(all(e['document_type']!='patent' and int(e['date'][:4])>=2023 for e in s['review']['evidence']))
        self.assertNotIn('PAPER-OLD',{e['document_id'] for e in s['review']['evidence']})
    def test_invalid_intent_and_dates_rejected(self):
        for kw in [dict(intent='invented'),dict(settings={'scope':'internal','start':2026,'end':2023})]:
            with self.assertRaises(ValueError):self.w.ask(self.s['id'],'Check',0,**kw)
    def test_graph_conflict_witnesses_and_provenance(self):
        s=self.investigate();r=s['review']
        self.assertTrue(r['analysis']['conflicts']);self.assertIn('PAPER-MISSING',r['analysis']['citation_conflicts'])
        for e in r['evidence']:
            self.assertIn(e['document_id'],self.kb.documents)
            self.assertEqual(e['text'],self.kb.documents[e['document_id']]['sections'][e['section']])
            self.assertTrue(e['sha256']);self.assertIn('$.sections.',e['source_location'])
        self.assertTrue(any(e['relationship']=='graph-linked related work' for e in r['evidence']))
    def test_proposal_does_not_count_as_independent_evidence(self):
        s=self.investigate()
        self.assertTrue(all(e['document_type']!='proposal' for e in s['review']['evidence']))
        self.assertIn('ethics',s['review']['analysis']['gaps'])
    def test_graph_never_bypasses_filters(self):
        state=initial_state(self.kb.documents['PROP-001']);state=update_state(state,'Novelty from 2026 to 2026. Academic only. Exclude patents.')
        es=self.kb.retrieve(state,rewrite(state),k=1)
        self.assertTrue(all(e['date'].startswith('2026') and e['scope']=='academic' for e in es))
    def test_local_fallback_has_no_fake_probabilities(self):
        s=self.investigate();d=s['review']['decision_model']
        self.assertEqual(d['engine'],'Local Deterministic Fallback');self.assertIsNone(d['answers']['evidence_sufficient']['probability'])
    def test_high_impact_routes_to_human(self):
        s=self.investigate();self.assertEqual(s['review']['gate']['route'],'escalate_to_human')
        self.assertIn('high_impact',s['review']['gate']['reasons'])
    def test_low_impact_can_continue_but_no_final_approval(self):
        s=self.investigate('PROP-002');self.assertEqual(s['review']['gate']['route'],'continue_ai_review')
        self.assertIsNone(s['final_decision']);self.assertTrue(s['review']['human_review_required'])
    def test_next_questions_are_grounded_and_continuable(self):
        s=self.investigate();qs=s['review']['next_questions'];self.assertEqual(len(qs),3)
        self.assertTrue(any(q['id']=='conflicting_findings' and q['evidence_ids'] for q in qs))
        s=self.w.ask(s['id'],'',s['revision'],question_id=qs[0]['id'])
        self.assertEqual(s['state']['intent'],'methodology');self.assertIn('patent',s['state']['excluded_sources'])
        _,log=self.w.read(s['id']);self.assertEqual(log[-1]['selected_next_question'],qs[0]['id'])
    def test_unknown_next_question_rejected(self):
        s=self.investigate()
        with self.assertRaises(ValueError):self.w.ask(s['id'],'',s['revision'],question_id='fake')
    def test_human_override_reason_required_and_captured(self):
        s=self.investigate()
        with self.assertRaisesRegex(ValueError,'Override'):self.w.decide(s['id'],1,'reject','A','Checked')
        s=self.w.decide(s['id'],1,'reject','A','Insufficient methodological case','Prefer rejecting this version')
        self.assertTrue(s['final_decision']['override']);self.assertEqual(self.w.metrics(s['id'])['human_override_rate'],1)
    def test_final_revision_requires_description(self):
        s=self.investigate()
        with self.assertRaisesRegex(ValueError,'proposed revision'):self.w.decide(s['id'],1,'revise','A','Fix')
    def test_escalation_supported(self):
        s=self.investigate();s=self.w.decide(s['id'],1,'escalate','A','Policy owner needed','Escalate instead of revise')
        self.assertEqual(s['state']['decision_stage'],'escalated')
    def test_approval_blocked_on_unresolved_evidence(self):
        s=self.investigate()
        with self.assertRaisesRegex(ValueError,'Unresolved'):self.w.decide(s['id'],1,'approve','A','Attempt','Override')
    def test_human_approval_after_clear_low_impact_review(self):
        s=self.investigate('PROP-002');s=self.w.decide(s['id'],1,'approve','A','Read independent related work and methodology')
        self.assertEqual(s['final_decision']['action'],'approve')
    def test_decision_rights_and_final_immutability(self):
        s=self.investigate('PROP-002')
        with self.assertRaisesRegex(ValueError,'decision_owner'):self.w.decide(s['id'],1,'approve','A','Checked',role='observer')
        s=self.w.decide(s['id'],1,'approve','A','Checked')
        with self.assertRaisesRegex(ValueError,'Final decision'):self.w.ask(s['id'],'Novelty',2)
    def test_stale_revision(self):
        s=self.investigate()
        with self.assertRaisesRegex(ValueError,'Stale'):self.w.ask(s['id'],'Novelty',0)
    def test_audit_persistence_and_tamper(self):
        s=self.investigate();again=Workspace(self.tmp.name,self.kb)
        snapshot,log=again.read(s['id']);self.assertEqual(snapshot,s)
        self.assertIn('llm_output',log[-1]);self.assertIn('next_questions',log[-1])
        db=self.w._journal(s['id']);db.execute("UPDATE events SET payload='{}' WHERE seq=1");db.commit();db.close()
        with self.assertRaisesRegex(ValueError,'chain'):self.w.read(s['id'])
    def test_unmeasured_metrics_null(self):
        m=self.w.metrics(self.s['id']);self.assertIsNone(m['human_override_rate']);self.assertIsNone(m['cost_usd']);self.assertIsNone(m['review_lead_time_seconds'])
    def test_jev_adapter_real_contract_mocked(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps(jev_response()).encode()
        with patch('reviewflow.decision.urlopen',return_value=response) as mocked:
            out=JevDecisionModel('unit-test-placeholder').evaluate({'gaps':[]})
        req=mocked.call_args.args[0];body=json.loads(req.data)
        self.assertEqual(req.full_url,'https://api.typesafe.ai/v1/systemone')
        self.assertEqual(body['model'],'jev-latest');self.assertEqual(body['questions']['risk']['type'],'score')
        self.assertEqual(out['model'],'jev-1.13.0');self.assertEqual(out['usage']['input_tokens'],100)
    def test_jev_invalid_response_falls_back_truthfully(self):
        with patch('reviewflow.decision.urlopen',side_effect=TimeoutError('secret must never appear')):
            out=safe_evaluate(JevDecisionModel('unit-test-placeholder'),self.investigate()['review']['analysis'])
        self.assertEqual(out['engine'],'Local Deterministic Fallback');self.assertIn('provider_failure',out)
        self.assertNotIn('secret',json.dumps(out))
    def test_schema_validation_rejects_wrong_choices_scores_and_nan(self):
        for change in [lambda o:o['answers']['risk'].update(score=float('nan')),
                       lambda o:o['answers']['routing'].update(choice='auto_approve'),
                       lambda o:o['answers']['evidence_sufficient'].update(noul=1.4),
                       lambda o:o['answers'].pop('risk'),
                       lambda o:o['usage'].update(input_tokens=-1),
                       lambda o:o['answers']['routing'].update(probabilities={'fake':1}),
                       lambda o:o['answers']['risk'].update(legend={'0':'fake'})]:
            obj=jev_response();change(obj)
            with self.assertRaises(ValueError):validate_response(obj,questions('gate'))
    def test_configuration_auto_selects_provider(self):
        with patch.dict(os.environ,{'JEVMODEL_API_KEY':''}):self.assertIsInstance(configured_model(),RuleBasedDecisionModel)
        with patch.dict(os.environ,{'JEVMODEL_API_KEY':'unit-test-placeholder'}):self.assertIsInstance(configured_model(),JevDecisionModel)
    def test_confidence_never_grants_high_impact_authority(self):
        obj=jev_response();out=dict(engine='Jev',answers=obj['answers'])
        analysis=dict(impact='high',gaps=[],conflicts=[],citation_conflicts=[],methodological_uncertainty=False)
        self.assertEqual(route(analysis,out,load_policy())['route'],'escalate_to_human')
    def test_thresholds_configurable_and_low_confidence_escalates(self):
        out=dict(engine='Jev',answers=jev_response()['answers']);out['answers']['routing']['confidence']=.6
        a=dict(impact='low',gaps=[],conflicts=[],citation_conflicts=[],methodological_uncertainty=False)
        p=load_policy();self.assertEqual(route(a,out,p)['route'],'escalate_to_human')
        p['minimum_choice_confidence']=.5;self.assertEqual(route(a,out,p)['route'],'continue_ai_review')
    def test_ollama_fake_citation_rejected(self):
        s=self.investigate();r=s['review'];self.llm.model='mock-only'
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'message':{'content':json.dumps({'suggestion':'Fake','citations':[{'id':'fake','quote':'made up'}]})}}).encode()
        with patch('reviewflow.synthesis.urlopen',return_value=response):
            out=self.llm.review(s['state'],r['rewritten_query'],r['evidence'],r['analysis'])
        self.assertIn('provider_failure',out);self.assertIn('not an LLM',out['engine'])
    def test_ollama_valid_output_requires_semantic_confirmation(self):
        self.llm.model='mock-only'
        def respond(req,timeout):
            evidence=json.loads(json.loads(req.data)['messages'][1]['content'])['evidence'][0]
            response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'message':{'content':json.dumps({'suggestion':'Compare the cited prior method','citations':[{'id':evidence['evidence_id'],'quote':evidence['text']}]})}}).encode();return response
        with patch('reviewflow.synthesis.urlopen',side_effect=respond):s=self.investigate('PROP-002')
        self.assertEqual(s['review']['synthesis']['engine'],'Ollama')
        with self.assertRaisesRegex(ValueError,'semantic'):self.w.decide(s['id'],1,'approve','A','Read')
        self.w.decide(s['id'],1,'approve','A','Read',semantic_support_confirmed=True)
    def test_reproducible_experiment_and_benchmark(self):
        c=compression_experiment();self.assertLess(c['naive_constraints_retained'],c['structured_constraints_retained'])
        b=synthetic_benchmark();self.assertTrue(all(r['routing_matches_fixture'] for r in b['cases']))
        self.assertTrue(all(r['repeat_decision_consistency'] for r in b['cases']))
        self.assertIsNone(b['comparison']['A_human_only']['review_time'])
    def test_generative_guidance_and_rewrite_keep_structured_constraints(self):
        self.llm.model='mock-only'
        state=update_state(initial_state(self.kb.documents['PROP-001']),'Check novelty. Exclude patents.')
        query=rewrite(state)
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'message':{'content':json.dumps({'clarification_question':'Which objective matters most?', 'rewritten_query':query})}}).encode()
        with patch('reviewflow.synthesis.urlopen',return_value=response):out=self.llm.prepare(state,query)
        self.assertEqual(out['engine'],'Ollama');self.assertEqual(out['rewritten_query'],query)
        response.__enter__.return_value.read.return_value=json.dumps({'message':{'content':json.dumps({'clarification_question':'Which objective?', 'rewritten_query':'Retrieve everything'})}}).encode()
        with patch('reviewflow.synthesis.urlopen',return_value=response):out=self.llm.prepare(state,query)
        self.assertIn('provider_failure',out);self.assertEqual(out['rewritten_query'],query)
    def test_investigated_question_does_not_resolve_evidence_gap(self):
        s=self.investigate();q=next(q for q in s['review']['next_questions'] if q['id'].startswith('missing_'))
        s=self.w.ask(s['id'],'',s['revision'],question_id=q['id'])
        self.assertIn(q['id'],s['state']['investigated_questions'])
        self.assertNotIn(q['id'],s['state']['resolved_questions'])
        self.assertIn('ethics',s['state']['unresolved_questions'])
    def test_path_traversal_and_missing_workspace_rejected(self):
        for sid in ['../escape','0'*32]:
            with self.assertRaises(ValueError):self.w.read(sid)

class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();llm=GenerativeLLM();llm.model=''
        self.w=Workspace(self.tmp.name,KnowledgeBase(),RuleBasedDecisionModel(),llm)
        self.server=HTTPServer(('127.0.0.1',0),make_handler(self.w));self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,obj=None,headers=None):
        req=Request(self.base+path,data=json.dumps(obj).encode() if obj else None,headers=headers or {'Content-Type':'application/json'})
        with urlopen(req) as response:return response.read()
    def test_actual_server_end_to_end(self):
        self.assertIn(b'Guided research question',self.request('/'))
        catalog=json.loads(self.request('/api/catalog'));self.assertEqual(catalog['documents'],16)
        s=json.loads(self.request('/api/create',{'proposal_id':'PROP-001'}))['workspace']
        s=json.loads(self.request('/api/ask',{'id':s['id'],'revision':0,'text':'Check this research. Exclude patents.'}))['workspace']
        self.assertTrue(s['clarification']['required'])
        s=json.loads(self.request('/api/ask',{'id':s['id'],'revision':1,'text':'Novelty','intent':'novelty'}))['workspace']
        s=json.loads(self.request('/api/decide',dict(id=s['id'],revision=2,action='revise',reviewer='Synthetic A',rationale='Conflict requires correction',revised_proposal='Add baseline and ethics evidence',role='decision_owner')))['workspace']
        out=json.loads(self.request('/api/export?id='+s['id']));self.assertEqual(len(out['audit']),4)
        self.assertEqual(out['workspace']['final_decision']['action'],'revise')
    def test_cross_origin_and_invalid_requests_rejected(self):
        for headers in [{'Content-Type':'application/json','Origin':'https://attacker.invalid'}, {'Content-Type':'text/plain'}]:
            with self.assertRaises(HTTPError):self.request('/api/create',{'proposal_id':'PROP-001'},headers)
    def test_error_is_readable(self):
        with self.assertRaises(HTTPError) as caught:self.request('/api/ask',{'id':'bad','revision':0,'text':'Novelty'})
        self.assertIn('workspace',json.loads(caught.exception.read())['error'])

if __name__=='__main__':unittest.main()
