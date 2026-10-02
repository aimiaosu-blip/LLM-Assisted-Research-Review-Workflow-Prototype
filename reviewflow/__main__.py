import argparse
import json
import sqlite3
import sys
from pathlib import Path
from .core import ingest, review, ollama_review
from .storage import connect, append, state, decide
from .dashboard import export


def run(args):
    folder = Path(args.input)
    documents, chunks = ingest(folder)
    criteria = json.loads(Path(args.criteria or folder/'criteria.json').read_text(encoding='utf-8'))
    findings = review(criteria, chunks)
    mode = 'deterministic rules (not an LLM)'
    errors = []
    if args.model:
        mode = 'Ollama requested: '+args.model
        for f in findings:
            if not f['evidence']:
                continue
            try:
                f['llm'] = ollama_review(f, args.model)
            except Exception as exc:
                errors.append({'finding':f['id'],'error_type':type(exc).__name__,'message':'LLM unavailable or output invalid; deterministic recommendation retained.'})
        mode += f'; {sum(f["llm"] is not None for f in findings)} validated drafts; {len(errors)} fallbacks'
    out = Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    db = connect(out)
    try:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT COUNT(*) FROM events').fetchone()[0]:
            raise ValueError('Run already exists; choose a new --out directory')
        append(db, {'action':'created','snapshot':{'data_label':args.data_label,'mode':mode,'documents':documents,'chunks':chunks,'findings':findings,'model_errors':errors,'criteria':criteria}})
        db.commit()
    finally:
        db.close()
    export(out)
    print(f'Review ready: {out}/dashboard.html')
    for f in findings:
        print(f'{f["id"]}: {f["kind"]} / pending / revision 0')


def main():
    p = argparse.ArgumentParser(description='Evidence-first research review. All bundled data are synthetic.')
    sub = p.add_subparsers(dest='command',required=True)
    r = sub.add_parser('run')
    r.add_argument('--input',default='sample_data')
    r.add_argument('--criteria')
    r.add_argument('--out',default='runs/demo')
    r.add_argument('--model',help='Opt-in local Ollama model name; failures fall back to rules')
    r.add_argument('--data-label',default='SYNTHETIC SAMPLE DATA',help='Change when using your own non-synthetic inputs')
    d = sub.add_parser('decide')
    d.add_argument('finding')
    d.add_argument('action',choices=['approve','reject','revise'])
    d.add_argument('--out',default='runs/demo')
    d.add_argument('--reviewer',required=True)
    d.add_argument('--note',required=True)
    d.add_argument('--revision',type=int,required=True)
    d.add_argument('--replacement',default='')
    for name in ('export','verify'):
        sub.add_parser(name).add_argument('--out',default='runs/demo')
    args = p.parse_args()
    try:
        if args.command == 'run':
            run(args)
        elif args.command == 'decide':
            decide(args.out,args.finding,args.action,args.reviewer,args.note,args.revision,args.replacement)
            export(args.out)
            print('Decision recorded; dashboard refreshed.')
        elif args.command == 'export':
            export(args.out)
        else:
            db = connect(args.out)
            try:
                data, log = state(db)
                print(f'Chain valid: {len(log)} events; {len(data["findings"])} findings. Not tamper-proof.')
            finally:
                db.close()
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        print(f'Error: {exc}',file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
