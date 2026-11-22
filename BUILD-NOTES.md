# BUILD-NOTES — RAG Knowledge Assistant MVP

Built Sat Nov 7, 2026, after Swamy approved "start building the prototype".
Status: working prototype, running locally. Not deployed anywhere.

## What was built

A local RAG knowledge assistant for support/ops docs, exactly the minimal
MVP scope from the Solution Blueprint:

- **Ingestion** (`rag_mvp/ingest.py`): parses the 8-document pilot corpus
  (`corpus/*.md`, each with title/owner/last-updated front matter) into
  32 chunks (one per `##` section), written to `index/chunks.json`.
- **Retrieval** (`rag_mvp/retrieval.py`): two interchangeable retrievers
  behind one interface — sentence-transformers embeddings
  (`all-MiniLM-L6-v2`) when the library is installed, otherwise pure
  NumPy TF-IDF. Both return top-3 chunks with cosine scores in [0, 1].
- **Answering** (`rag_mvp/answer.py`): extractive answers — the sentences
  from retrieved passages that best match the question, quoted verbatim,
  each with a numbered citation (doc title, section, owner, last-updated
  date). If the best retrieval score is below the calibrated threshold,
  it returns the "not found" fallback (directing the user to the IT Help
  Desk) instead of guessing.
- **Eval harness** (`rag_mvp/eval.py`, `eval/questions.jsonl`): 20 fixed
  questions (12 answerable, 8 unanswerable) after the Nov 21 expansion. Reports grounded-answer rate,
  citation coverage, correct-fallback rate, false-fallback rate, and
  median latency. Results are saved to `eval/results.json`.
- **Web UI** (`rag_mvp/app.py`): standard-library-only HTTP server —
  one chat page (`GET /`) and a JSON endpoint (`POST /ask`).
- **CLI** (`rag_mvp/cli.py`): `ingest`, `ask`, `repl`, `eval`, `demo`.

## Stack actually used (honest version)

| Layer | What is actually used | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Retrieval | TF-IDF (NumPy) — 10/10 on the original eval, 16/20 on the expanded eval. Embeddings code is written and auto-detected when installed, but the install was blocked on this VM — see "Embeddings attempt" below | No IBM Cloud dependency |
| Vector store | In-memory NumPy arrays; embeddings cached in `index/embeddings.npy` | No FAISS/Chroma — unnecessary at this scale |
| Generation | **None configured.** Answers are extractive quotes from retrieved passages | This is the flagged gap (below) |
| UI | Python `http.server` (stdlib) | No Flask/FastAPI |
| Corpus | 8 hand-written sample support/ops docs in `corpus/` | Realistic but invented sample content, clearly marked as samples |

## Embeddings attempt (Nov 7 — blocked by this VM, not by the code)

`rag_mvp/retrieval.py` ships a real `EmbeddingRetriever`
(sentence-transformers, `all-MiniLM-L6-v2`) that activates automatically
when the library is importable. Installing it on this VM failed for
environment reasons, in this order:

1. First `pip install sentence-transformers` died with `Errno 28` — pip
   unpacks wheels in `/tmp`, a 512 MB tmpfs, and the torch wheel is
   539 MB.
2. Retried with `TMPDIR` on disk: the torch wheel downloaded, but pip
   pulled the CUDA build plus ~2 GB of NVIDIA packages (`nvidia-cudnn`
   etc.) on a CPU-only VM, so the install was stopped.
3. Installed the cached CUDA torch wheel with `--no-deps`; `import torch`
   then failed with `libcublasLt.so not found` — the CUDA build needs
   `nvidia-cublas-cu13`, which never finished downloading.
4. The CPU-only torch index (`download.pytorch.org`) timed out repeatedly.
5. A `sentence-transformers` install ran 10+ minutes without completing
   (network ~1 MB/s); backgrounded pip processes kept dying with their
   shell sessions.
6. The half-built venv (torch that cannot import) was removed to leave a
   clean repo. The TF-IDF backend is the shipped, verified one.

**To enable embeddings later** (on a machine with normal network):
`python3 -m venv .venv && source .venv/bin/activate && pip install -r
requirements.txt && pip install "sentence-transformers>=3.0"`, then re-run `python -m rag_mvp.eval` to calibrate the
embeddings threshold — embedding cosine scores live on a different scale,
so the TF-IDF threshold (0.30) does not transfer.

## The generation gap (flagged, not hidden)

No generative language model is available on this machine:

- No team IBM Cloud account — team registration (Oct 9) was never
  confirmed, so **watsonx.ai access does not exist**. No watsonx API key
  is present on this machine.
- No local LLM (no Ollama) and no LLM API key (OpenAI/Anthropic/Google)
  is set on this machine.
- Nothing was signed up for and no credentials were requested.

**Exact step that closes it:** once IBM Cloud access is restored, point
the model layer at a watsonx.ai hosted model for generation (and
embeddings), keeping the same retrieval/citation/fallback code — the
`answer()` function is the single place to swap extractive composition
for a grounded-generation call with a prompt that forbids outside
knowledge and requires citations. Until then, the demo must describe
answers as extractive, not model-generated.

