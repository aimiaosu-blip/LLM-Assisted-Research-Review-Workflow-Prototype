"""Execute synthetic governance, diagnosis, feedback and replay. Use a fresh output path."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reviewflow.__main__ import run
from reviewflow.governance import record
from reviewflow.storage import connect,state
from reviewflow.regression import promote,retest
from reviewflow.improvement import feedback
from reviewflow.dashboard import export
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='runs/v4-demo');args=parser.parse_args()
    run(argparse.Namespace(input=str(ROOT/'sample_data'),criteria=None,out=args.out,model=None,data_label='SYNTHETIC V4 DEMO',repeats=3))
    record(args.out,'C1','final','Synthetic decision owner',0,decision='approve',role='decision_owner',reason='Reviewed source evidence for the limited participant-count check.',override_reason='Human resolves the rule baseline review abstention; not an AI error.')
    record(args.out,'C2','final','Synthetic decision owner',0,decision='revise',role='decision_owner',reason='Reconcile the conflicting retention records.')
    diagnosis=json.loads((ROOT/'demo/retention_rca.json').read_text())
    record(args.out,'C2','rca','Synthetic policy reviewer',1,**diagnosis)
    db=connect(args.out)
    try:data,_=state(db)
    finally:db.close()
    f=data['findings'][1]
    target=Path(args.out)/'regression/retention.json'
    promote(args.out,'C2',target,'conflict',[e['id'] for e in f['evidence']])
    result=retest(target)
    (Path(args.out)/'retest.json').write_text(json.dumps(result,indent=2))
    feedback(args.out,'C2',Path(args.out)/'feedback.json','L2')
    export(args.out)
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':sys.exit(main())
