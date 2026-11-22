"""Tests for rag_mvp.app — HTTP GET/POST endpoints, security headers,
body size cap, input validation.

Covers:
- GET / returns 200 with text/html content-type
- GET unknown path returns 404
- POST /ask with valid question returns 200 JSON answer
- POST /ask with missing question field returns 400
- POST /ask with empty question string returns 400
- POST /ask with invalid JSON returns 400
- POST /ask with oversized body returns 413 (Phase 1 security fix)
- POST /ask with question exceeding MAX_QUESTION_CHARS returns 400
- POST /ask with missing Content-Length header returns 400
- POST /ask with non-dict JSON payload returns 400
- Security headers present on HTML response (X-Content-Type-Options, X-Frame-Options)
- Security headers present on JSON response
- POST to unknown path returns 404
"""

import json
import socket
import sys
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_mvp.app import Handler, MAX_BODY_BYTES, MAX_QUESTION_CHARS
from rag_mvp.ingest import load_chunks
from rag_mvp.retrieval import get_retriever
from http.server import ThreadingHTTPServer


# ---------------------------------------------------------------------------
# Server fixture — spins up a live ThreadingHTTPServer on a free port
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server() -> tuple:
    """Start the HTTP server with real chunks/retriever. Returns (server, port)."""
    chunks = load_chunks()
    retriever, backend = get_retriever(chunks)
    Handler.retriever = retriever
    Handler.backend = backend
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Give the thread a moment to bind.
    time.sleep(0.05)
    return server, port


def _post_raw(port: int, path: str, body: bytes, headers: dict | None = None) -> tuple:
    """Send a raw POST. Returns (status_code, response_headers, body_bytes)."""
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Content-Length": str(len(body)), "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    conn.request("POST", path, body=body, headers=h)
    resp = conn.getresponse()
    return resp.status, dict(resp.getheaders()), resp.read()


def _get(port: int, path: str) -> tuple:
    """Send a GET. Returns (status_code, response_headers, body_bytes)."""
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    resp = conn.getresponse()
    return resp.status, dict(resp.getheaders()), resp.read()


# ---------------------------------------------------------------------------
# Test class — one server shared across all tests for speed
# ---------------------------------------------------------------------------

