# IBM-BOB-CONTRIBUTIONS.md

## IBM Bob Usage — RAG Knowledge Assistant MVP

**Project:** RAG Knowledge Assistant MVP  
**IBM SkillsBuild Cohort:** Fall 2026  
**Bob session dates:** November 22, 2026  
**Repository:** https://github.com/Swamy2255/rag-knowledge-assistant-mvp

---

## 1. What IBM Bob Was Asked to Do

This document records two distinct Bob sessions on November 22, 2026 — the final submission day.

### Session A — Code Review

Bob was asked to act as a senior Python and AI engineer and perform a full code review of the existing prototype for the final IBM SkillsBuild submission. The review covered:

- Document ingestion, TF-IDF retrieval, extractive answering, citations, fallback mechanism, and web interface.
- Root-cause analysis of the four evaluation failures in the 20-question harness.
- Security issues, reliability concerns, and code quality findings.
- Practical improvement recommendations.
- Automated unit and integration test recommendations.
- Verification of documentation accuracy.

Bob read every source file in the project (all five `rag_mvp/` modules, both corpus documents relevant to the failed cases, the full `eval/results.json`, `eval/questions.jsonl`, `README.md`, `BUILD-NOTES.md`, and `requirements.txt`) before producing findings.

### Session B — Controlled Implementation

Bob was asked to implement the highest-priority improvements identified in Session A, specifically:

- Phase 1 (security and reliability): five targeted changes to `app.py` and `requirements.txt`.
- Phase 2 (automated testing): a full `unittest` test suite with no additional dependencies.

Bob was explicitly instructed **not to** change the retrieval algorithm, evaluation questions, corpus, fallback threshold, or frontend design, and **not to** push to GitHub or run installs.

---

## 2. Code Review Findings (Session A)

Bob inspected the entire codebase and produced a structured report. Key findings by severity:

### HIGH severity

| ID | File | Finding |
|----|------|---------|
| SEC-1 | `app.py` | No request body size cap — `rfile.read(length)` accepted arbitrarily large payloads |
| SEC-2 | `app.py` | No `X-Content-Type-Options` or `X-Frame-Options` security headers |
| SCOPE-1 | `answer.py` | "parental leave for contractors" returned an employee-policy answer (scope bypass) |
| SCOPE-2 | `answer.py` | "reset my manager's password" returned self-service reset instructions (entity bypass) |

### MEDIUM severity

| ID | File | Finding |
|----|------|---------|
| REL-1 | `app.py` | `log_message` override silenced all errors, making failures silent |
| REL-2 | `retrieval.py` | EmbeddingRetriever cache not invalidated on corpus change (count-equality check only) |
| REL-3 | `retrieval.py` | `except Exception` swallowed real import errors, masking wrong-backend usage |
| QA-4 | `answer.py` | Latency timer stopped before sentence scoring, reporting 0.0 ms for most cases |
| QA-5 | `cli.py` | `cmd_eval` mutated `sys.argv` as a side effect |

### LOW severity / Documentation

| ID | Finding |
|----|---------|
| QA-1 | YAML front-matter parser is correct but deserves a comment about key restrictions |
| QA-3 | Sentence splitter is coarse (no abbreviation handling), latent bug for real docs |
| DOC-1 | `requirements.txt` listed `sentence-transformers` as a required dependency when it is explicitly optional |
| DOC-2 | Latency metric description was accurate but the 0.0 ms median in `results.json` could mislead |

### Evaluation failure root causes

| Failure | Root cause identified by Bob |
|---------|------------------------------|
| "Changed my password / VPN won't connect" (false fallback, score 0.267) | No stemming: `connect` ≠ `connection`, `yesterday` ≠ `recently` — score just below 0.30 threshold |
| "How many sick days" (false fallback, score 0.277) | Ultra-short query (2 tokens post-stopword); `days` is high-frequency so IDF is diluted |
| "Parental leave for contractors" (false answer) | TF-IDF has no scope/entity reasoning; retrieves the parental-leave section and answers as if it applies to contractors |
| "Reset my manager's password" (false answer) | `reset` + `password` match the self-service reset doc; possessive third-party context is invisible to bag-of-words |

---

## 3. Implemented Changes (Session B)

All changes were implemented by Bob and executed in the existing `.venv` virtual environment. No new dependencies were added. The evaluation baseline, retrieval algorithm, corpus, and frontend were not changed.

