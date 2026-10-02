"""Organization-owned decision boundaries, separate from model prompts."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_policy(path=None):
    p = json.loads(Path(path or os.environ.get('REVIEWFLOW_POLICY') or ROOT/'config/governance.json').read_text())
    for k in ('minimum_choice_confidence','sufficiency_yes_threshold','escalation_yes_threshold'):
        if not isinstance(p[k],(int,float)) or isinstance(p[k],bool) or not 0<=p[k]<=1:
            raise ValueError('Invalid policy threshold: '+k)
    if not 0<=p['high_risk_score']<=3 or not p['all_final_decisions_require_human'] or not p['high_impact_requires_human']:
        raise ValueError('Human authority boundaries may not be disabled')
    if p['missing_evidence_route']!='request_more_information' or p['conflict_route']!='escalate_to_human':
        raise ValueError('Invalid governance route')
    if p['final_decision_role']!='decision_owner':
        raise ValueError('Final decision owner required')
    return p


def route(analysis, output, policy):
    a = output['answers']; reasons = []
    if analysis['impact']=='high': reasons.append('high_impact')
    if analysis['conflicts'] or analysis['citation_conflicts']: reasons.append('conflicting_evidence_or_citation')
    if analysis['methodological_uncertainty']: reasons.append('methodological_uncertainty')
    risk = a['risk']['score']
    if risk >= policy['high_risk_score']: reasons.append('risk_threshold')
    if a['human_escalation'].get('noul',int(a['human_escalation'].get('value',False))) >= policy['escalation_yes_threshold']:
        reasons.append('model_or_rule_escalation')
    if reasons:
        routing = policy['conflict_route']
    elif analysis['gaps']:
        reasons.append('missing_mandatory_evidence')
        routing = policy['missing_evidence_route']
    elif output.get('provider_failure'):
        reasons.append('decision_provider_failure')
        routing = 'escalate_to_human'
    elif output['engine']=='Jev':
        confidence = min(a['risk']['confidence'],a['routing']['confidence'])
        if confidence < policy['minimum_choice_confidence']:
            reasons.append('low_model_confidence'); routing='escalate_to_human'
        elif a['evidence_sufficient']['noul'] < policy['sufficiency_yes_threshold']:
            reasons.append('model_evidence_uncertainty'); routing='request_more_information'
        else:
            routing=a['routing']['choice']; reasons.append('bounded_model_route')
    else:
        routing=a['routing']['choice']; reasons.append('deterministic_rule_route')
    return dict(route=routing,reasons=reasons,policy_version=policy['version'],thresholds={k:policy[k] for k in
        ('minimum_choice_confidence','sufficiency_yes_threshold','escalation_yes_threshold','high_risk_score')},
        human_review_required=True,organizational_authority='Human decision owner only; confidence never grants approval authority')
