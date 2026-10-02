"""Local declared decision rights; no identity authentication."""
from .storage import connect, state, append
from .evaluation import claim_status

CATEGORIES = {
 'Retrieval Failure': ('retrieval','retriever'),
 'Evidence Selection Failure': ('evidence_selection','evidence_selector'),
 'Evidence Interpretation Failure': ('interpretation','model_or_reviewer'),
 'Reasoning Failure': ('reasoning','recommendation_logic'),
 'Criteria/Policy Failure': ('criteria','policy_owner'),
 'Unsupported Claim': ('analysis','claim_validator'),
 'Legitimate Human-AI Disagreement': ('human_review','decision_owner'),
 'Review Criteria Ambiguity': ('criteria','policy_owner'),
}


def record(out, finding_id, action, reviewer, revision, **payload):
    if not reviewer.strip(): raise ValueError('Reviewer required')
    db = connect(out)
    try:
        db.execute('BEGIN IMMEDIATE')
        data, log = state(db)
        f = next((f for f in data['findings'] if f['id']==finding_id),None)
        if f is None: raise ValueError('Unknown finding')
        if f['revision'] != revision: raise ValueError('Stale revision')
        if 'claims' not in f: raise ValueError('Create a V4 run first')
        if action == 'support':
            if f['final_decision']: raise ValueError('Final decision already recorded')
            if payload.get('verdict') not in {'supported','unsupported','conflict'}: raise ValueError('Invalid support verdict')
            if not any(c['id']==payload.get('claim') for c in f['claims']): raise ValueError('Unknown claim')
            if not payload.get('reason','').strip(): raise ValueError('Support rationale required')
        elif action == 'final':
            if f['final_decision']: raise ValueError('Final decision already recorded')
            if payload.get('role') != 'decision_owner': raise ValueError('Only declared decision_owner may finalize')
            if payload.get('decision') not in {'approve','reject','revise'}: raise ValueError('Invalid decision')
            if not payload.get('reason','').strip(): raise ValueError('Decision rationale required')
            payload['override'] = payload['decision'] != f['recommendation']['decision']
            if payload['override'] and not payload.get('override_reason','').strip(): raise ValueError('Override reason required')
            if payload['decision']=='approve' and (f['kind'] != 'candidate' or any(claim_status(f,c)!='supported' for c in f['claims'])):
                raise ValueError('Unresolved evidence or claims: revise/reject, then create a corrected run')
            payload['decision_rights'] = 'Human decision owner finalizes prototype review disposition; no study authorization'
            payload['accountable_owner'] = reviewer.strip()
        elif action == 'rca':
            if payload.get('category') not in CATEGORIES: raise ValueError('Unknown RCA category')
            for key in ('observed_failure','first_divergence','root_cause','responsible_component','corrective_action','validation_evidence'):
                if not payload.get(key,'').strip(): raise ValueError('RCA requires '+key)
            if payload['first_divergence'] not in {'retrieval','evidence_selection','interpretation','reasoning','criteria','analysis','human_review'}: raise ValueError('Invalid divergence stage')
            payload['validated'] = True
            payload['ai_error'] = payload['category'] not in {'Legitimate Human-AI Disagreement','Review Criteria Ambiguity'}
        else: raise ValueError('Unknown governance action')
        append(db,dict(payload,action=action,finding=finding_id,reviewer=reviewer.strip(),revision=revision+1))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally: db.close()