### Phase 1 — Security and reliability (`rag_mvp/app.py`)

**Change 1 — HTTP 413 body size cap**  
Added module-level constant `MAX_BODY_BYTES = 65_536`. In `do_POST()`, the server now reads the `Content-Length` header value and rejects requests whose declared size exceeds this limit with HTTP 413 **before** reading any body bytes. The original code had no size guard and could allocate arbitrary memory.

**Change 2 — Full server-side input validation**  
Added a layered validation sequence to `do_POST()`:
1. `Content-Length` header must be present and must be a non-negative integer (→ 400 otherwise).
2. Body size cap check against `MAX_BODY_BYTES` (→ 413 if exceeded).
3. Body must be valid JSON (→ 400).
4. JSON root must be an object/dict, not an array or scalar (→ 400).
5. `question` field must be present and non-empty after stripping (→ 400).
6. `question` must not exceed `MAX_QUESTION_CHARS = 2_000` characters (→ 400).

**Change 3 — Security response headers**  
Added `_add_security_headers()` method to `Handler`. Both `do_GET()` and `_send_json()` now call this method, which attaches `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` to every response — including error responses.

**Change 4 — Targeted error logging**  
Replaced the silent `log_message(self, *args): pass` override with a named private function `_log_warning(message: str)` that writes to `stderr`. It is called explicitly for the validation rejection cases. The design rule is strict: only the rejection reason is logged — request body content is never logged. The base-class per-request access lines remain suppressed.

### Phase 1 — `requirements.txt`

**Change 5 — `sentence-transformers` marked optional**  
Commented out the `sentence-transformers>=3.0` line and replaced it with a detailed explanation distinguishing required (NumPy only) from optional (sentence-transformers, needs PyTorch, ~2 GB), with installation instructions and a note that the TF-IDF threshold does not transfer.

### Phase 2 — Automated test suite (`tests/`)

Created `tests/__init__.py` and three test modules using Python's built-in `unittest` framework:

| File | Test class(es) | Tests |
|------|----------------|-------|
| `tests/test_ingest.py` | `TestParseDoc`, `TestSplitSections`, `TestChunkDoc`, `TestIngest` | 18 |
| `tests/test_retrieval.py` | `TestTokenize`, `TestTfidfRetriever`, `TestGetRetriever` | 18 |
| `tests/test_answer.py` | `TestSplitSentences`, `TestFallbackLowScore`, `TestFallbackNoOverlap`, `TestSuccessfulAnswer`, `TestDefaultThreshold` | 20 |
| `tests/test_app.py` | `TestAppHTTP` | 29 |
| **Total** | | **85** |

The `TestAppHTTP` class starts a live `ThreadingHTTPServer` on a free port using `setUpClass`, exercises real HTTP requests with `http.client`, and tears down the server with `tearDownClass`.

---

## 4. Test Execution Results

Command executed:

```
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

**Result: 85 tests run, 85 passed, 0 failures, 0 errors.**

```
Ran 85 tests in 0.736s

