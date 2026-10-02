"""Inspectable proxies, not a semantic judge or calibrated probability model."""
from collections import Counter
from datetime import datetime


def ratio(n, d):
    return n / d if d else None


def enrich(findings, chunks):
    from .core import retrieve
    for f in findings:
        retrieved = retrieve(f['query'], chunks, f.get('fact_key'))
        # The structured conflict scan is a second retrieval channel.
        scan = [c for c in chunks if c.get('fact_key') and c['fact_key'] == f.get('fact_key')]
        pool = {c['id']: c for c in retrieved + scan}
        f['retrieved_sources'] = list(pool.values())
        f['claims'] = [dict(id=f['id']+'-E'+str(i), text=e['text'],
                            evidence_ids=[e['id']], quote=e['text'],
                            support='supported', method='extractive_identity')
                       for i, e in enumerate(f['evidence'], 1)]
        if f['llm']:
            f['claims'].append(dict(id=f['id']+'-LLM', text=f['llm']['suggestion'],
                evidence_ids=[c['id'] for c in f['llm']['citations']],
                support='unverified', method='human_semantic_review_required'))
        f['recommendation'] = {'text': f['llm']['suggestion'] if f['llm'] else f['suggestion'],
                               'evidence_ids': [e['id'] for e in f['evidence']],
                               'decision': 'revise' if f['kind'] != 'candidate' else 'review',
                               'basis': 'conservative rule result; human interpretation required'}
        f['confidence'] = {'value': .3 if f['kind'] in {'missing','conflict'} else .6,
                           'kind': 'uncalibrated triage heuristic, not probability'}
        f['routing'] = ['human_final_decision_required']
        if f['confidence']['value'] < .5: f['routing'].append('low_confidence')
        if f['kind'] == 'missing': f['routing'].append('insufficient_evidence')
        if f['kind'] == 'conflict': f['routing'].append('evidence_conflict')
        if f.get('impact') == 'high': f['routing'].append('high_impact')
        if f['llm']: f['routing'].append('unverified_model_interpretation')
        f['final_decision'] = None
        f['support_reviews'] = {}
        f['rca'] = []
        f['trace'] = [dict(stage='retrieval', ids=list(pool)),
                      dict(stage='evidence_selection', ids=[e['id'] for e in f['evidence']]),
                      dict(stage='analysis', claim_ids=[c['id'] for c in f['claims']]),
                      dict(stage='recommendation', **f['recommendation'])]


def claim_status(f, claim):
    evidence = {e['id']: e for e in f['evidence']}
    if not claim['evidence_ids'] or any(i not in evidence for i in claim['evidence_ids']):
        return 'unsupported'
    human = f.get('support_reviews', {}).get(claim['id'], {}).get('verdict')
    if human in {'unsupported','conflict'}: return human
    if claim['method'] == 'extractive_identity':
        return 'supported' if all(claim['text'] == evidence[i]['text'] for i in claim['evidence_ids']) else 'unsupported'
    return f.get('support_reviews', {}).get(claim['id'], {}).get('verdict', 'unverified')


def evaluate(data, log):
    findings = data['findings']
    claims = [(f,c) for f in findings for c in f.get('claims', [])]
    statuses = [claim_status(f,c) for f,c in claims]
    decisions = [f for f in findings if f.get('final_decision')]
    bad = [f for f in findings if f.get('kind') in {'missing','conflict','blocked'} or
           any(claim_status(f,c) != 'supported' for c in f.get('claims', [])) or
           (f.get('final_decision') or {}).get('override') or f.get('rca') or 'evaluation_conflict' in f.get('routing',[])]
    causes = [r['category'] for f in findings for r in f.get('rca', []) if r['validated']]
    times = [(datetime.fromisoformat(f['final_decision']['timestamp']) - datetime.fromisoformat(log[0]['timestamp'])).total_seconds() for f in decisions]
    repeats = data.get('repeat_recommendations', [])
    consistency = {}
    if len(repeats) >= 2:
        for f in findings:
            valid = [row[f['id']] for row in repeats if row[f['id']] != '__MODEL_FAILURE__']
            consistency[f['id']] = ratio(max(Counter(valid).values()) if valid else 0, len(repeats))
    return dict(
        evidence_coverage=ratio(sum(bool(c['evidence_ids']) and all(i in {e['id'] for e in f['evidence']} for i in c['evidence_ids']) for f,c in claims),len(claims)),
        claim_evidence_consistency=ratio(statuses.count('supported'),len(statuses)),
        unverified_claims=statuses.count('unverified'), unsupported_claims=statuses.count('unsupported'),
        recommendation_consistency=consistency,
        ai_human_agreement=ratio(sum(f['recommendation']['decision']==f['final_decision']['decision'] for f in decisions),len(decisions)),
        human_override_rate=ratio(sum(f['final_decision']['override'] for f in decisions),len(decisions)),
        review_lead_time_seconds=ratio(sum(times),len(times)),
        reviewer_workload_proxy=dict(pending_final_decisions=len(findings)-len(decisions),human_events=len(log)-1),
        badcase_rate=ratio(len(bad),len(findings)),
        root_cause_distribution=dict(Counter(causes)),
        denominators=dict(claims=len(claims),final_decisions=len(decisions),findings=len(findings),validated_diagnoses=len(causes)),
        caveat='Synthetic descriptive proxies. Unverified claims count as not supported. Badcase means investigation candidate, not proven AI error. Lead time includes idle time; events are not effort savings.')