## AI assistance used in this build (for the Technology Statement)

- The code, corpus, and docs in this repo were written by **Muse Spark**
  (Meta's AI coding agent) working from Swamy's approved Solution
  Blueprint and Technical Architecture drafts.
- **IBM Bob was not used in the original prototype build** due to access limitations. During final submission preparation, Bob was subsequently used for a structured code review and controlled implementation of HTTP validation, request-size limits, security headers on the application's HTML and JSON responses, validation-warning logging, dependency clarification, and automated tests. The original Bob report is labeled November 22, 2026; the local preparation and push occurred on November 21 Central Time.
- **ChatGPT** assisted with documentation, frontend presentation, submission drafts and demo preparation.
- See [IBM-BOB-CONTRIBUTIONS.md](IBM-BOB-CONTRIBUTIONS.md) and the [Bob review report](rag-knowledge-assistant-mvp-code-review-report.html) for the recorded development contributions. IBM Bob was a development assistant, not a runtime model.

## Final-stage automated testing

The user-reported Windows test execution ran 85 standard-library unittest cases (18 ingestion, 18 retrieval, 20 answering, 29 HTTP) in 0.736 seconds, all passing. The separate 20-question evaluation was rerun with unchanged 16/20 outcomes. The corpus, retrieval logic and original committed evaluation were preserved. The remaining four retrieval/scope failures and optional embedding cache issue are not resolved. The local HTTP server is not production-ready.

## Original 10-question eval results (TF-IDF backend, threshold 0.30)

Measured Sat Nov 7, 2026 on the 8-document pilot corpus:

- Grounded-answer rate: **100%** (7/7; blueprint target 90%)
- Citation coverage: **100%** (7/7 non-fallback answers carry citations)
- Correct-fallback rate: **100%** (3/3 unanswerable questions fell back)
- False-fallback rate: **0%**
- Median latency: <1 ms

Threshold calibration: answerable top scores 0.35–0.49, unanswerable
0.16–0.24, so 0.30 separates them on this set. The margin is thin —
on a real corpus the threshold must be re-calibrated on that corpus's
own eval set. (Embeddings backend, if installed, needs its own
calibration run; its scores live on a different scale.)

## Expanded eval (Nov 21, after coach review)

Coach Damien De La Cerda asked for harder testing before the final
submission, so the eval set grew from 10 to 20 questions
(`eval/questions.jsonl`): 5 harder answerable questions (paraphrased
wording, multi-fact, short queries) and 5 near-miss unanswerable ones
(topics adjacent to the docs, or scoped to someone/something the docs
do not cover). Result: **16/20 pass** (grounded-answer rate 83%,
correct-fallback rate 75%, false-fallback rate 17%).

The 4 failures are real findings, not bad questions:

- **False fallbacks (2):** "I changed my password yesterday and now
  the VPN will not connect" scored 0.27 and "How many sick days do I
  get?" scored 0.28, both under the 0.30 threshold, although the
  answers are in the docs. Cause: TF-IDF with no stemming
  ("connect" does not match "Connection"/"connects") and short
  queries scoring low. The near-miss "change the toner cartridge"
  scored 0.29, so the bands now overlap and **no threshold separates
  them** — threshold tuning cannot fix this.
- **False answers (2):** "parental leave policy for contractors" and
  "reset my manager's password" were answered with the employee
  policy and the self-service reset, which do not apply to those
  cases. Cause: TF-IDF has no scope or entity reasoning; it cannot
  tell that a rule for employees does not cover contractors, or that
  self-service reset is only for your own account.

Fixes for later (not attempted before the deadline, per the coach's
advice to test what exists rather than add features): stemming or
embeddings for paraphrase robustness, and a generative-model layer
that checks scope before answering. The failures are documented here
rather than hidden, because the eval's job is to show the gaps.

## What is still missing for the Nov 22 final submission

1. **3-minute demo video** (public link) — record the demo script in
   README.md: one cited answer, one fallback, the eval run, the web UI.
2. **Problem and Solution Statement** (max 500 words).
3. **Technology Statement** (max 500 words) — describe IBM Bob's actual final-stage review, hardening and testing; watsonx.ai is not configured.
4. **Code repository link** — published at https://github.com/Swamy2255/rag-knowledge-assistant-mvp; include the link in the submission.

## Blockers

- **IBM Cloud / watsonx.ai access** — the generation gap above. The
  prototype is fully demoable without it, but the final Technology
  Statement must address the plan honestly.
- **Checkpoint blockers unchanged** — team name remains unconfirmed; coach Damien De La Cerda provided evaluation feedback (separate from this build); the Nov 6 Career Fair deadline
  has passed. The Nov 22 final submission is unaffected.
- **Real corpus** — the pilot corpus is invented sample content. A real
  pilot needs one team's actual approved docs plus an eval set written
  by the doc owners.
