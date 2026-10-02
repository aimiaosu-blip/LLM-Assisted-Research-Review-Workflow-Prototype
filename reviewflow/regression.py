"""Validated human diagnoses become frozen replay inputs and explicit expectations."""
import json
from pathlib import Path
from .storage import connect, state
from .core import review
from .evaluation import enrich, claim_status


def promote(out, finding_id, target, expected_kind, required_evidence):
    db=connect(out)
    try: data,log=state(db)
    finally: db.close()
    f=next((f for f in data['findings'] if f['id']==finding_id),None)
    if f is None or not f.get('rca'): raise ValueError('Validated RCA required before promotion')
    if expected_kind not in {'candidate','conflict','blocked','missing'}: raise ValueError('Invalid expected kind')
    if not f['rca'][-1].get('validated') or not f['rca'][-1].get('validation_evidence'):
        raise ValueError('Human validation evidence required')
    if not required_evidence and expected_kind != 'missing':
        raise ValueError('Non-missing cases require explicit expected evidence')
    ids=set(required_evidence)
    if not ids <= {c['id'] for c in data['chunks']}: raise ValueError('Unknown expected evidence')
    case=dict(schema_version=1,synthetic_label=data['data_label'],finding=finding_id,
        criterion=next(c for c in data['criteria'] if c['id']==finding_id),chunks=data['chunks'],
        diagnosis=f['rca'][-1],expected_kind=expected_kind,required_evidence=sorted(ids),
        limitation='Replays deterministic retrieval/selection/rules only, not live LLM or human judgment',
        original_kind=f['kind'])
    path=Path(target); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as handle: json.dump(case,handle,indent=2)
    return case


def retest(path):
    case=json.loads(Path(path).read_text())
    f=review([case['criterion']],case['chunks'])[0]
    enrich([f],case['chunks'])
    actual={e['id'] for e in f['evidence']}
    missing=set(case['required_evidence'])-actual
    passed=f['kind']==case['expected_kind'] and not missing and all(claim_status(f,c)=='supported' for c in f['claims'])
    return dict(case=str(path),passed=passed,expected_kind=case['expected_kind'],actual_kind=f['kind'],missing_evidence=sorted(missing),scope=case['limitation'])
