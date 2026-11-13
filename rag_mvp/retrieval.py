"""Retrieval layer: two interchangeable retrievers over the ingested chunks.

- EmbeddingRetriever: sentence-transformers (all-MiniLM-L6-v2), cosine
  similarity. Used when the library is installed.
- TfidfRetriever: pure NumPy TF-IDF cosine similarity. Zero extra
  dependencies; this is the retrieval baseline named in the Solution
  Blueprint ("keyword search over the same docs, with no model").

Both expose the same interface: search(query, top_k) -> list of
(chunk, score) with score in [0, 1], best first.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = PROJECT_ROOT / "index"

TOKEN_RE = re.compile(r"[a-z0-9]+")

# Small English stopword list (keeps TF-IDF focused on content words).
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "it", "its", "this", "that",
    "you", "your", "we", "our", "they", "their", "he", "she", "his", "her",
    "at", "by", "from", "as", "if", "when", "how", "do", "does", "did",
    "can", "could", "should", "will", "would", "what", "which", "who",
    "i", "me", "my", "am", "not", "no", "yes", "but", "so", "than", "then",
    "there", "here", "into", "out", "up", "down", "over", "under", "about",
    "after", "before", "between", "through", "during", "each", "all", "any",
    "some", "such", "only", "own", "same", "too", "very", "just", "also",
    "have", "has", "had", "get", "gets", "go", "goes", "use", "used",
}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class TfidfRetriever:
    """NumPy TF-IDF retriever. No model download, no API key, deterministic."""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray | None = None
        self.matrix: np.ndarray | None = None
        self._build()

    def _build(self) -> None:
        docs_tokens = [tokenize(c["title"] + " " + c["section"] + " " + c["text"])
                       for c in self.chunks]
        df: dict[str, int] = {}
        for tokens in docs_tokens:
            for tok in set(tokens):
                df[tok] = df.get(tok, 0) + 1
        self.vocab = {tok: i for i, tok in enumerate(sorted(df))}
        n_docs = len(self.chunks)
        self.idf = np.array(
            [math.log((n_docs + 1) / (df[tok] + 1)) + 1.0 for tok in sorted(df)],
            dtype=np.float32,
        )
        mat = np.zeros((n_docs, len(self.vocab)), dtype=np.float32)
        for row, tokens in enumerate(docs_tokens):
            counts: dict[str, int] = {}
            for tok in tokens:
                counts[tok] = counts.get(tok, 0) + 1
            for tok, count in counts.items():
                col = self.vocab[tok]
                mat[row, col] = (1.0 + math.log(count)) * self.idf[col]
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.matrix = mat / norms

    def _encode_query(self, query: str) -> np.ndarray:
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        counts: dict[str, int] = {}
        for tok in tokenize(query):
            if tok in self.vocab:
                counts[tok] = counts.get(tok, 0) + 1
        for tok, count in counts.items():
            col = self.vocab[tok]
            vec[col] = (1.0 + math.log(count)) * self.idf[col]
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def search(self, query: str, top_k: int = 3) -> list[tuple[dict, float]]:
        q = self._encode_query(query)
        scores = self.matrix @ q
        order = np.argsort(-scores)[:top_k]
        return [(self.chunks[i], float(scores[i])) for i in order]


class EmbeddingRetriever:
    """sentence-transformers retriever (all-MiniLM-L6-v2). Embeddings are
    cached under index/ so repeat runs do not re-encode the corpus."""

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self, chunks: list[dict]):
        from sentence_transformers import SentenceTransformer

        self.chunks = chunks
        self.model = SentenceTransformer(self.MODEL_NAME)
        cache_path = INDEX_DIR / "embeddings.npy"
        texts = [f"{c['title']} — {c['section']}\n{c['text']}" for c in chunks]
        if cache_path.exists():
            mat = np.load(cache_path)
            if mat.shape[0] == len(chunks):
                self.matrix = mat
                return
        emb = self.model.encode(texts, normalize_embeddings=True,
                                show_progress_bar=False)
        self.matrix = np.asarray(emb, dtype=np.float32)
        np.save(cache_path, self.matrix)

    def search(self, query: str, top_k: int = 3) -> list[tuple[dict, float]]:
        q = self.model.encode([query], normalize_embeddings=True,
                              show_progress_bar=False)[0]
        scores = self.matrix @ q
        order = np.argsort(-scores)[:top_k]
        return [(self.chunks[i], float(max(0.0, scores[i]))) for i in order]


def get_retriever(chunks: list[dict]):
    """Prefer embeddings when the library is importable; otherwise TF-IDF.
    Returns (retriever, backend_name)."""
    try:
        import sentence_transformers  # noqa: F401
        return EmbeddingRetriever(chunks), "embeddings"
    except Exception:
        return TfidfRetriever(chunks), "tfidf"
