"""L0 reports, L1 local tickets and L2 reviewable proposals; never auto-apply."""
import json
from pathlib import Path
from .storage import connect,state

PLAYBOOKS = {
 'Retrieval Failure': ('RAG / knowledge', ['Add missing source knowledge','Adjust chunk boundaries and lexical recall','Check source/version coverage']),
 'Evidence Selection Failure': ('RAG / knowledge', ['Retain contradictory witnesses beyond top-k','Review selection rules','Validate claim citations']),
 'Evidence Interpretation Failure': ('Prompt / strategy', ['Require bounded interpretations and explicit uncertainty','Split extraction from interpretation','Escalate ambiguous passages']),
 'Reasoning Failure': ('Model capability', ['Decompose complex judgments','Compare models on frozen cases before switching','Consider fine-tuning only after adequate labeled data']),
 'Criteria/Policy Failure': ('Business process', ['Version the SOP and authority rules','Encode checkable state transitions','Review decision rights with the policy owner']),
 'Unsupported Claim': ('Prompt / strategy', ['Require claim-level citations','Reject unsupported conclusions','Retest citation and semantic-support checks']),
 'Legitimate Human-AI Disagreement': ('Product interaction', ['Capture contextual rationale','Offer clarification and human handoff','Retain disagreement without labelling it AI error']),
 'Review Criteria Ambiguity': ('Business process', ['Clarify criterion with research and policy owners','Document authoritative evidence','Add a checkable decision node']),
}
TOOL_PLAYBOOK=('Tools / API',['Validate response schema and parameter types','Preserve adapter error trace','Fallback to rules and human review'])


def feedback(out, finding_id, target, level):
    if level not in {'L0','L1','L2'}: raise ValueError('Only L0/L1/L2 implemented; no automatic PR generation')
    db=connect(out)
    try: data,log=state(db)
    finally: db.close()
    f=next((f for f in data['findings'] if f['id']==finding_id),None)
    if f is None or not f.get('rca'): raise ValueError('Validated diagnosis required')
    r=f['rca'][-1]; family,actions=PLAYBOOKS[r['category']]
    result=dict(level=level,category=r['category'],family=family,actions=actions,
                corrective_action=r['corrective_action'],owner=r['responsible_component'],
                trace=f['trace'],validation_evidence=r['validation_evidence'],
                status='proposed; human review required',auto_applied=False)
    if any(e['finding']==finding_id for e in data['model_errors']):
        result['adapter_followup']=dict(family=TOOL_PLAYBOOK[0],actions=TOOL_PLAYBOOK[1])
    if level in {'L1','L2'}:
        result['local_ticket']=dict(title=r['category']+': '+finding_id,acceptance_criteria=[r['corrective_action'],'Pass the frozen regression case and existing test suite'],external_ticket_created=False)
    if level=='L2':
        result['configuration_proposal']=dict(target_component=r['responsible_component'],proposed_changes=actions,required_checks=['Compare baseline and candidate on frozen cases','Review high-impact cases with a human','Reject candidate if any required regression fails'],executable=False)
    path=Path(target);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as h:json.dump(result,h,indent=2)
    return result
