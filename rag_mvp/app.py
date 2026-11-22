"""Tiny web UI for the RAG knowledge assistant MVP.

Standard-library only (http.server) — no Flask/FastAPI needed.
Run:  python -m rag_mvp.app [--port 8080]
Then open http://localhost:8080 in a browser.

Endpoints:
  GET  /        the chat page
  POST /ask    {"question": "..."} -> the answer dict as JSON

Security hardening (applied Nov 22 2026 via IBM Bob code review):
  - MAX_BODY_BYTES: hard cap on request body; oversized requests → 413
  - MAX_QUESTION_CHARS: server-side question length guard
  - Security response headers on every response (nosniff, no-frame)
  - Content-Length validation before reading body
  - Errors logged to stderr at WARNING level; request bodies never logged
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Hard cap on the request body read.  Oversized payloads are rejected with
# HTTP 413 before any bytes are consumed beyond this limit.
MAX_BODY_BYTES = 65_536

# Server-side question length guard (matches the UI maxlength="2000").
MAX_QUESTION_CHARS = 2_000

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_mvp.answer import answer  # noqa: E402
from rag_mvp.ingest import load_chunks  # noqa: E402
from rag_mvp.retrieval import get_retriever  # noqa: E402

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowledge Assistant | RAG MVP</title>
<style>
:root{color-scheme:light;--navy:#172943;--ink:#152238;--muted:#53647a;--line:#dce4ee;--blue:#1455c0;--bg:#f4f7fb}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{background:var(--navy);color:white;padding:18px 28px}
.top{max-width:1120px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px;font-weight:700;letter-spacing:-.02em}
.logo{display:grid;place-items:center;background:#3578e5;width:42px;height:42px;border-radius:11px;font-size:21px}
.tag{font-size:12px;color:#dce8fa;border:1px solid #536782;padding:5px 11px;border-radius:20px}
main{max-width:1120px;margin:34px auto;padding:0 20px 40px;display:grid;grid-template-columns: minmax(0,1fr) 260px;gap:24px}
h1{font-size:clamp(25px,4vw,36px);letter-spacing:-.04em;line-height:1.2;margin:8px 0 12px}
.eyebrow{font-weight:700;color:var(--blue);font-size:11px;text-transform:uppercase;letter-spacing:.13em}
h2{font-size:16px;margin:0 0 12px} h3{font-size:14px;margin:0}
.lead{color:var(--muted);margin:0 0 22px;max-width:620px}
.panel{background:white;border:1px solid var(--line);border-radius:16px;padding:24px;box-shadow:0 5px 24px #1c3d6610}
form{display:flex;gap:10px;margin-top:6px}
input{font:inherit;color:var(--ink);width:100%;min-width:0;border:1px solid #c1cddd;border-radius:9px;padding:13px 14px;background:#fff}
button{font:inherit;cursor:pointer;border-radius:9px;border:1px solid transparent}
button:focus-visible,input:focus-visible{outline:3px solid #8ab8ff;outline-offset:3px}
.primary{background:var(--blue);color:white;font-weight:700;padding:11px 19px;white-space:nowrap}
.primary:hover{background:#10479e}button:disabled{opacity:.55;cursor:wait}
.suggestions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:14px 0 0}
.suggestion{text-align:left;color:#29496f;border-color:var(--line);background:#f7f9fc;font-size:13px;padding:10px 12px}
.suggestion:hover{border-color:#7da9e8;background:#eef5ff}
.label{margin-top:22px;color:var(--muted);font-size:12px;font-weight:650}
#answer{margin-top:20px}
#answer:empty{display:none}
.result{border-top:1px solid var(--line);padding-top:20px}
.question{font-size:13px;color:var(--muted);margin:0 0 12px;overflow-wrap:anywhere}
.status{display:inline-block;border-radius:6px;padding:4px 9px;background:#e6f3ed;color:#176743;font-size:12px;font-weight:700;margin-bottom:10px}
.status.warn{background:#fff1da;color:#8b5208}
.answer-text{margin:0 0 18px;white-space:pre-wrap;overflow-wrap:anywhere}
.source{border:1px solid var(--line);border-left:3px solid #3978d5;border-radius:9px;padding:12px;margin:8px 0}
.source p,.meta{font-size:12px;color:var(--muted);margin:4px 0 0}
details{margin-top:16px;border-top:1px solid var(--line);padding-top:12px}
summary{cursor:pointer;font-weight:650;font-size:13px;color:#29496f}
.score{margin:10px 0;font-size:12px;overflow-wrap:anywhere}
.track{height:7px;background:#e6edf6;border-radius:4px;margin:5px 0}
.fill{height:100%;background:#4382d7;border-radius:4px}
.stats{display:flex;flex-wrap:wrap;gap:7px;margin-top:16px}
.pill{font-size:11px;padding:4px 8px;background:#edf2f8;border-radius:5px;color:#41536c}
aside{display:flex;flex-direction:column;gap:16px}
aside .panel{padding:19px}
.fact{padding:9px 0;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:10px;font-size:13px}
.fact:last-child{border:0}
.fact span{color:var(--muted)}
.note{font-size:13px;color:var(--muted);margin:0}
footer{max-width:1120px;margin:0 auto;padding:0 20px 24px;color:var(--muted);font-size:12px}
@media(max-width:780px){main{grid-template-columns:1fr;margin:22px auto}aside{display:grid;grid-template-columns:1fr 1fr}}
@media(max-width:480px){header{padding:14px 18px}.panel{padding:17px}aside,.suggestions{grid-template-columns:1fr}form{flex-direction:column}}
</style>
</head>
<body>
<header><div class="top"><div class="brand"><span class="logo" aria-hidden="true">K</span><span>Knowledge Assistant</span></div><span class="tag">Local MVP &middot; IBM SkillsBuild project</span></div></header>
<main>
<section>
<div class="eyebrow">Support &amp; operations / Knowledge retrieval</div>
<h1>Find the right information.</h1>
<p class="lead">Ask about IT support and operational policies. Explore answers extracted from sample documents, inspect the sources, and see how the retrieval system handles missing evidence.</p>
<div class="panel">
<h2>Ask the knowledge assistant</h2>
<form id="f"><input id="q" type="text" aria-label="Your question" placeholder="e.g. How do I reset my password?" autocomplete="off" required maxlength="2000"><button id="ask" class="primary" type="submit">Ask &rarr;</button></form>
<div class="label">Try a sample question</div>
<div class="suggestions">
<button class="suggestion" type="button">How do I reset my password if I forgot it?</button>
<button class="suggestion" type="button">What should I do when the VPN says connection failed?</button>
<button class="suggestion" type="button">How many days of annual leave do I get each year?</button>
<button class="suggestion" type="button">What is the Wi-Fi password for the guest network?</button>
</div>
<div id="answer" aria-live="polite" aria-busy="false"></div>
</div>
</section>
<aside>
<div class="panel"><h2>Pilot knowledge base</h2>
<div class="fact"><span>Sample documents</span><strong>8</strong></div>
<div class="fact"><span>Indexed sections</span><strong>32*</strong></div>
<div class="fact"><span>Evaluation cases</span><strong>20</strong></div>
<p class="note">*Original pilot corpus. All policies and contact details are fictional examples.</p></div>
<div class="panel"><h2>Responsible AI</h2><p class="note">This prototype extracts text from retrieved passages and attempts to decline unsupported questions. It can still miss relevant information or return out-of-scope answers. No generative model is configured.</p></div>
</aside>
</main>
<footer>IBM SkillsBuild AI Experiential Learning Lab &middot; Retrieval-augmented extractive QA prototype</footer>
<script>
const form=document.getElementById('f'), input=document.getElementById('q'), box=document.getElementById('answer'), ask=document.getElementById('ask');
let busy=false;
function add(parent,tag,cls,value){
  const node=document.createElement(tag);
  if(cls) node.className=cls;
  if(value!==undefined) node.textContent=String(value);
  parent.appendChild(node);
  return node;
}
function render(d,q){
  box.replaceChildren();
  const result=add(box,'section','result');
  add(result,'p','question',q);
  add(result,'span',d.fallback?'status warn':'status',d.fallback?'Insufficient evidence':'Extracted answer');
  add(result,'p','answer-text',d.answer);
  const citations=Array.isArray(d.citations)?d.citations:[];
  if(citations.length){
    add(result,'h2','','Source citations');
    citations.forEach(c=>{
      const card=add(result,'article','source');
      add(card,'h3','', '['+c.n+'] '+c.title);
      add(card,'p','',c.section);
      add(card,'p','',c.owner+' | Updated '+c.last_updated);
    });
  }
  const retrieved=Array.isArray(d.retrieved)?d.retrieved:[];
  if(retrieved.length){
    const details=add(result,'details','');
    add(details,'summary','','Retrieved passages and similarity scores');
    add(details,'p','meta','Similarity scores are not probabilities or guarantees of accuracy.');
    retrieved.forEach(r=>{
      const score=Number(r.score);
      const row=add(details,'div','score',r.title+' — '+r.section+' | '+(Number.isFinite(score)?score.toFixed(3):'N/A'));
      const bar=add(add(row,'div','track'),'div','fill');
      bar.style.width=(Number.isFinite(score)?Math.min(1,Math.max(0,score))*100:0)+'%';
    });
  }
  const stats=add(result,'div','stats');
  add(stats,'span','pill','Backend: '+d.backend);
  add(stats,'span','pill','Retrieval time: '+d.latency_ms+' ms');
  add(stats,'span','pill','Threshold: '+d.threshold);
  add(stats,'span','pill',d.mode);
}
async function submit(q){
  q=q.trim();
  if(!q||busy) return;
  input.value=q;
  busy=true;
  ask.disabled=true;
  document.querySelectorAll('.suggestion').forEach(b=>b.disabled=true);
  box.setAttribute('aria-busy','true');
  box.textContent='Searching the sample knowledge base…';
  try{
    const response=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
    if(!response.ok) throw new Error('Request failed ('+response.status+')');
    render(await response.json(),q);
  }catch(error){
    box.replaceChildren();
    add(box,'p','status warn','Unable to retrieve an answer');
    add(box,'p','note','Check that the local server is running and try again.');
  }finally{
    busy=false;
    ask.disabled=false;
    document.querySelectorAll('.suggestion').forEach(b=>b.disabled=false);
    box.setAttribute('aria-busy','false');
  }
}
form.addEventListener('submit',e=>{e.preventDefault();submit(input.value);});
document.querySelectorAll('.suggestion').forEach(b=>b.addEventListener('click',()=>submit(b.textContent)));
</script>
</body>
</html>
"""


