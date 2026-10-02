"""Local-only interactive demo. No authentication or production deployment claim."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .knowledge import KnowledgeBase
from .workspace import Workspace

ROOT=Path(__file__).resolve().parents[1]


def make_handler(workspace):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, value, status=200):
            raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers(); self.wfile.write(raw)

        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.allowed_host(): return self.reply({'error':'Local host only'},403)
            parsed=urlparse(self.path)
            try:
                if parsed.path=='/':
                    raw=(ROOT/'reviewflow/ui.html').read_bytes()
                    self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
                    self.send_header('X-Content-Type-Options','nosniff')
                    self.end_headers(); self.wfile.write(raw); return
                if parsed.path=='/api/catalog':
                    return self.reply(dict(proposals=[d for d in workspace.kb.documents.values() if d['document_type']=='proposal'],
                        documents=len(workspace.kb.documents),configured_decision_engine=workspace.adapter.engine,
                        configured_synthesis='Ollama' if workspace.llm.model else 'Local Extractive Synthesis (not an LLM)',policy=workspace.policy))
                sid=parse_qs(parsed.query).get('id',[''])[0]
                current,log=workspace.read(sid)
                if parsed.path=='/api/workspace': return self.reply(dict(workspace=current,audit=log,metrics=workspace.metrics(sid)))
                if parsed.path=='/api/export': return self.reply(dict(synthetic=True,workspace=current,audit=log,metrics=workspace.metrics(sid)))
                return self.reply({'error':'Not found'},404)
            except (ValueError,KeyError,OSError) as exc:
                return self.reply({'error':str(exc)},400)

        def do_POST(self):
            if not self.allowed_host(): return self.reply({'error':'Local host only'},403)
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://localhost:{self.server.server_port}',f'http://127.0.0.1:{self.server.server_port}'}:
                return self.reply({'error':'Cross-origin mutation rejected'},403)
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.reply({'error':'JSON content type required'},415)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=32000: raise ValueError('Invalid request size')
                obj=json.loads(self.rfile.read(size))
                if not isinstance(obj,dict): raise ValueError('Request must be an object')
                path=urlparse(self.path).path
                if path=='/api/create': result=workspace.create(obj.get('proposal_id','PROP-001'))
                elif path=='/api/ask': result=workspace.ask(obj['id'],obj.get('text',''),obj['revision'],obj.get('intent'),obj.get('settings'),obj.get('question_id'))
                elif path=='/api/decide':
                    result=workspace.decide(obj['id'],obj['revision'],obj['action'],obj['reviewer'],obj['rationale'],
                        obj.get('override_reason',''),obj.get('role',''),obj.get('semantic_support_confirmed',False),obj.get('revised_proposal',''))
                else: return self.reply({'error':'Not found'},404)
                return self.reply({'workspace':result})
            except (ValueError,KeyError,TypeError,OSError) as exc:
                return self.reply({'error':str(exc)},400)

    return Handler


def main():
    parser=argparse.ArgumentParser(description='Synthetic local research review workspace')
    parser.add_argument('--port',type=int,default=8765); parser.add_argument('--out',default='runs/workspaces')
    args=parser.parse_args()
    workspace=Workspace(args.out,KnowledgeBase())
    server=HTTPServer(('127.0.0.1',args.port),make_handler(workspace))
    print(f'Synthetic research workspace: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
