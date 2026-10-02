"""Executed synthetic intent → clarification → evidence → follow-up → human disposition."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reviewflow.knowledge import KnowledgeBase
from reviewflow.workspace import Workspace
from reviewflow.decision import RuleBasedDecisionModel
from reviewflow.synthesis import GenerativeLLM


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='runs/workflow-demo');args=parser.parse_args()
    llm=GenerativeLLM();llm.model=''
    w=Workspace(args.out,KnowledgeBase(),RuleBasedDecisionModel(),llm)
    s=w.create()
    s=w.ask(s['id'],'Can you check whether this research is good enough? Exclude patents.',0)
    assert s['clarification']['required'] and not s['review']
    s=w.ask(s['id'],'Assess novelty using internal and academic research from 2023 to 2026.',s['revision'],intent='novelty')
    assert 'patent' in s['state']['excluded_sources']
    s=w.ask(s['id'],'',s['revision'],question_id=s['review']['next_questions'][0]['id'])
    s=w.decide(s['id'],s['revision'],'revise','Synthetic decision owner',
        'Prior work overlaps the novelty claim; reconcile contradictory findings and supply missing ethics evidence.',
        revised_proposal='Narrow the novelty claim, compare burst traffic methods, verify PAPER-MISSING and supply ethics authorization evidence.')
    s,log=w.read(s['id'])
    out=Path(args.out)/'demo.json';out.write_text(json.dumps(dict(workspace=s,audit=log,metrics=w.metrics(s['id'])),indent=2)+'\n')
    print('Synthetic demo: '+str(out))

if __name__=='__main__':main()
