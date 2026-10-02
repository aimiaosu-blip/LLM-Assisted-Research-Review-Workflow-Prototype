"""SQLite event journal; hashes detect edits, not a security boundary."""
import copy
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def connect(out):
    db = sqlite3.connect(Path(out)/'review.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL)')
    return db


def append(db, payload):
    previous = db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
    previous = previous[0] if previous else '0'*64
    payload = dict(payload, timestamp=datetime.now(timezone.utc).isoformat())
    raw = canonical(payload)
    h = hashlib.sha256((previous+raw).encode()).hexdigest()
    db.execute('INSERT INTO events(payload,previous,hash) VALUES(?,?,?)', (raw, previous, h))


def events(db):
    rows = db.execute('SELECT payload,previous,hash FROM events ORDER BY seq').fetchall()
    previous = '0'*64
    result = []
    for raw, prev, h in rows:
        if prev != previous or hashlib.sha256((prev+raw).encode()).hexdigest() != h:
            raise ValueError('Audit chain mismatch')
        result.append(json.loads(raw))
        previous = h
    return result


def state(db):
    log = events(db)
    if not log or log[0]['action'] != 'created':
        raise ValueError('No initialized review run')
    data = copy.deepcopy(log[0]['snapshot'])
    for event in log[1:]:
        finding = next(f for f in data['findings'] if f['id'] == event['finding'])
        if event['action'] in {'support','final','rca'}:
            finding['revision'] = event['revision']
            finding['trace'].append(dict(stage='human_review', **event))
            if event['action']=='support': finding['support_reviews'][event['claim']] = event
            elif event['action']=='final': finding['final_decision'] = event
            else: finding['rca'].append(event)
            continue
        finding.update(status={'approve':'approved','reject':'rejected','revise':'revised'}[event['action']], revision=event['revision'], note=event['note'], reviewer=event['reviewer'])
        if event['action'] == 'revise':
            finding['suggestion'] = event['replacement']
    return data, log


def decide(out, finding_id, action, reviewer, note, expected_revision, replacement=''):
    if action not in {'approve','reject','revise'} or not reviewer.strip() or not note.strip():
        raise ValueError('Valid action, reviewer and rationale are required')
    if action == 'revise' and not replacement.strip():
        raise ValueError('Revision requires replacement text')
    db = connect(out)
    try:
        db.execute('BEGIN IMMEDIATE')
        data, _ = state(db)
        finding = next((f for f in data['findings'] if f['id'] == finding_id), None)
        if finding is None:
            raise ValueError('Unknown finding')
        if finding.get('final_decision'):
            raise ValueError('Final decision already recorded')
        if finding['revision'] != expected_revision:
            raise ValueError('Stale revision: reload the dashboard')
        if finding['status'] in {'approved','rejected'}:
            raise ValueError('Terminal decision: create a new run to reconsider')
        append(db, {'action':action,'finding':finding_id,'reviewer':reviewer.strip(),'note':note.strip(),'replacement':replacement,'revision':expected_revision+1})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
