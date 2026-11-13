"""Tiny web UI for the RAG knowledge assistant MVP.

Standard-library only (http.server) — no Flask/FastAPI needed.
Run:  python -m rag_mvp.app [--port 8080]
Then open http://localhost:8080 in a browser.

Endpoints:
  GET  /        the chat page
  POST /ask    {"question": "..."} -> the answer dict as JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_mvp.answer import answer  # noqa: E402
from rag_mvp.ingest import load_chunks  # noqa: E402
from rag_mvp.retrieval import get_retriever  # noqa: E402

PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>RAG Knowledge Assistant — MVP</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 720px; margin: 2em auto; padding: 0 1em; }
h1 { font-size: 1.4em; } #answer { white-space: pre-wrap; margin-top: 1em; }
.cite { color: #444; font-size: 0.9em; } .fallback { color: #8a5a00; }
input[type=text] { width: 75%; padding: 0.5em; } button { padding: 0.5em 1em; }
.meta { color: #666; font-size: 0.85em; margin-top: 0.5em; }
</style></head>
<body>
<h1>RAG Knowledge Assistant (MVP)</h1>
<p>Ask a question about the approved support documents. Answers come only
from those documents, with citations. If nothing matches, it says so instead
of guessing.</p>
<form id="f"><input type="text" id="q" placeholder="e.g. How do I reset my password?" autocomplete="off">
<button type="submit">Ask</button></form>
<div id="answer"></div>
<script>
document.getElementById('f').addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = document.getElementById('q').value;
  const box = document.getElementById('answer');
  box.textContent = 'Searching the approved docs...';
  const r = await fetch('/ask', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({question: q})});
  const d = await r.json();
  let html = '<p class="' + (d.fallback ? 'fallback' : '') + '">' +
    d.answer.replace(/</g, '&lt;') + '</p>';
  d.citations.forEach(c => {
    html += '<p class="cite">[' + c.n + '] ' + c.title + ' — ' + c.section +
      ' (Owner: ' + c.owner + ', updated ' + c.last_updated + ')</p>';
  });
  html += '<p class="meta">Backend: ' + d.backend + ' | ' + d.mode +
    ' | ' + d.latency_ms + ' ms</p>';
  box.innerHTML = html;
});
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    retriever = None
    backend = "unknown"

    def log_message(self, *args):  # keep the console quiet
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        if self.path != "/ask":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, status=400)
            return
        question = str(payload.get("question", "")).strip()
        if not question:
            self._send_json({"error": "question is required"}, status=400)
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
