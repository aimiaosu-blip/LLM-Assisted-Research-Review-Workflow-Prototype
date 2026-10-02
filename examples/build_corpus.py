"""Rebuild hand-authored synthetic corpus. No real research or enterprise data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def doc(id, title, topic, year, kind, sections, **kw):
    return dict(document_id=id, title='SYNTHETIC — '+title, author='Synthetic '+('Research Board' if kind=='guideline' else 'Research Team '+id),
                date=f'{year}-03-15', document_type=kind, research_area=topic,
                synthetic=True, sections=sections, citations=[], relations=[], **kw)

TOPIC = 'AI-assisted network optimization'
DOCS = [
 doc('PROP-001','Adaptive network co-pilot proposal',TOPIC,2026,'proposal',{
  'objective':'We propose AI-assisted network optimization using a human-supervised co-pilot. Novelty claim: first adaptive traffic scheduling model with operator explanations.',
  'methodology':'A simulated network with 24 traffic traces is planned. No power calculation or held-out validation report is supplied.',
  'ethics':'Production traffic data approval is pending. Intended deployment affects network availability.',
 }, impact='high', mandatory_evidence=['related_work','methodology','validation','ethics']),
 doc('PAPER-001','Explained adaptive scheduling',TOPIC,2023,'paper',{
  'related_work':'Adaptive traffic scheduling with operator explanations was explored in 2023. This prior approach overlaps the proposal novelty claim.',
  'methodology':'A controlled simulation compared adaptive scheduling with fixed routing on 50 held-out traffic traces.',
  'validation':'Latency decreased 12 percent in this synthetic simulation, with a reported uncertainty interval. This is not real-world performance.',
 }, scope='academic'),
 doc('PAPER-002','Replication under burst traffic',TOPIC,2025,'paper',{
  'related_work':'A replication extends explained adaptive scheduling to burst traffic.',
  'methodology':'Held-out burst traffic traces use the same baseline but a different traffic distribution.',
  'validation':'Latency increased 4 percent under burst traffic, contradicting the earlier improvement claim under changed conditions.',
 }, scope='academic'),
 doc('ART-001','Internal scheduling pilot',TOPIC,2024,'artefact',{
  'related_work':'Internal pilot used adaptive scheduling with operator explanations; potentially overlapping research already exists.',
  'methodology':'Pilot logs contain 24 traces, no control group, and no prospective power calculation.',
  'validation':'Latency improvement cannot be attributed to the co-pilot because load and configuration changed concurrently.',
 }, scope='internal'),
 doc('PAPER-003','Operator trust in AI recommendations',TOPIC,2026,'paper',{
  'related_work':'Human override and explanations support inspection of AI-assisted network optimization recommendations.',
  'methodology':'A synthetic controlled usability protocol defines an operator comparison, without claiming real participant results.',
 }, scope='academic'),
 doc('PAT-001','Scheduling patent demonstration',TOPIC,2025,'patent',{
  'related_work':'Synthetic patent on adaptive scheduling with operator explanations. Must be excluded when requested.',
 }, scope='academic'),
 doc('PAPER-OLD','Early traffic routing',TOPIC,2021,'paper',{
  'related_work':'Early adaptive network optimization lacks operator explanations.',
 }, scope='academic'),
 doc('GUIDE-001','Research review and decision rights',TOPIC,2026,'guideline',{
  'policy':'Every major recommendation requires traceable evidence. Related work, methodology, validation and ethics are mandatory for this synthetic proposal. Missing evidence requires more information; conflicts require human review. AI cannot finalize approval.',
 }, scope='internal'),
 doc('REV-001','Historical pilot revision',TOPIC,2024,'review',{
  'decision':'Synthetic decision owner requested revision of the internal pilot because no controlled baseline was supplied. This is a historical demonstration, not approval for PROP-001.',
 }, scope='internal'),
 doc('META-001','Publication register',TOPIC,2026,'metadata',{
  'register':'PAPER-002 cites PAPER-001; PAPER-003 cites PAPER-001. Publication dates and titles are synthetic. One proposal citation is unresolved: PAPER-MISSING.',
 }, scope='internal'),
 doc('PROP-002','Robotics retrieval review','Embodied AI research',2026,'proposal',{
  'objective':'Research a retrieval-assisted embodied AI laboratory helper using only synthetic robotics task logs.',
 }, impact='low', mandatory_evidence=['related_work','methodology']),
 doc('PAPER-004','Embodied lab helper','Embodied AI research',2024,'paper',{
  'related_work':'A retrieval-assisted embodied AI laboratory helper maps task descriptions to safe actions.',
  'methodology':'Synthetic robotics task logs use a disjoint test set and independent task labels.',
 }, scope='academic'),
 doc('ART-002','Robotics simulation logs','Embodied AI research',2025,'artefact',{
  'validation':'Synthetic robotics simulations record task completion without real user data.',
 }, scope='internal'),
 doc('PROP-003','Energy forecasting study','Energy demand forecasting',2026,'proposal',{
  'objective':'Compare probabilistic energy demand forecasting methods on synthetic time series.',
 }, impact='low', mandatory_evidence=['related_work','methodology']),
 doc('PAPER-005','Forecast comparison','Energy demand forecasting',2024,'paper',{
  'related_work':'Probabilistic energy demand forecasting compares seasonal and neural baselines.',
  'methodology':'Temporal holdout prevents future leakage; predictions use synthetic time series.',
 }, scope='academic'),
 doc('ART-003','Forecast replication','Energy demand forecasting',2025,'artefact',{
  'validation':'Synthetic forecasting replication uses rolling windows and reports errors by horizon.',
 }, scope='internal'),
]
DOCS[0]['citations'] = ['PAPER-001','PAPER-MISSING']
DOCS[2]['citations'] = ['PAPER-001']
DOCS[2]['relations'] = [{'type':'extends','target':'PAPER-001'},{'type':'contradicts','target':'PAPER-001'}]
DOCS[3]['relations'] = [{'type':'related_to','target':'PAPER-001'}]
DOCS[4]['citations'] = ['PAPER-001']
DOCS[8]['relations'] = [{'type':'reviewed_by','target':'Synthetic Review Board'},{'type':'related_to','target':'ART-001'}]

if __name__ == '__main__':
    folder = ROOT/'data/synthetic'; folder.mkdir(parents=True,exist_ok=True)
    for d in DOCS:
        (folder/(d['document_id']+'.json')).write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
    print(f'Wrote {len(DOCS)} synthetic documents')
