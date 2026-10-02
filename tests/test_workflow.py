import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from reviewflow.core import ingest, review, retrieve, validate_llm
from reviewflow.storage import connect, state, decide
from reviewflow.__main__ import run
from reviewflow.dashboard import export

ROOT = Path(__file__).resolve().parents[1]

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.capture = contextlib.redirect_stdout(io.StringIO())
        self.capture.__enter__()
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)/'run'
        self.args = argparse.Namespace(input=str(ROOT/'sample_data'), criteria=None, out=str(self.out), model=None, data_label='SYNTHETIC SAMPLE DATA')
    def tearDown(self):
        self.tmp.cleanup()
        self.capture.__exit__(None,None,None)
    def snapshot(self):
        db = connect(self.out)
        try:
            return state(db)
        finally:
            db.close()
    def test_fixture_classifications_and_provenance(self):
        run(self.args)
        data, log = self.snapshot()
        self.assertEqual([f['kind'] for f in data['findings']], ['candidate','conflict','blocked','missing'])
        self.assertEqual(len(data['documents']),4)
        self.assertTrue(all(f['status']=='pending' for f in data['findings']))
        self.assertEqual(len(log),1)
        for f in data['findings'][:3]:
            self.assertTrue(all(e['sha256'] and e['location'] and e['text'] for e in f['evidence']))
    def test_determinism(self):
        docs, chunks = ingest(ROOT/'sample_data')
        self.assertEqual((docs,chunks),ingest(ROOT/'sample_data'))
    def test_zero_overlap(self):
        _, chunks = ingest(ROOT/'sample_data')
        self.assertEqual(retrieve('xyzabsent',chunks),[])
    def test_revision_then_approval_preserves_original(self):
        run(self.args)
        decide(self.out,'C2','revise','Demo reviewer','Reconcile policy first',0,'Request corrected retention protocol.')
        decide(self.out,'C2','approve','Demo reviewer','Accept this recommendation, not study deployment',1)
        data, log = self.snapshot()
        self.assertEqual(data['findings'][1]['status'],'approved')
        self.assertEqual(data['findings'][1]['revision'],2)
        self.assertEqual(log[0]['snapshot']['findings'][1]['suggestion'],'Resolve inconsistent structured values or units before approval.')
    def test_stale_revision_rejected(self):
        run(self.args)
        decide(self.out,'C1','revise','A','Need clarification',0,'Clarify sampling method')
        with self.assertRaisesRegex(ValueError,'Stale'):
            decide(self.out,'C1','approve','B','Checked',0)
    def test_terminal_decision_rejected(self):
        run(self.args)
        decide(self.out,'C1','reject','A','Insufficient evidence',0)
        with self.assertRaisesRegex(ValueError,'Terminal'):
            decide(self.out,'C1','approve','B','Checked',1)
    def test_reason_and_revision_text_required(self):
        run(self.args)
        for note, replacement in [('', 'new'),('reason','')]:
            with self.assertRaises(ValueError):
                decide(self.out,'C1','revise','A',note,0,replacement)
    def test_unknown_finding(self):
        run(self.args)
        with self.assertRaisesRegex(ValueError,'Unknown'):
            decide(self.out,'C99','approve','A','Checked',0)
    def test_tamper_detection(self):
        run(self.args)
        db=connect(self.out)
        db.execute("UPDATE events SET payload='{}' WHERE seq=1")
        db.commit()
        with self.assertRaisesRegex(ValueError,'chain'):
            state(db)
        db.close()
    def test_no_overwrite(self):
        run(self.args)
        with self.assertRaisesRegex(ValueError,'already exists'):
            run(self.args)
        self.assertEqual(len(self.snapshot()[1]),1)
    def test_invalid_llm_citations(self):
        for c in [{'id':'x','quote':'hello'},{'id':'a','quote':'invented'},{'id':'a','quote':''}]:
            with self.assertRaises(ValueError):
                validate_llm({'suggestion':'Review','citations':[c]},[{'id':'a','text':'hello'}])
    def test_valid_llm_citation(self):
        result=validate_llm({'suggestion':'Check','citations':[{'id':'a','quote':'hello'}]},[{'id':'a','text':'hello world'}])
        self.assertIn('NOT guaranteed',result['warning'])
    def test_missing_llm_citation(self):
        with self.assertRaises(ValueError):
            validate_llm({'suggestion':'Check','citations':[]},[])
    def test_llm_failure_fallback(self):
        self.args.model='fake-test-model'
        with patch('reviewflow.__main__.ollama_review',side_effect=ValueError('bad model output')):
            run(self.args)
        data,_=self.snapshot()
        self.assertEqual(len(data['model_errors']),3)
        self.assertTrue(all(f['llm'] is None for f in data['findings']))
        self.assertIn('0 validated drafts',data['mode'])
    def test_llm_adapter_integration_mocked(self):
        self.args.model='fake-test-model'
        def respond(request, timeout):
            payload=json.loads(request.data)
            context=json.loads(payload['messages'][1]['content'])
            evidence=context['evidence'][0]
            result={'suggestion':'Review the quoted evidence', 'citations':[{'id':evidence['id'],'quote':evidence['text']}]}
            response=MagicMock()
            response.__enter__.return_value.read.return_value=json.dumps({'message':{'content':json.dumps(result)}}).encode()
            return response
        with patch('reviewflow.core.urlopen',side_effect=respond):
            run(self.args)
        self.assertEqual(sum(f['llm'] is not None for f in self.snapshot()[0]['findings']),3)
    def test_invalid_model_output_falls_back_end_to_end(self):
        self.args.model='fake-test-model'
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'message':{'content':json.dumps({'suggestion':'Approve all','citations':[{'id':'fabricated','quote':'fake'}]})}}).encode()
        with patch('reviewflow.core.urlopen',return_value=response):
            run(self.args)
        data,_=self.snapshot()
        self.assertEqual(len(data['model_errors']),3)
        self.assertTrue(all(f['status']=='pending' and f['llm'] is None for f in data['findings']))
    def test_html_escaping(self):
        run(self.args)
        decide(self.out,'C1','revise','A','<script>alert(1)</script>',0,'<img src=x onerror=alert(1)>')
        export(self.out)
        html=(self.out/'dashboard.html').read_text()
        self.assertNotIn('<script>',html)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;script&gt;',html)
    def test_malformed_json(self):
        folder=Path(self.tmp.name)/'input'; folder.mkdir()
        (folder/'bad.json').write_text('{oops')
        with self.assertRaises(ValueError):
            ingest(folder)
    def test_empty_corpus(self):
        with self.assertRaisesRegex(ValueError,'No supported'):
            ingest(self.tmp.name)
    def test_conflict_beyond_top_k(self):
        chunks=[dict(id=str(i),fact_key='x',value=i,unit='days',text='x',source='s',location=str(i),sha256='hash') for i in range(8)]
        f=review([{'id':'c','title':'x','query':'x','fact_key':'x'}],chunks)[0]
        self.assertEqual(f['kind'],'conflict')
        self.assertEqual(len(f['evidence']),8)
    def test_duplicate_criteria(self):
        with self.assertRaises(ValueError):
            review([{'id':'c'},{'id':'c'}],[])

if __name__ == '__main__':
    unittest.main()
