"""Provider-independent bounded decisions using the verified TypeSafe contract."""
import json
import math
import os
from abc import ABC, abstractmethod
from urllib.request import Request, urlopen
from .context import INTENTS, detect_intent

ROUTES = {'continue_ai_review':'Continue low-risk investigation',
          'request_more_information':'Mandatory evidence or certainty missing',
          'escalate_to_human':'Conflicts or high-impact judgment require a human'}
RISK_LEVELS = ['low: no known methodological issues','medium: evidence gaps',
               'high: contradictory or methodologically uncertain evidence','critical: material safety uncertainty']


def questions(kind):
    if kind == 'intent':
        return {'intent': {'type':'choice','instructions':'Classify the requested research review objective. Do not grant approval.', 'criteria': INTENTS}}
    return {
        'evidence_sufficient': {'type':'noul','instructions':'Are all mandatory evidence sections present in the retrieved independent evidence, with no unresolved contradictions or citation conflicts?'},
        'risk': {'type':'score','instructions':'Rate methodological and evidence risk using observed gaps and conflicts. This score is not approval authority.', 'criteria': RISK_LEVELS},
        'routing': {'type':'choice','instructions':'Select a recommended review route. High impact and contradictions require human escalation. Missing evidence requires more information.', 'criteria': ROUTES},
        'human_escalation': {'type':'noul','instructions':'Does this investigation require human escalation because of high impact, conflicts or high methodological uncertainty?'},
    }

class DecisionModelAdapter(ABC):
    @abstractmethod
    def evaluate(self, state, kind='gate'):
        raise NotImplementedError

class RuleBasedDecisionModel(DecisionModelAdapter):
    engine = 'Local Deterministic Fallback'

    def evaluate(self, state, kind='gate'):
        if kind == 'intent':
            selected = detect_intent(state['input'])
            answers = {'intent':dict(type='choice',choice=selected,choices=list(INTENTS),
                                    confidence=None,probabilities=None,reason='Keyword heuristic; ambiguous input still requires explicit clarification')}
        else:
            sufficient = not (state['gaps'] or state['conflicts'] or state['citation_conflicts'])
            high = bool(state['conflicts'] or state['citation_conflicts'] or state['methodological_uncertainty'])
            risk = 2 if high else 1 if state['gaps'] else 0
            escalation = high or state['impact']=='high'
            route = 'escalate_to_human' if escalation else 'request_more_information' if not sufficient else 'continue_ai_review'
            answers = {
                'evidence_sufficient':dict(type='binary_rule',value=sufficient,probability=None),
                'risk':dict(type='ordered_rule',score=risk,level=['low','medium','high','critical'][risk],confidence=None),
                'routing':dict(type='choice_rule',choice=route,choices=list(ROUTES),confidence=None),
                'human_escalation':dict(type='binary_rule',value=escalation,probability=None),
            }
        return dict(engine=self.engine,model=None,answers=answers,questions=questions(kind),usage=None,
                    api_calls=0,cost_usd=None,calibration='Deterministic rules have no model probabilities or calibrated confidence')


def unit_number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0 <= value <= 1


def validate_response(obj, requested):
    if not isinstance(obj,dict) or not isinstance(obj.get('model'),str) or not isinstance(obj.get('answers'),dict):
        raise ValueError('Invalid Jev response envelope')
    if set(obj['answers']) != set(requested):
        raise ValueError('Jev answer keys do not match request')
    usage = obj.get('usage')
    if not isinstance(usage,dict) or any(not isinstance(usage.get(k),int) or isinstance(usage[k],bool) or usage[k]<0 for k in ('input_tokens','output_tokens')):
        raise ValueError('Invalid Jev token usage')
    for key, q in requested.items():
        a = obj['answers'][key]
        if not isinstance(a,dict) or a.get('type') != q['type']:
            raise ValueError('Jev answer type mismatch')
        if q['type']=='noul':
            if not unit_number(a.get('noul')):
                raise ValueError('Invalid Jev Noul probability')
            continue
        p = a.get('probabilities')
        expected = set(q['criteria']) if q['type']=='choice' else {str(i) for i in range(len(q['criteria']))}
        if not isinstance(p,dict) or set(p)!=expected or not all(unit_number(v) for v in p.values()) or abs(sum(p.values())-1)>.01 or not unit_number(a.get('confidence')):
            raise ValueError('Invalid Jev distribution or confidence')
        if q['type']=='choice':
            if a.get('choice') not in expected or p[a['choice']] < max(p.values())-1e-6:
                raise ValueError('Invalid Jev choice')
        else:
            score = a.get('score')
            if not isinstance(score,(int,float)) or isinstance(score,bool) or not math.isfinite(score) or not 0<=score<=len(q['criteria'])-1:
                raise ValueError('Invalid Jev score')
            if a.get('legend')!={str(i):x for i,x in enumerate(q['criteria'])}:
                raise ValueError('Invalid Jev score legend')
            if abs(score-sum(int(i)*v for i,v in p.items()))>.02:
                raise ValueError('Inconsistent Jev weighted score')
    return obj

class JevDecisionModel(DecisionModelAdapter):
    engine = 'Jev'
    endpoint = 'https://api.typesafe.ai/v1/systemone'

    def __init__(self, key=None, model=None):
        self.key = key or os.environ.get('JEVMODEL_API_KEY','')
        self.model = model or os.environ.get('JEVMODEL_MODEL','jev-latest')
        if not self.key:
            raise ValueError('JEVMODEL_API_KEY is required for Jev')

    def evaluate(self, state, kind='gate'):
        qs = questions(kind)
        payload = dict(model=self.model,state=state,questions=qs)
        request = Request(self.endpoint,data=json.dumps(payload,allow_nan=False).encode(),
                          headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        # One bounded call: no automatic retries that might silently add cost.
        with urlopen(request,timeout=20) as response:
            raw = response.read(1_000_001)
        if len(raw)>1_000_000:
            raise ValueError('Jev response exceeds limit')
        obj = validate_response(json.loads(raw),qs)
        return dict(engine=self.engine,model=obj['model'],answers=obj['answers'],questions=qs,
                    usage=obj['usage'],api_calls=1,cost_usd=None,
                    calibration='Vendor confidence/probabilities; calibration on this research domain has not been measured')


def configured_model():
    return JevDecisionModel() if os.environ.get('JEVMODEL_API_KEY') else RuleBasedDecisionModel()


def safe_evaluate(adapter, state, kind='gate'):
    try:
        return adapter.evaluate(state,kind)
    except Exception as exc:
        if not isinstance(adapter,JevDecisionModel):
            raise
        result = RuleBasedDecisionModel().evaluate(state,kind)
        result['provider_failure'] = dict(provider='Jev',error_type=type(exc).__name__,
            message='Jev unavailable or invalid response; local rules used. Raw errors omitted to protect credentials.',attempted_api_calls=1)
        return result
