# RAG Knowledge Assistant — MVP Prototype

IBM SkillsBuild AI Experiential Learning Lab — final submission prototype
(due Nov 22, 2026). A retrieval-augmented generation (RAG) knowledge
assistant for support/ops docs: ask a question, get an answer built only
from the approved documents, with citations. If the docs have no answer,
it says so instead of guessing.

## What it is — and is not

- **Working now, locally:** ingestion of a small pilot corpus, retrieval,
  extractive answers with citations, a "not found" fallback, an eval
  harness, and a simple web UI.
- **Not a deployed system.** No IBM Cloud, no watsonx.ai — the team Cloud
  account was never confirmed, so no hosted model is configured. Answers
  are composed extractively from retrieved passages (see `BUILD-NOTES.md`
  for the honest stack description and the exact step that closes the
  generation gap).

## Quick start

```bash
cd rag-knowledge-assistant-mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # numpy + sentence-transformers (optional)

python -m rag_mvp.cli ingest     # build the chunk index from corpus/
python -m rag_mvp.cli demo       # the two demo questions
python -m rag_mvp.cli ask "How do I reset my password if I forgot it?"
python -m rag_mvp.cli repl       # interactive question loop
python -m rag_mvp.eval           # eval harness (10 questions)
python -m rag_mvp.app            # web UI at http://127.0.0.1:8080
```

Only NumPy is strictly required: without `sentence-transformers` the
retriever falls back to TF-IDF (the baseline named in the Solution
Blueprint). With it installed, retrieval uses `all-MiniLM-L6-v2`
embeddings, cached under `index/`.

## Layout

```
corpus/                  8 sample support/ops docs (the pilot corpus)
rag_mvp/
  ingest.py              Markdown + front matter -> chunk index
  retrieval.py           TF-IDF retriever + embedding retriever
  answer.py              extractive answering + "not found" fallback
  cli.py                 ingest / ask / repl / eval / demo
  eval.py                eval harness
  app.py                 stdlib-only web UI (GET / , POST /ask)
eval/
  questions.jsonl        10 eval questions (7 answerable, 3 fallback)
  results.json           latest eval run
index/                   generated chunk index + embedding cache
```

## Eval results (latest run — see `eval/results.json`)

- Grounded-answer rate: 100% (blueprint target: 90%)
- Citation coverage: 100% (target: 100%)
- Correct-fallback rate: 100% (3/3 unanswerable questions fell back)
- False-fallback rate: 0%
- Median latency: <1 ms on the pilot corpus (TF-IDF backend)

These are measured on the 8-document pilot corpus, not on real team docs.
The numbers will change when the corpus is replaced with real documents.

## Demo script (what to show in the 3-minute video)

1. `python -m rag_mvp.cli ask "How do I reset my password if I forgot it?"`
   → answer assembled from the password-reset doc, with citations showing
   title, section, owner, and last-updated date.
2. `python -m rag_mvp.cli ask "What is the Wi-Fi password for the guest network?"`
   → the "not found" fallback, directing the user to the Help Desk.
3. `python -m rag_mvp.eval` → the metrics above.
4. `python -m rag_mvp.app` → the same flow in the browser.

## Still to do for the Nov 22 final submission

- 3-minute demo video (public link) — record the demo script above.
- Problem and Solution Statement (max 500 words).
- Technology Statement (max 500 words) — must explain IBM Bob usage and
  the actual stack (see BUILD-NOTES.md).
- Code repository link — this folder, once Swamy reviews it and decides
  where to publish it.
