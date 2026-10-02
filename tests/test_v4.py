import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from reviewflow.__main__ import run
from reviewflow.storage import connect,state,decide
from reviewflow.governance import record
from reviewflow.evaluation import evaluate,enrich,claim_status
from reviewflow.regression import promote,retest
from reviewflow.core import ingest,review

ROOT=Path(__file__).resolve().parents[1]
class V4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.out=Path(self.tmp.name)/'run'
        with contextlib.redirect_stdout(io.StringIO()):
            run(argparse.Namespace(input=str(ROOT/'sample_data'),criteria=None,out=str(self.out),model=None,data_label='SYNTHETIC',repeats=3))
    def tearDown(self): self.tmp.cleanup()
    def snapshot(self):
        db=connect(self.out)
        try: return state(db)
        finally: db.close()
    def test_trace_and_metrics(self):
        data,log=self.snapshot(); m=evaluate(data,log)
        self.assertIsNone(m['ai_human_agreement'])
        self.assertEqual(m['denominators']['final_decisions'],0)
        self.assertEqual(m['recommendation_consistency']['C1'],1)
        self.assertIn('high_impact',data['findings'][1]['routing'])
        self.assertEqual(m['badcase_rate'],.75)
        self.assertTrue(data['findings'][0]['retrieved_sources'])
    def test_rights_override_and_accountability(self):
        with self.assertRaisesRegex(ValueError,'decision_owner'):
            record(self.out,'C1','final','A',0,decision='approve',role='observer',reason='checked')
        with self.assertRaisesRegex(ValueError,'Override reason'):
            record(self.out,'C1','final','A',0,decision='approve',role='decision_owner',reason='checked')
        record(self.out,'C1','final','A',0,decision='approve',role='decision_owner',reason='checked',override_reason='Human resolves review abstention')
        data,log=self.snapshot(); f=data['findings'][0]
        self.assertEqual(f['final_decision']['accountable_owner'],'A')
        self.assertEqual(evaluate(data,log)['human_override_rate'],1)
        self.assertEqual(f['rca'],[])
        with self.assertRaises(ValueError): decide(self.out,'C1','revise','A','changed',1,'new')
    def test_unresolved_cannot_approve(self):
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            record(self.out,'C2','final','A',0,decision='approve',role='decision_owner',reason='checked',override_reason='attempt')
    def test_semantic_support_not_inferred_from_citation(self):
        _,chunks=ingest(ROOT/'sample_data'); fs=review(json.loads((ROOT/'sample_data/criteria.json').read_text()),chunks)
        fs[0]['llm']={'suggestion':'Everyone consented','citations':[{'id':fs[0]['evidence'][0]['id']}]}
        enrich(fs,chunks); c=fs[0]['claims'][-1]
        self.assertEqual(claim_status(fs[0],c),'unverified')
        fs[0]['support_reviews'][c['id']]={'verdict':'unsupported'}
        self.assertEqual(claim_status(fs[0],c),'unsupported')
    def test_missing_evidence_cannot_be_human_labelled_supported(self):
        data,_=self.snapshot(); f=data['findings'][0]; c=f['claims'][0]; c['evidence_ids']=['fabricated']
        f['support_reviews'][c['id']]={'verdict':'supported'}
        self.assertEqual(claim_status(f,c),'unsupported')
    def test_support_event_and_stale_revision(self):
        data,_=self.snapshot(); claim=data['findings'][0]['claims'][0]['id']
        record(self.out,'C1','support','A',0,claim=claim,verdict='supported',reason='Exact extraction checked')
        self.assertIn(claim,self.snapshot()[0]['findings'][0]['support_reviews'])
        with self.assertRaisesRegex(ValueError,'Stale'):
            record(self.out,'C1','support','B',0,claim=claim,verdict='supported',reason='checked')
    def test_validated_rca_and_regression_detects_selection_loss(self):
        target=Path(self.tmp.name)/'case.json'
        with self.assertRaisesRegex(ValueError,'Validated'):
            promote(self.out,'C2',target,'conflict',[])
        diagnosis=json.loads((ROOT/'demo/retention_rca.json').read_text())
        record(self.out,'C2','rca','Synthetic reviewer',0,**diagnosis)
        data,_=self.snapshot(); f=data['findings'][1]
        self.assertFalse(f['rca'][0]['ai_error'])
        ids=[e['id'] for e in f['evidence']]
        promote(self.out,'C2',target,'conflict',ids)
        self.assertTrue(retest(target)['passed'])
        def broken(criteria,chunks):
            fs=review(criteria,chunks); fs[0]['evidence']=[]; return fs
        with patch('reviewflow.regression.review',side_effect=broken):
            self.assertFalse(retest(target)['passed'])
        self.assertTrue(retest(target)['passed'])
        with self.assertRaises(FileExistsError): promote(self.out,'C2',target,'conflict',ids)
    def test_failed_repeats_never_score_perfect(self):
        data,log=self.snapshot(); data['repeat_recommendations']=[{f['id']:'__MODEL_FAILURE__' for f in data['findings']}]*3
        self.assertEqual(evaluate(data,log)['recommendation_consistency']['C1'],0)
    def test_empty_claim_metric_is_null(self):
        data,log=self.snapshot()
        for f in data['findings']: f['claims']=[]
        self.assertIsNone(evaluate(data,log)['claim_evidence_consistency'])
    def test_rca_requires_evidence(self):
        with self.assertRaisesRegex(ValueError,'requires'):
            record(self.out,'C2','rca','A',0,category='Reasoning Failure')

    def test_feedback_maturity_levels(self):
        from reviewflow.improvement import feedback
        diagnosis=json.loads((ROOT/'demo/retention_rca.json').read_text())
        record(self.out,'C2','rca','A',0,**diagnosis)
        for level in ('L0','L1','L2'):
            result=feedback(self.out,'C2',Path(self.tmp.name)/(level+'.json'),level)
            self.assertFalse(result['auto_applied'])
            self.assertEqual('local_ticket' in result,level!='L0')
            self.assertEqual('configuration_proposal' in result,level=='L2')
        with self.assertRaises(ValueError):feedback(self.out,'C2',Path(self.tmp.name)/'L3.json','L3')
    def test_human_conflict_blocks_extractive_claim(self):
        data,_=self.snapshot();f=data['findings'][0];c=f['claims'][0]
        f['support_reviews'][c['id']]={'verdict':'conflict'}
        self.assertEqual(claim_status(f,c),'conflict')
    def test_regression_requires_explicit_behavior(self):
        diagnosis=json.loads((ROOT/'demo/retention_rca.json').read_text())
        record(self.out,'C2','rca','A',0,**diagnosis)
        with self.assertRaisesRegex(ValueError,'explicit expected evidence'):
            promote(self.out,'C2',Path(self.tmp.name)/'empty.json','conflict',[])
