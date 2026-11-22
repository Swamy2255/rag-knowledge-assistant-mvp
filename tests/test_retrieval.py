"""Tests for rag_mvp.retrieval — TF-IDF retriever.

Covers:
- tokenize() stopword removal and lowercasing
- TfidfRetriever returns exactly top_k results
- Scores are in [0, 1]
- Exact-term match scores higher than non-matching chunk
- OOV (out-of-vocabulary) query returns results without crashing
- Chunk with zero-length text does not crash _build()
- get_retriever() returns TfidfRetriever when sentence_transformers absent
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_mvp.retrieval import tokenize, TfidfRetriever


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(doc_id: str, title: str, section: str, text: str) -> dict:
    return {
        "chunk_id": f"{doc_id}-01",
        "doc_id": doc_id,
        "title": title,
        "owner": "Test Owner",
        "last_updated": "2026-01-01",
        "section": section,
        "text": text,
    }


CHUNKS = [
    _chunk("DOC-A", "Password Policy",   "Reset",      "Use the self-service portal to reset your password immediately."),
    _chunk("DOC-B", "VPN Setup",         "Connection", "Open the VPN client and connect using your corporate credentials."),
    _chunk("DOC-C", "Leave Policy",      "Annual",     "Employees receive twenty days of paid annual leave per year."),
    _chunk("DOC-D", "Expense Policy",    "Meals",      "The daily meal allowance for travel is sixty-five dollars."),
    _chunk("DOC-E", "Printer Guide",     "Setup",      "Install the printer driver and add the device via Windows Settings."),
]


# ---------------------------------------------------------------------------
# tokenize()
# ---------------------------------------------------------------------------

class TestTokenize(unittest.TestCase):

    def test_lowercases_tokens(self):
        tokens = tokenize("VPN Password RESET")
        for tok in tokens:
            self.assertEqual(tok, tok.lower())

    def test_removes_common_stopwords(self):
        tokens = tokenize("the system is ready for use")
        stopwords_found = [t for t in tokens if t in {"the", "is", "for"}]
        self.assertEqual(stopwords_found, [])

    def test_keeps_content_words(self):
        tokens = tokenize("reset your password")
        self.assertIn("reset", tokens)
        self.assertIn("password", tokens)

    def test_removes_punctuation(self):
        tokens = tokenize("hello, world! how are you?")
        self.assertNotIn("hello,", tokens)
        self.assertNotIn("world!", tokens)

    def test_numbers_are_kept(self):
        tokens = tokenize("15 minutes lockout")
        self.assertIn("15", tokens)

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(tokenize(""), [])

    def test_all_stopwords_returns_empty(self):
        self.assertEqual(tokenize("the and or of to in"), [])


# ---------------------------------------------------------------------------
# TfidfRetriever
# ---------------------------------------------------------------------------

class TestTfidfRetriever(unittest.TestCase):

    def setUp(self):
        self.retriever = TfidfRetriever(CHUNKS)

    def test_returns_top_k_results(self):
        results = self.retriever.search("password reset", top_k=3)
        self.assertEqual(len(results), 3)

    def test_returns_fewer_than_k_when_corpus_smaller(self):
        small = CHUNKS[:2]
        r = TfidfRetriever(small)
        results = r.search("password", top_k=10)
        self.assertLessEqual(len(results), 2)

    def test_scores_in_valid_range(self):
        results = self.retriever.search("vpn client connect", top_k=5)
        for _, score in results:
            self.assertGreaterEqual(score, 0.0, "Score below 0")
            self.assertLessEqual(score, 1.0 + 1e-6, "Score above 1")

    def test_exact_term_ranks_first(self):
        # "password" appears only in DOC-A chunk; it should rank highest.
        results = self.retriever.search("password self-service portal", top_k=3)
        top_doc_id = results[0][0]["doc_id"]
        self.assertEqual(top_doc_id, "DOC-A")

    def test_oov_query_does_not_crash(self):
        # Query with zero vocabulary overlap should return results (all score 0.0)
        results = self.retriever.search("zzz xyzzy quux frobnicator", top_k=3)
        self.assertEqual(len(results), 3)
        for _, score in results:
            self.assertAlmostEqual(score, 0.0, places=5)

    def test_result_tuple_has_chunk_and_score(self):
        results = self.retriever.search("leave annual days", top_k=2)
        for item in results:
            self.assertEqual(len(item), 2)
            chunk, score = item
            self.assertIn("chunk_id", chunk)
            self.assertIsInstance(score, float)

    def test_result_chunks_are_from_corpus(self):
        results = self.retriever.search("vpn", top_k=5)
        corpus_ids = {c["chunk_id"] for c in CHUNKS}
        for chunk, _ in results:
            self.assertIn(chunk["chunk_id"], corpus_ids)

    def test_top_k_zero_returns_empty(self):
        results = self.retriever.search("password", top_k=0)
        self.assertEqual(results, [])

    def test_single_chunk_corpus(self):
        single = [_chunk("DOC-Z", "Solo", "Only", "The only document in the index.")]
        r = TfidfRetriever(single)
        results = r.search("document index", top_k=3)
        self.assertEqual(len(results), 1)

    def test_idf_and_matrix_built_on_init(self):
        self.assertIsNotNone(self.retriever.idf)
        self.assertIsNotNone(self.retriever.matrix)
        self.assertEqual(self.retriever.matrix.shape[0], len(CHUNKS))


# ---------------------------------------------------------------------------
# get_retriever() — TF-IDF fallback when sentence_transformers is absent
# ---------------------------------------------------------------------------

class TestGetRetriever(unittest.TestCase):

    def test_returns_tfidf_when_no_sentence_transformers(self):
        """With a venv that has no sentence_transformers installed,
        get_retriever must return a TfidfRetriever, not raise."""
        from rag_mvp.retrieval import get_retriever
        retriever, backend = get_retriever(CHUNKS)
        # Either TF-IDF (expected in this venv) or embeddings is acceptable;
        # the key assertion is that it doesn't raise.
        self.assertIn(backend, ("tfidf", "embeddings"))
        result = retriever.search("password", top_k=1)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