class TestAppHTTP(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server, cls.port = _start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    # --- GET ---

    def test_get_root_returns_200(self):
        status, _, _ = _get(self.port, "/")
        self.assertEqual(status, 200)

    def test_get_root_content_type_html(self):
        _, headers, _ = _get(self.port, "/")
        ct = headers.get("Content-Type", "")
        self.assertIn("text/html", ct)

    def test_get_root_body_not_empty(self):
        _, _, body = _get(self.port, "/")
        self.assertGreater(len(body), 0)

    def test_get_root_body_contains_html_doctype(self):
        _, _, body = _get(self.port, "/")
        self.assertIn(b"<!doctype html", body.lower())

    def test_get_unknown_path_returns_404(self):
        status, _, _ = _get(self.port, "/robots.txt")
        self.assertEqual(status, 404)

    def test_get_index_html_alias_returns_200(self):
        status, _, _ = _get(self.port, "/index.html")
        self.assertEqual(status, 200)

    # --- Security headers on GET ---

    def test_get_root_has_x_content_type_options(self):
        _, headers, _ = _get(self.port, "/")
        # Header names from http.client are lowercased.
        lower_headers = {k.lower(): v for k, v in headers.items()}
        self.assertEqual(lower_headers.get("x-content-type-options", "").lower(), "nosniff")

    def test_get_root_has_x_frame_options(self):
        _, headers, _ = _get(self.port, "/")
        lower_headers = {k.lower(): v for k, v in headers.items()}
        self.assertEqual(lower_headers.get("x-frame-options", "").lower(), "deny")

    # --- POST /ask — valid ---

    def test_post_ask_valid_question_returns_200(self):
        body = json.dumps({"question": "How do I reset my password?"}).encode()
        status, _, _ = _post_raw(self.port, "/ask", body)
        self.assertEqual(status, 200)

    def test_post_ask_valid_question_returns_json(self):
        body = json.dumps({"question": "How do I reset my password?"}).encode()
        status, headers, resp_body = _post_raw(self.port, "/ask", body)
        self.assertEqual(status, 200)
        lower_headers = {k.lower(): v for k, v in headers.items()}
        self.assertIn("application/json", lower_headers.get("content-type", ""))

    def test_post_ask_response_has_required_keys(self):
        body = json.dumps({"question": "How do I reset my password?"}).encode()
        _, _, resp_body = _post_raw(self.port, "/ask", body)
        data = json.loads(resp_body)
        for key in ("answer", "citations", "fallback", "retrieved", "backend"):
            self.assertIn(key, data, f"Response missing key: {key}")

    def test_post_ask_fallback_question_returns_fallback(self):
        body = json.dumps({"question": "What is the company stock ticker?"}).encode()
        _, _, resp_body = _post_raw(self.port, "/ask", body)
        data = json.loads(resp_body)
        self.assertTrue(data["fallback"])
        self.assertEqual(data["citations"], [])

    # --- POST /ask — invalid inputs ---

    def test_post_ask_missing_question_returns_400(self):
        body = json.dumps({"other": "value"}).encode()
        status, _, resp_body = _post_raw(self.port, "/ask", body)
        self.assertEqual(status, 400)
        data = json.loads(resp_body)
        self.assertIn("error", data)

    def test_post_ask_empty_question_returns_400(self):
        body = json.dumps({"question": "   "}).encode()
        status, _, _ = _post_raw(self.port, "/ask", body)
        self.assertEqual(status, 400)

    def test_post_ask_invalid_json_returns_400(self):
        body = b"this is not json at all"
        status, _, resp_body = _post_raw(self.port, "/ask", body)
        self.assertEqual(status, 400)
        data = json.loads(resp_body)
        self.assertIn("error", data)

    def test_post_ask_json_array_payload_returns_400(self):
        # Root JSON array is not an object — should be rejected.
        body = json.dumps(["question", "value"]).encode()
        status, _, resp_body = _post_raw(self.port, "/ask", body)
        self.assertEqual(status, 400)
        data = json.loads(resp_body)
        self.assertIn("error", data)

    def test_post_ask_question_too_long_returns_400(self):
        long_q = "a" * (MAX_QUESTION_CHARS + 1)
        body = json.dumps({"question": long_q}).encode()
        status, _, resp_body = _post_raw(self.port, "/ask", body)
        self.assertEqual(status, 400)
        data = json.loads(resp_body)
        self.assertIn("error", data)

    def test_post_unknown_path_returns_404(self):
        body = json.dumps({"question": "test"}).encode()
        status, _, _ = _post_raw(self.port, "/upload", body)
        self.assertEqual(status, 404)

    # --- Oversized body → HTTP 413 (Phase 1 security fix) ---

    def test_post_ask_oversized_body_returns_413(self):
        # Send a body whose Content-Length exceeds MAX_BODY_BYTES.
        # We advertise the size but don't actually send all bytes, so the
        # server must reject based on Content-Length alone.
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        oversized = MAX_BODY_BYTES + 1
        conn.request(
            "POST", "/ask",
            body=b"x" * oversized,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(oversized),
            },
        )
        resp = conn.getresponse()
        self.assertEqual(resp.status, 413)
        data = json.loads(resp.read())
        self.assertIn("error", data)

    def test_post_ask_exactly_max_body_allowed(self):
        # A body of exactly MAX_BODY_BYTES is not oversized — but it won't
        # be valid JSON, so we expect 400 (invalid JSON), not 413.
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        body = b"x" * MAX_BODY_BYTES
        conn.request(
            "POST", "/ask",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        # Must NOT be 413 — could be 400 (invalid JSON) or 200.
        self.assertNotEqual(resp.status, 413)

    # --- Missing Content-Length ---

    def test_post_ask_missing_content_length_returns_400(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        # Manually set only Content-Type, omit Content-Length.
        conn.putrequest("POST", "/ask")
        conn.putheader("Content-Type", "application/json")
        # No Content-Length header.
        conn.endheaders(b"")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 400)
        data = json.loads(resp.read())
        self.assertIn("error", data)

    # --- Security headers on JSON responses ---

    def test_post_ask_response_has_x_content_type_options(self):
        body = json.dumps({"question": "How do I reset my password?"}).encode()
        _, headers, _ = _post_raw(self.port, "/ask", body)
        lower = {k.lower(): v for k, v in headers.items()}
        self.assertEqual(lower.get("x-content-type-options", "").lower(), "nosniff")

    def test_post_ask_response_has_x_frame_options(self):
        body = json.dumps({"question": "How do I reset my password?"}).encode()
        _, headers, _ = _post_raw(self.port, "/ask", body)
        lower = {k.lower(): v for k, v in headers.items()}
        self.assertEqual(lower.get("x-frame-options", "").lower(), "deny")

    def test_error_response_has_security_headers(self):
        body = b"not json"
        _, headers, _ = _post_raw(self.port, "/ask", body)
        lower = {k.lower(): v for k, v in headers.items()}
        self.assertEqual(lower.get("x-content-type-options", "").lower(), "nosniff")


if __name__ == "__main__":
    unittest.main()
