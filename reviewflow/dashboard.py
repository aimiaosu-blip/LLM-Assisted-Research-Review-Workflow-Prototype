"""Portable, read-only HTML; decisions are authenticated only by local CLI access."""
from html import escape
import json
from pathlib import Path
from .storage import connect, state
from .evaluation import evaluate


def export(out):
    db = connect(out)
    try:
        data, log = state(db)
    finally:
        db.close()
    Path(out, 'review.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    Path(out, 'audit.json').write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding='utf-8')
    metrics = evaluate(data, log)
    Path(out, 'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    esc = lambda x: escape(str(x), quote=True)
    cards = []
    for f in data['findings']:
        evidence = ''.join(f'<details><summary>{esc(e["source"])} · {esc(e["location"])}</summary><blockquote>{esc(e["text"])}</blockquote><small>Chunk {esc(e["id"])}<br>SHA-256 {esc(e["sha256"])}</small></details>' for e in f['evidence'])
        model = ''
        if f['llm']:
            model = '<h4>Local LLM draft — unverified interpretation</h4><p>'+esc(f['llm']['suggestion'])+'</p><pre>'+esc(json.dumps(f['llm']['citations'],indent=2))+'</pre>'
        final = f.get('final_decision')
        disposition = final['decision'] if final else 'awaiting final decision'
        cards.append(f'<article><div class="row"><span class="tag {esc(f["kind"])}">{esc(f["kind"])}</span><span>{esc(disposition)} · revision {f["revision"]}</span></div><h2>{esc(f["id"])} / {esc(f["title"])}</h2><p>{esc(f["suggestion"])}</p>{model}{evidence or "<p>No matches. Provenance: recorded query against the input snapshot.</p>"}<p class="muted">Query: {esc(f["query"])}</p><p>Reviewer note: {esc(final["reason"] if final else f["note"]) or "Awaiting human review"}</p></article>')
    pending = sum(not f.get('final_decision') for f in data['findings'])
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research Review / Evidence Desk</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f0f3f5;color:#18303c;font:16px/1.6 system-ui}main{max-width:1100px;margin:auto;padding:44px 24px}header{background:#123747;color:white;padding:32px;border-radius:20px}h1{font-size:34px;line-height:1.2}h2{font-size:21px}small,.muted{color:#58707b;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px;margin-top:24px}article{background:white;padding:24px;border:1px solid #d8e2e5;border-radius:16px}.row{display:flex;justify-content:space-between;gap:12px;font-size:13px}.tag{border-radius:20px;padding:2px 12px;background:#e5eef0}.conflict,.blocked{background:#ffe1ce}.missing{background:#fff0b8}details{border-top:1px solid #dde5e9;padding:10px 0}summary{cursor:pointer}blockquote{margin:12px 0;padding-left:14px;border-left:3px solid #369f9b}td{padding:10px;border-bottom:1px solid #dde5e9;vertical-align:top;overflow-wrap:anywhere}table{width:100%;table-layout:fixed;border-collapse:collapse}pre{white-space:pre-wrap;overflow-wrap:anywhere}footer{padding:24px 0}code{background:#e1e8eb;padding:2px 6px}
</style><main>'''
    html += f'<header><small style="color:#a8ddd8">RESEARCH OPERATIONS / PORTFOLIO PROTOTYPE</small><h1>Evidence before approval.</h1><p>{esc(data["data_label"])} · {esc(data["mode"])} · No automatic approvals</p><p>{len(data["documents"])} documents &nbsp; / &nbsp; {len(data["findings"])} checks &nbsp; / &nbsp; {pending} awaiting review</p></header>'
    rows = ''.join('<tr><td>'+esc(k.replace('_',' ').title())+'</td><td>'+esc(json.dumps(v))+'</td></tr>' for k,v in metrics.items() if k not in {'caveat','denominators'})
    html += '<article><h2>Evaluation / synthetic descriptive proxies</h2><p>'+esc(metrics['caveat'])+'</p><table>'+rows+'</table><details><summary>Metric denominators</summary><pre>'+esc(json.dumps(metrics['denominators'],indent=2))+'</pre></details></article>'
    for f in data['findings']:
        if 'trace' in f:
            html += '<article><h2>'+esc(f['id'])+' · Evidence, governance & RCA</h2><details><summary>Claims, routing, confidence, final decision and trace</summary><pre>'+esc(json.dumps({k:f[k] for k in ('claims','recommendation','confidence','routing','final_decision','rca','trace','retrieved_sources','support_reviews')},indent=2))+'</pre></details></article>'
    html += '<div class="grid">'+''.join(cards)+'</div><footer><h2>Human review & audit trail</h2><p>This is a read-only export. Use the CLI to approve, reject or revise a recommendation, then reopen this file. Approval accepts the review recommendation; it does not authorize research deployment.</p><pre>'+esc(json.dumps(log[1:],indent=2,ensure_ascii=False))+'</pre><p>Evidence matching is lexical. Quote validation does not establish truth. Local hashes are not tamper-proof.</p></footer></main></html>'
    Path(out, 'dashboard.html').write_text(html,encoding='utf-8')
