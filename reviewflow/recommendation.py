"""Next questions tied to evidence gaps, relationships, state and review stage."""

def next_questions(state, analysis, evidence):
    candidates=[]
    def add(id, text, intent, reason, ids=None):
        candidates.append(dict(id=id,text=text,intent=intent,reason=reason,evidence_ids=ids or [],
                               stage=state['decision_stage'],source_intent=state['intent']))
    if analysis['conflicts']:
        pair=analysis['conflicts'][0]
        ids=[e['evidence_id'] for e in evidence if e['document_id'] in {pair['source'],pair['target']}]
        add('conflicting_findings',f"Why do {pair['source']} and {pair['target']} disagree, and which methodological differences explain it?",'methodology','Contradictory retrieved research',ids)
    if analysis['gaps']:
        gap=analysis['gaps'][0]
        add('missing_'+gap,f'Which approval criteria still lack {gap} evidence, and what should be supplied?','evidence','Missing mandatory evidence: '+gap)
    if analysis['citation_conflicts']:
        add('citation_conflict','Can the unresolved citation '+analysis['citation_conflicts'][0]+' be verified or corrected?','citation_consistency','Citation target absent from knowledge base')
    if state['intent'] in {'novelty','related_work'}:
        ids=[e['evidence_id'] for e in evidence if e['section']=='related_work']
        if ids:
            add('novelty_challenge','Which prior studies most strongly challenge the novelty claim?','novelty','Overlapping related work was retrieved',ids)
    if analysis['methodological_uncertainty']:
        add('methodology_gap','Which controlled baseline and held-out validation would address the methodological uncertainty?','methodology','Retrieved internal pilot lacks a control group')
    if state['decision_stage']=='human_review':
        add('decision_readiness','What evidence and unresolved questions must the human decision owner inspect before disposition?','approval_readiness','Current stage is human review',[e['evidence_id'] for e in evidence[:2]])
    add('related_scope','Which related internal and academic studies are still relevant within the current date and source constraints?','related_work','Expand comparison while preserving existing constraints',[e['evidence_id'] for e in evidence[:2]])
    add('evidence_check','Which retrieved passages support the mandatory review criteria, and which links need human verification?','evidence','Verify source support, not just citation existence',[e['evidence_id'] for e in evidence[:2]])
    resolved=set(state['resolved_questions']) | set(state.get('investigated_questions',[]))
    return [q for q in candidates if q['id'] not in resolved][:3]
