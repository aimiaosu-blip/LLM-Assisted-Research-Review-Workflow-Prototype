"""Metadata-rich corpus, inspectable graph and constrained lexical retrieval."""
import json
from pathlib import Path
from .core import digest, tokens

ROOT = Path(__file__).resolve().parents[1]

class KnowledgeBase:
    def __init__(self, folder=None):
        self.documents, self.chunks, self.edges = {}, [], []
        for path in sorted(Path(folder or ROOT/'data/synthetic').glob('*.json')):
            raw = path.read_bytes()
            if len(raw) > 1_000_000:
                raise ValueError('Document exceeds limit')
            d = json.loads(raw)
            if d.get('synthetic') is not True:
                raise ValueError('Only explicitly synthetic demonstration data accepted')
            if d['document_id'] in self.documents:
                raise ValueError('Duplicate document ID')
            d['source_location'] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name
            d['sha256'] = digest(raw)
            self.documents[d['document_id']] = d
            for section, text in d['sections'].items():
                eid = 'EVID-'+digest((d['document_id']+section+text).encode())[:12]
                self.chunks.append(dict(evidence_id=eid, document_id=d['document_id'],
                    title=d['title'], author=d['author'], date=d['date'],
                    document_type=d['document_type'], research_area=d['research_area'],
                    section=section, text=text, source_location=d['source_location']+'#$.sections.'+section,
                    sha256=d['sha256'], citation_relationships=d['citations'], scope=d.get('scope','internal')))
                if section in {'related_work','methodology','validation','ethics'}:
                    self.edges.append({'source':eid,'type':'supports_claim','target':d['document_id']+':'+section})
            self.edges.extend([
                {'source':d['document_id'],'type':'authored_by','target':d['author']},
                {'source':d['document_id'],'type':'belongs_to_topic','target':d['research_area']}])
            self.edges.extend({'source':d['document_id'],'type':'cites','target':x} for x in d['citations'])
            self.edges.extend({'source':d['document_id'],'type':x['type'],'target':x['target']} for x in d['relations'])
        if not self.documents:
            raise ValueError('Empty knowledge base')

    def relationships(self, ids):
        ids = set(ids)
        return [e for e in self.edges if e['source'] in ids or e['target'] in ids]

    def retrieve(self, state, query, k=12):
        q = tokens(query)
        proposal = self.documents[state['proposal_id']]
        cited = set(proposal['citations'])
        neighbors = {e['target'] for e in self.relationships(cited)} | {e['source'] for e in self.relationships(cited)}
        ranked = []
        for c in self.chunks:
            # Proposal remains separate task context; never counts as independent supporting evidence.
            if c['document_type']=='proposal' or c['document_type'] in state['excluded_sources']:
                continue
            year = int(c['date'][:4])
            if not state['time_range']['start'] <= year <= state['time_range']['end']:
                continue
            if state['scope'] != 'internal_and_academic' and c['scope'] != state['scope']:
                continue
            if c['research_area'] != state['research_topic']:
                continue
            score = len(q & tokens(c['text']+' '+c['title']+' '+c['research_area'])) / max(len(q),1)
            related = c['document_id'] in cited or c['document_id'] in neighbors
            if related:
                score += .15
            if score:
                ranked.append(dict(c,retrieval_score=round(score,5),
                                   relationship='graph-linked related work' if related else 'topic and lexical match'))
        result = sorted(ranked,key=lambda c:(-c['retrieval_score'],c['evidence_id']))[:k]
        # Preserve filtered contradiction witnesses even when ordinary top-k drops one side.
        ids = {e['document_id'] for e in result}
        conflict_ids = {e['source'] for e in self.edges if e['type']=='contradicts' and (e['source'] in ids or e['target'] in ids)} | {e['target'] for e in self.edges if e['type']=='contradicts' and (e['source'] in ids or e['target'] in ids)}
        result_ids = {e['evidence_id'] for e in result}
        result += [dict(c,relationship='contradiction witness') for c in ranked if c['document_id'] in conflict_ids and c['section']=='validation' and c['evidence_id'] not in result_ids]
        return result

    def analyze(self, state, evidence):
        proposal = self.documents[state['proposal_id']]
        mandatory = proposal.get('mandatory_evidence',[])
        covered = sorted({e['section'] for e in evidence} & set(mandatory))
        ids = {e['document_id'] for e in evidence}
        conflicts = [e for e in self.edges if e['type']=='contradicts' and e['source'] in ids and e['target'] in ids]
        citation_conflicts = [x for x in proposal['citations'] if x not in self.documents]
        uncertainty = any('no control group' in e['text'].lower() for e in evidence)
        return dict(mandatory=mandatory, covered=covered, gaps=sorted(set(mandatory)-set(covered)),
                    conflicts=conflicts, citation_conflicts=citation_conflicts, methodological_uncertainty=uncertainty,
                    impact=state['impact'], evidence_ids=[e['evidence_id'] for e in evidence])
