"""Synthetic measurements only. Human baseline and live model quality are unmeasured."""
import argparse
import copy
import json
import tempfile
from pathlib import Path
from time import perf_counter
from .context import initial_state, update_state, rewrite
from .knowledge import KnowledgeBase
from .workspace import Workspace
from .decision import RuleBasedDecisionModel
from .synthesis import GenerativeLLM


def compression_experiment():
    cases=[
        ['Review novelty. Exclude patents.','Use internal and academic sources from 2023 to 2026.','Explain overlapping research.'],
        ['Review novelty from 2024 to 2026. Exclude patents.','Compare methodological differences.','Focus on novelty.'],
        ['Check methodology. Exclude patents.','Use internal only research.','Check sample size.'],
    ]
    kb=KnowledgeBase(); results=[]
    for i,turns in enumerate(cases):
        state=initial_state(kb.documents['PROP-001'])
        for text in turns: state=update_state(state,text)
        # Explicit lossy baseline: last-turn-only compression, not a claim about all LLM summaries.
        naive=turns[-1]
        rebuilt=update_state(initial_state(kb.documents['PROP-001']),naive)
        checks={
            'exclude_patents':lambda s:'patent' in s['excluded_sources'],
            'time_range':lambda s:s['time_range']==state['time_range'],
            'scope':lambda s:s['scope']==state['scope'],
        }
        results.append(dict(case=i+1,conversation=turns,naive_summary=naive,structured_state=state,
            naive_retention={k:fn(rebuilt) for k,fn in checks.items()},
            structured_retention={k:fn(state) for k,fn in checks.items()}))
    total=sum(len(r['naive_retention']) for r in results)
    return dict(label='Synthetic Context Compression Experiment',baseline='Deliberately naive last-turn-only summarizer; not live LLM output',
        cases=results,critical_constraint_checks=total,
        naive_constraints_retained=sum(sum(r['naive_retention'].values()) for r in results),
        structured_constraints_retained=sum(sum(r['structured_retention'].values()) for r in results),
        limitation='Hand-authored cases demonstrate possible loss; not an estimate of real model summarization quality.')


def synthetic_benchmark():
    kb=KnowledgeBase()
    # Gold labels declared before retrieval; doc/section IDs are independent of ranks.
    cases=[
        dict(id='network_conflict',proposal='PROP-001',intent='novelty',question='Check novelty. Exclude patents.',
             gold=[['PAPER-001','related_work'],['PAPER-002','validation'],['ART-001','methodology']],route='escalate_to_human'),
        dict(id='robotics_low_impact',proposal='PROP-002',intent='related_work',question='Find related research. Exclude patents.',
             gold=[['PAPER-004','related_work'],['PAPER-004','methodology']],route='continue_ai_review'),
        dict(id='forecast_low_impact',proposal='PROP-003',intent='methodology',question='Check methodology. Exclude patents.',
             gold=[['PAPER-005','related_work'],['PAPER-005','methodology']],route='continue_ai_review'),
        dict(id='network_empty_scope',proposal='PROP-001',intent='evidence',question='Check evidence from 2026 to 2026. Internal only. Exclude patents.',
             gold=[],route='escalate_to_human'),
    ]
    rows=[]
    with tempfile.TemporaryDirectory() as folder:
        w=Workspace(folder,kb,RuleBasedDecisionModel(),GenerativeLLM(model=''))
        # Force baseline regardless of developer machine Ollama environment.
        w.llm.model=''
        for case in cases:
            s=w.create(case['proposal']); outputs=[]; times=[]
            for _ in range(3):
                start=perf_counter()
                result=w.ask(s['id'],case['question'],s['revision'],intent=case['intent'])
                times.append(perf_counter()-start); s=result
                outputs.append((s['review']['recommendation'],s['review']['gate']['route']))
            r=s['review']; pairs={(e['document_id'],e['section']) for e in r['evidence']}; gold={tuple(x) for x in case['gold']}
            correct=r['gate']['route']==case['route']
            trace=sum(bool(e['source_location'] and e['sha256'] and e['text']) for e in r['evidence'])
            rows.append(dict(case=case,actual_route=r['gate']['route'],routing_matches_fixture=correct,
                gold_retrieval_recall=len(gold & pairs)/len(gold) if gold else None,
                evidence_traceability=trace/len(r['evidence']) if r['evidence'] else None,
                section_coverage=w.metrics(s['id'])['evidence_coverage'],repeat_decision_consistency=len(set(outputs))==1,
                pipeline_seconds=times,documents_retrieved=len({e['document_id'] for e in r['evidence']}),
                escalation=r['gate']['route']=='escalate_to_human',actual_engine=r['decision_model']['engine']))
    return dict(label='Evaluation Framework / Synthetic Benchmark',cases=rows,
        comparison={
            'A_human_only':{'status':'not studied','review_time':None,'decision_quality':None},
            'B_llm_rag':{'status':'protocol only; no live model or users measured','review_time':None,'decision_quality':None},
            'C_hybrid':{'status':'deterministic hybrid control-flow fixtures executed; no live Jev or LLM quality measured','cases':len(rows)},
        },human_override_rate=None,reviewer_workload=None,model_cost_usd=None,calibration=None,
        limitation='Gold labels are hand-authored behavioral fixtures. Pipeline timing is machine execution, not human review time or time saved.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='runs/benchmark');args=parser.parse_args()
    folder=Path(args.out);folder.mkdir(parents=True,exist_ok=True)
    for name, result in [('compression',compression_experiment()),('benchmark',synthetic_benchmark())]:
        (folder/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('Synthetic benchmark and context experiment written to '+str(folder))

if __name__=='__main__':main()