OK
```

The WARNING lines in stderr during the run are expected — they are the structured log messages from `_log_warning()` triggered by the invalid-input test cases (oversized body, missing Content-Length, invalid JSON, non-dict payload). These are correct behaviour, not failures.

Selected test results confirming the Phase 1 security fixes:

| Test | Result |
|------|--------|
| `test_post_ask_oversized_body_returns_413` | **PASS** — 65,537-byte body → HTTP 413 with `{"error": "Request body too large (limit: 65536 bytes)"}` |
| `test_post_ask_exactly_max_body_allowed` | **PASS** — 65,536-byte body → not 413 (correctly passes size check, then 400 for invalid JSON) |
| `test_post_ask_missing_content_length_returns_400` | **PASS** — absent Content-Length → HTTP 400 |
| `test_post_ask_invalid_json_returns_400` | **PASS** — non-JSON body → HTTP 400 |
| `test_post_ask_json_array_payload_returns_400` | **PASS** — JSON array root → HTTP 400 |
| `test_post_ask_question_too_long_returns_400` | **PASS** — 2,001-char question → HTTP 400 |
| `test_get_root_has_x_content_type_options` | **PASS** — `X-Content-Type-Options: nosniff` present on `GET /` |
| `test_get_root_has_x_frame_options` | **PASS** — `X-Frame-Options: DENY` present on `GET /` |
| `test_post_ask_response_has_x_content_type_options` | **PASS** — security header present on `POST /ask` 200 response |
| `test_post_ask_response_has_x_frame_options` | **PASS** — security header present on `POST /ask` 200 response |
| `test_error_response_has_security_headers` | **PASS** — security header present on error (400) response |

---

## 5. Evaluation Baseline — Preserved

Command executed:

```
.\.venv\Scripts\python.exe -m rag_mvp.eval
```

**Result: 16/20 — identical to the pre-Bob baseline.**

```
Backend: tfidf  threshold: None
Questions: 20  (0.0s total)
Grounded-answer rate:  83%  (blueprint target: 90%)
Citation coverage:      100%  (target: 100%)
Correct-fallback rate:  75%
False-fallback rate:    17%
Median latency:         0.0 ms
```

The four known failures are identical and unchanged:

| Question | Failure type | Score |
|----------|-------------|-------|
| "I changed my password yesterday and now the VPN will not connect…" | False fallback | 0.267 |
| "How many sick days do I get?" | False fallback | 0.277 |
| "What is the company's parental leave policy for contractors?" | False answer | 0.400 |
| "How do I reset my manager's password?" | False answer | 0.355 |

---

## 6. Files Modified by Bob

| File | Change type | Summary |
|------|-------------|---------|
| `rag_mvp/app.py` | Modified | Phase 1 security hardening: body size cap, full input validation, security response headers, targeted error logging |
| `requirements.txt` | Modified | `sentence-transformers` commented out as optional with detailed installation notes |
| `tests/__init__.py` | Created | Empty package marker |
| `tests/test_ingest.py` | Created | 18 unit tests for ingestion and chunking |
| `tests/test_retrieval.py` | Created | 18 unit tests for TF-IDF retrieval |
| `tests/test_answer.py` | Created | 20 unit tests for extractive answering, citations, and fallback |
| `tests/test_app.py` | Created | 29 integration tests for HTTP endpoints, security headers, and body validation |
| `IBM-BOB-CONTRIBUTIONS.md` | Created | This file |

### Files NOT modified (preserved exactly)

- `rag_mvp/ingest.py`
- `rag_mvp/retrieval.py`
- `rag_mvp/answer.py`
- `rag_mvp/cli.py`
- `rag_mvp/eval.py`
- `rag_mvp/__init__.py`
- `eval/questions.jsonl`
- `eval/results.json`
- `corpus/` (all 8 documents)
- `README.md`
- `BUILD-NOTES.md`
- `DEMO-SCRIPT.md`
- `scripts/demo.sh`

---

## 7. Remaining Limitations (Not Addressed in This Session)

The following limitations were identified in the code review but were **not implemented** in this session. They are documented here for honesty and for future work:

1. **No stemming / morphological normalization in TF-IDF** — the two false-fallback failures (`VPN/password-change` and `sick days`) are caused by lexical mismatch that stemming would partially address. Not implemented because the instructions explicitly said not to change the retrieval algorithm.

2. **No scope/entity reasoning** — the two false-answer failures (`contractor parental leave` and `manager's password reset`) require either a generative model layer or targeted heuristics. The code review proposed these; they were not implemented to preserve the evaluation baseline exactly.

3. **EmbeddingRetriever cache invalidation** — the embeddings cache uses chunk-count equality, not content hashing. Only relevant when the embeddings backend is installed (it is not in this venv). No change made.

4. **Latency timer scope** — `answer()` stops the timer before sentence scoring, so `latency_ms` measures retrieval only. The review recommended moving the timer; not changed because it would alter the results.json format without a matching eval re-run.

5. **`cmd_eval` sys.argv mutation** — `cli.py` mutates `sys.argv` when delegating to the eval harness. Low risk, not addressed.

6. **No generative model layer** — watsonx.ai access was unavailable during the build period. This is the acknowledged primary gap in the prototype.

---

## 8. Technology Statement Note

This project was **originally built** (November 7, 2026) by Muse Spark (Meta's AI coding agent) working from Swamy's approved Solution Blueprint and Technical Architecture drafts. IBM Bob was **not** used in the original build due to access limitations.

**IBM Bob was first used on November 22, 2026** (the final submission day) for:
- A full code review of the completed prototype (Session A).
- A controlled implementation session applying security hardening and automated tests (Session B).

The Technology Statement submitted through the program's required channel must reflect this timeline accurately: Bob was used for final-stage review and hardening, not for the original prototype construction.