def _log_warning(message: str) -> None:
    """Write a WARNING line to stderr.  Never include request body content."""
    print(f"WARNING [{__name__}]: {message}", file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    retriever = None
    backend = "unknown"

    def log_message(self, fmt: str, *args) -> None:  # noqa: ARG002
        # Suppress noisy per-request access lines from the base class.
        # Errors are logged explicitly via _log_warning().
        pass

    def _add_security_headers(self) -> None:
        """Attach security headers to the response currently being built."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._add_security_headers()
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        if self.path != "/ask":
            self.send_error(404, "Not found")
            return

        # --- Content-Length validation ---
        raw_cl = self.headers.get("Content-Length", "").strip()
        if not raw_cl.isdigit():
            _log_warning(f"POST /ask rejected: missing or non-numeric Content-Length ({raw_cl!r})")
            self._send_json({"error": "Content-Length header is required and must be a non-negative integer"}, status=400)
            return
        length = int(raw_cl)

        # --- Body size cap: reject before reading ---
        if length > MAX_BODY_BYTES:
            _log_warning(f"POST /ask rejected: Content-Length {length} exceeds {MAX_BODY_BYTES} byte limit")
            self._send_json(
                {"error": f"Request body too large (limit: {MAX_BODY_BYTES} bytes)"},
                status=413,
            )
            return

        # --- Read and parse JSON ---
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            _log_warning("POST /ask rejected: body is not valid JSON")
            self._send_json({"error": "invalid JSON"}, status=400)
            return

        # --- Payload type check ---
        if not isinstance(payload, dict):
            _log_warning(f"POST /ask rejected: payload root is {type(payload).__name__}, expected object")
            self._send_json({"error": "request body must be a JSON object"}, status=400)
            return

        # --- Question field validation ---
        question = str(payload.get("question", "")).strip()
        if not question:
            self._send_json({"error": "question is required"}, status=400)
            return
        if len(question) > MAX_QUESTION_CHARS:
            self._send_json(
                {"error": f"question exceeds maximum length of {MAX_QUESTION_CHARS} characters"},
                status=400,
            )
            return

        self._send_json(answer(question, self.retriever, self.backend))


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG MVP web UI")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    chunks = load_chunks()
    Handler.retriever, Handler.backend = get_retriever(chunks)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"RAG knowledge assistant running at http://127.0.0.1:{args.port}")
    print(f"Backend: {Handler.backend}. Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
