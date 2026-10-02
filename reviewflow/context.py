"""Explicit state preserves constraints; summaries cannot erase state fields."""
import copy
import re

INTENTS = {
    'novelty': 'Novelty', 'related_work': 'Related research',
    'evidence': 'Evidence completeness', 'methodology': 'Methodology',
    'citation_consistency': 'Citation consistency', 'approval_readiness': 'Approval readiness',
}
KEYWORDS = {
    'novelty': ['novelty', 'novel', 'original'],
    'related_work': ['similar', 'related research', 'related work', 'done before'],
    'evidence': ['evidence', 'completeness', 'missing'],
    'methodology': ['methodology', 'method', 'sample size'],
    'citation_consistency': ['citation', 'reference'],
    'approval_readiness': ['approval', 'approve', 'ready'],
}


def detect_intent(text):
    matches = [k for k, words in KEYWORDS.items() if any(w in text.lower() for w in words)]
    return matches[0] if len(matches) == 1 else None


def initial_state(proposal):
    return dict(intent=None, research_topic=proposal['research_area'],
                proposal_id=proposal['document_id'], scope='internal_and_academic',
                time_range={'start': 2023, 'end': 2026}, excluded_sources=[],
                decision_stage='pre_review', resolved_questions=[], investigated_questions=[], unresolved_questions=[],
                important_constraints=['traceable_evidence_required', 'human_final_decision_required'],
                impact=proposal.get('impact', 'high'), original_input='', turns=[])


def update_state(state, text, intent=None, settings=None):
    result = copy.deepcopy(state)
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('Provide a nonempty question of at most 4000 characters')
    if intent is not None and intent not in INTENTS:
        raise ValueError('Unknown review intent')
    result['intent'] = intent or detect_intent(text) or result['intent']
    if not result['original_input']:
        result['original_input'] = text
    result['turns'].append({'input': text, 'explicit_intent': intent})
    lower = text.lower()
    if re.search(r'(exclude|excluding|without|don.t (include|use)|no)\s+patents?', lower):
        result['excluded_sources'] = sorted(set(result['excluded_sources'] + ['patent']))
    if re.search(r'(include|allow)\s+patents?', lower) and not re.search(r"don.t\s+include\s+patents?", lower):
        result['excluded_sources'] = [x for x in result['excluded_sources'] if x != 'patent']
    years = re.findall(r'\b(?:19|20)\d{2}\b', text)
    if len(years) >= 2:
        result['time_range'] = {'start': int(years[0]), 'end': int(years[1])}
    elif len(years) == 1 and re.search(r'(since|after|from)', lower):
        result['time_range']['start'] = int(years[0])
    if 'internal only' in lower:
        result['scope'] = 'internal'
    elif 'academic only' in lower:
        result['scope'] = 'academic'
    elif 'internal and academic' in lower:
        result['scope'] = 'internal_and_academic'
    if settings:
        if settings.get('scope') not in {'internal', 'academic', 'internal_and_academic'}:
            raise ValueError('Invalid scope')
        result['scope'] = settings['scope']
        result['time_range'] = {'start': int(settings['start']), 'end': int(settings['end'])}
        result['excluded_sources'] = ['patent'] if settings.get('exclude_patents') else []
    if result['time_range']['start'] > result['time_range']['end']:
        raise ValueError('Start year must not exceed end year')
    return result


def clarification(state):
    if state['intent'] is None:
        return {'required': True, 'question': 'What would you like to evaluate?', 'choices': INTENTS}
    return {'required': False, 'question': '', 'choices': {}}


def rewrite(state):
    if not state['intent']:
        raise ValueError('Clarify the review objective before retrieval')
    period = state['time_range']
    excluded = ', '.join(state['excluded_sources']) or 'none'
    return (f"Retrieve {state['scope']} research from {period['start']}–{period['end']} "
            f"related to {state['research_topic']}, excluding source types: {excluded}. "
            f"Evaluate {INTENTS[state['intent']]} for proposal {state['proposal_id']}; "
            f"latest question: {state['turns'][-1]['input']}. Preserve traceable evidence and human final authority.")
