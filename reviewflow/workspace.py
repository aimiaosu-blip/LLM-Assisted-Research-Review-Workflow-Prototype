"""Transactional multi-turn workspace with append-only audit snapshots."""
import copy
import uuid
from datetime import datetime
from pathlib import Path
from .storage import connect, append, events
from .context import initial_state, update_state, clarification, rewrite
from .decision import configured_model, safe_evaluate
from .synthesis import GenerativeLLM
from .policy import load_policy, route
from .recommendation import next_questions

class Workspace:
    def __init__(self, folder, kb, adapter=None, llm=None, policy=None):
        self.folder=Path(folder); self.folder.mkdir(parents=True,exist_ok=True)
        self.kb=kb; self.adapter=adapter or configured_model(); self.llm=llm or GenerativeLLM()
        self.policy=policy or load_policy()

    def _journal(self, sid):
        if not isinstance(sid,str) or len(sid)!=32 or any(c not in '0123456789abcdef' for c in sid):
            raise ValueError('Invalid workspace ID')
        directory=self.folder/sid
        if not directory.is_dir(): raise ValueError('Unknown workspace')
        return connect(directory)

    def read(self, sid):
        db=self._journal(sid)
        try:
            log=events(db)
            if not log: raise ValueError('Empty workspace')
            return copy.deepcopy(log[-1]['snapshot']),log
        finally: db.close()

    def create(self, proposal_id='PROP-001'):
        proposal=self.kb.documents.get(proposal_id)
        if not proposal or proposal['document_type']!='proposal': raise ValueError('Select a synthetic proposal')
        sid=uuid.uuid4().hex; directory=self.folder/sid; directory.mkdir()
        snapshot=dict(id=sid,revision=0,synthetic=True,proposal=proposal,
            state=initial_state(proposal),clarification=clarification(initial_state(proposal)),
            review=None,final_decision=None,policy=self.policy)
        db=connect(directory)
        try:
            append(db,dict(action='workspace_created',snapshot=snapshot)); db.commit()
        finally: db.close()
        return snapshot

    def _commit(self, sid, previous_revision, action, snapshot, **payload):
        db=self._journal(sid)
        try:
            db.execute('BEGIN IMMEDIATE')
            log=events(db)
            if log[-1]['snapshot']['revision']!=previous_revision: raise ValueError('Stale revision: reload workspace')
            snapshot['revision']=previous_revision+1
            append(db,dict(action=action,snapshot=snapshot,**payload)); db.commit()
        except Exception:
            db.rollback(); raise
        finally: db.close()
        return snapshot

    def ask(self, sid, text, revision, intent=None, settings=None, question_id=None):
        current,_=self.read(sid)
        if current['revision']!=revision: raise ValueError('Stale revision: reload workspace')
        if current['final_decision']: raise ValueError('Final decision already recorded; create a new workspace')
        if question_id:
            if not current['review']: raise ValueError('No recommended questions')
            q=next((q for q in current['review']['next_questions'] if q['id']==question_id),None)
            if not q: raise ValueError('Unknown recommended question')
            text,intent=q['text'],q['intent']
        state=update_state(current['state'],text,intent,settings)
        classification=safe_evaluate(self.adapter,{'input':text,'research_state':state},'intent')
        # Ambiguous requests are never silently converted into a closed-set model guess.
        # User choice and the deterministic clarity check control whether investigation begins.
        current['state']=state; current['clarification']=clarification(state)
        if current['clarification']['required']:
            current['review']=None
            guidance=self.llm.prepare(state)
            current['guidance']=guidance
            current['clarification']['question']=guidance['clarification_question']
            return self._commit(sid,revision,'clarification_requested',current,
                original_input=text,decision_model_output=classification,llm_preparation=guidance,clarification=current['clarification'])
        if question_id:
            state['investigated_questions']=sorted(set(state.get('investigated_questions',[])+[question_id]))
        guidance=self.llm.prepare(state,rewrite(state))
        current['guidance']=guidance
        query=guidance['rewritten_query']
        evidence=self.kb.retrieve(state,query)
        analysis=self.kb.analyze(state,evidence)
        # Policy owns defaults; proposal-specific mandatory sections narrow the investigation.
        if not analysis['mandatory']:
            analysis['mandatory']=self.policy['mandatory_evidence']
            analysis['covered']=sorted({e['section'] for e in evidence}&set(analysis['mandatory']))
            analysis['gaps']=sorted(set(analysis['mandatory'])-set(analysis['covered']))
        decisions=safe_evaluate(self.adapter,dict(analysis,research_state=state,evidence=evidence))
        gate=route(analysis,decisions,self.policy)
        synthesis=self.llm.review(state,query,evidence,analysis)
        if synthesis.get('provider_failure') or synthesis.get('generated_claim'):
            gate['route']='escalate_to_human'
            gate['reasons'].append('generated_rationale_requires_human_semantic_review' if synthesis.get('generated_claim') else 'synthesis_provider_failure')
        state['unresolved_questions']=analysis['gaps']+(['conflicting_findings'] if analysis['conflicts'] else [])+analysis['citation_conflicts']
        state['decision_stage']='human_review' if gate['route']=='escalate_to_human' else 'investigation'
        recommendation='revise' if analysis['gaps'] or analysis['conflicts'] or analysis['citation_conflicts'] else 'approve'
        review=dict(research_question=query,rewritten_query=query,recommendation=recommendation,
            recommendation_basis='Inspection of retrieved independent sections and configured policy; AI recommendation only',
            recommendation_evidence_ids=analysis['evidence_ids'],evidence=evidence,analysis=analysis,
            synthesis=synthesis,intent_classification=classification,decision_model=decisions,gate=gate,
            key_findings=synthesis['findings'],evidence_gaps=analysis['gaps'],conflicting_evidence=analysis['conflicts'],
            risks=['methodological_uncertainty'] if analysis['methodological_uncertainty'] else [],
            human_review_required=True,next_questions=next_questions(state,analysis,evidence),
            relationships=self.kb.relationships([state['proposal_id']]+[e['document_id'] for e in evidence]))
        current['review']=review
        return self._commit(sid,revision,'investigation_completed',current,original_input=text,
            selected_next_question=question_id,structured_research_state=state,rewritten_query=query,
            retrieved_evidence_ids=analysis['evidence_ids'],llm_preparation=guidance,llm_output=synthesis,decision_model_output=decisions,
            active_decision_engine=decisions['engine'],routing_decision=gate,next_questions=review['next_questions'])

    def decide(self, sid, revision, action, reviewer, rationale, override_reason='', role='decision_owner',
               semantic_support_confirmed=False, revised_proposal=''):
        current,_=self.read(sid)
        if current['revision']!=revision: raise ValueError('Stale revision: reload workspace')
        if current['final_decision']: raise ValueError('Final decision already recorded')
        if not current['review']: raise ValueError('Complete an investigation first')
        if action not in {'approve','reject','revise','escalate'} or role!=self.policy['final_decision_role']:
            raise ValueError('Valid action and declared decision_owner role required')
        if not reviewer.strip() or not rationale.strip(): raise ValueError('Reviewer and rationale are required')
        review=current['review']; override=action!=review['recommendation']
        if override and not override_reason.strip(): raise ValueError('Override reason required')
        if action=='approve':
            if review['analysis']['gaps'] or review['analysis']['conflicts'] or review['analysis']['citation_conflicts']:
                raise ValueError('Unresolved mandatory evidence or conflicts: correct the packet before approval')
            if review['synthesis'].get('generated_claim') and semantic_support_confirmed is not True:
                raise ValueError('Human semantic support confirmation required for generated rationale')
        if action=='revise' and not revised_proposal.strip(): raise ValueError('Describe the proposed revision')
        decision=dict(action=action,reviewer=reviewer.strip(),rationale=rationale.strip(),override=override,
            override_reason=override_reason.strip(),role=role,semantic_support_confirmed=semantic_support_confirmed,
            revised_proposal=revised_proposal.strip(),
            authority='Human-owned prototype disposition; no real organizational authorization')
        current['final_decision']=decision; current['state']['decision_stage']='finalized' if action!='escalate' else 'escalated'
        return self._commit(sid,revision,'human_decision',current,human_action=decision,override_status=override)

    def metrics(self, sid):
        current,log=self.read(sid)
        reviews=[e for e in log if e['action']=='investigation_completed']
        final=[e for e in log if e['action']=='human_decision']
        review=current['review']
        analysis=review['analysis'] if review else None
        usage=[]; attempted=0
        for event in log:
            for key in ('decision_model_output','llm_output','llm_preparation'):
                out=event.get(key,{})
                attempted+=out.get('api_calls',0)+out.get('provider_failure',{}).get('attempted_api_calls',0)
                if isinstance(out.get('usage'),dict): usage.append(out['usage'])
            if event['action']=='investigation_completed':
                out=event['snapshot']['review']['intent_classification']
                attempted+=out.get('api_calls',0)+out.get('provider_failure',{}).get('attempted_api_calls',0)
                if isinstance(out.get('usage'),dict): usage.append(out['usage'])
        return dict(documents_retrieved=len({e['document_id'] for e in review['evidence']}) if review else 0,
            evidence_coverage=len(analysis['covered'])/len(analysis['mandatory']) if analysis and analysis['mandatory'] else None,
            evidence_gaps=len(analysis['gaps']) if analysis else None,
            completed_investigations=len(reviews),human_decisions=len(final),
            human_override_rate=sum(e['override_status'] for e in final)/len(final) if final else None,
            recommendation_acceptance_rate=sum(not e['override_status'] for e in final)/len(final) if final else None,
            escalation_rate=sum(e['routing_decision']['route']=='escalate_to_human' for e in reviews)/len(reviews) if reviews else None,
            review_lead_time_seconds=(datetime.fromisoformat(final[-1]['timestamp'])-datetime.fromisoformat(log[0]['timestamp'])).total_seconds() if final else None,
            model_api_calls_attempted=attempted,input_tokens=sum(x['input_tokens'] for x in usage),
            output_tokens=sum(x['output_tokens'] for x in usage),cost_usd=None,retrieval_gold_coverage=None,
            caveat='Synthetic session metrics. Coverage = mandatory sections retrieved / mandatory sections; not semantic sufficiency. Lead time includes idle time. Unmeasured cost and gold recall remain null.')
