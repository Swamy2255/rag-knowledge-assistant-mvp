"""Answer layer: extractive answering over retrieved passages, with a
"not found" fallback.

IMPORTANT HONESTY NOTE (see BUILD-NOTES.md): no generative language model
is configured on this machine — no watsonx.ai access (team Cloud account
never confirmed), no local LLM, and no LLM API key. The answer is therefore
composed extractively: the sentences from the retrieved passages that best
match the question are quoted verbatim, each tied to a citation. The
retrieval, citation, and fallback layers are fully working; the generation
layer is the flagged gap, closed by pointing the model layer at a real
hosted model (planned: watsonx.ai) once Cloud access exists.
"""

from __future__ import annotations

import re
import time

from .retrieval import tokenize

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Fallback thresholds on the retriever's [0, 1] cosine score. Calibrated
# against eval/questions.jsonl (TF-IDF: answerable top scores 0.35-0.49,
# unanswerable 0.16-0.24, so 0.30 separates them; embeddings need their
# own calibration run — see eval results in eval/results.json).
DEFAULT_THRESHOLDS = {"embeddings": 0.30, "tfidf": 0.30}

FALLBACK_TEXT = (
    "I could not find an answer to that in the approved support documents, "
    "so I will not guess. Please ask the IT Help Desk (extension 4357 or "
    "helpdesk@company.example) or check with the document owner for the "
    "area your question is about."
)


def split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in SENTENCE_RE.split(text.replace("\n", " "))]
    return [s for s in parts if len(s) > 20]


def _sentence_score(sentence: str, query_tokens: set[str]) -> float:
    tokens = set(tokenize(sentence))
    if not tokens:
        return 0.0
    overlap = len(tokens & query_tokens)
    return overlap / max(1, len(query_tokens)) + 0.1 * overlap / len(tokens)


def answer(question: str, retriever, backend: str, top_k: int = 3,
           threshold: float | None = None) -> dict:
    """Answer one question. Returns a dict with answer text, citations,
    retrieval metadata, and a fallback flag."""
    started = time.perf_counter()
    if threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(backend, 0.10)

    retrieved = retriever.search(question, top_k=top_k)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    if not retrieved or retrieved[0][1] < threshold:
        return {
            "question": question,
            "answer": FALLBACK_TEXT,
            "citations": [],
            "retrieved": [
                {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
                 "title": c["title"], "section": c["section"],
                 "score": round(s, 3)}
                for c, s in retrieved
            ],
            "fallback": True,
            "backend": backend,
            "threshold": threshold,
            "latency_ms": latency_ms,
            "mode": "extractive (no generative model configured)",
        }

    query_tokens = set(tokenize(question))
    # Rank sentences from the retrieved chunks by query overlap.
    candidates: list[tuple[float, int, int, str, dict]] = []
    for rank, (chunk, _) in enumerate(retrieved):
        for pos, sentence in enumerate(split_sentences(chunk["text"])):
            score = _sentence_score(sentence, query_tokens)
            candidates.append((score, rank, pos, sentence, chunk))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

    # Take up to 3 sentences, at most 2 per chunk, preferring distinct chunks.
    chosen: list[tuple[str, dict]] = []
    per_chunk: dict[str, int] = {}
    for score, _, _, sentence, chunk in candidates:
        if score <= 0:
            continue
        if per_chunk.get(chunk["chunk_id"], 0) >= 2:
            continue
        chosen.append((sentence, chunk))
        per_chunk[chunk["chunk_id"]] = per_chunk.get(chunk["chunk_id"], 0) + 1
        if len(chosen) == 3:
            break

    if not chosen:
        # Retrieved passages scored well but no sentence overlapped the
        # question terms: fall back rather than fabricate.
        return {
            "question": question,
            "answer": FALLBACK_TEXT,
            "citations": [],
            "retrieved": [
                {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
                 "title": c["title"], "section": c["section"],
                 "score": round(s, 3)}
                for c, s in retrieved
            ],
            "fallback": True,
            "backend": backend,
            "threshold": threshold,
            "latency_ms": latency_ms,
            "mode": "extractive (no generative model configured)",
        }

    # Citations: one per distinct chunk used, in order of first use.
    citation_chunks: list[dict] = []
    for _, chunk in chosen:
        if chunk not in citation_chunks:
            citation_chunks.append(chunk)
    index_of = {c["chunk_id"]: i + 1 for i, c in enumerate(citation_chunks)}

    answer_parts = []
    for sentence, chunk in chosen:
        answer_parts.append(f"{sentence} [{index_of[chunk['chunk_id']]}]")
    answer_text = (
        "Based on the approved support documents: " + " ".join(answer_parts)
    )

    citations = [
        {
            "n": i + 1,
            "title": c["title"],
            "section": c["section"],
            "owner": c["owner"],
            "last_updated": c["last_updated"],
            "doc_id": c["doc_id"],
        }
        for i, c in enumerate(citation_chunks)
    ]

    return {
        "question": question,
        "answer": answer_text,
        "citations": citations,
        "retrieved": [
            {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
             "title": c["title"], "section": c["section"],
             "score": round(s, 3)}
            for c, s in retrieved
        ],
        "fallback": False,
        "backend": backend,
        "threshold": threshold,
        "latency_ms": latency_ms,
        "mode": "extractive (no generative model configured)",
    }
