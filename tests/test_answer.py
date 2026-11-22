"""Tests for rag_mvp.answer — extractive answering, citations, and fallback.

Covers:
- Fallback triggered by low retrieval score (below threshold)
- Fallback triggered by no sentence overlap (second path)
- Successful answer includes citation fields
- At most 2 sentences per chunk in the answer
- Answer text prefix ("Based on the approved support documents:")
- Citation numbering starts at 1 and is sequential
- Fallback response has empty citations list
- split_sentences() minimum-length filter
- answer() metadata fields present (backend, threshold, latency_ms, mode)
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_mvp.answer import answer, split_sentences, FALLBACK_TEXT, DEFAULT_THRESHOLDS


# ---------------------------------------------------------------------------
# Minimal stub retriever — allows injecting arbitrary (chunk, score) pairs
# ---------------------------------------------------------------------------

class _StubRetriever:
    """Returns a fixed list of (chunk, score) tuples."""

    def __init__(self, results: list):
        self._results = results

    def search(self, query: str, top_k: int = 3) -> list:  # noqa: ARG002
        return self._results[:top_k]


def _chunk(doc_id="DOC-T", section="Section", text="Default text for testing purposes."):
    return {
        "chunk_id": f"{doc_id}-01",
        "doc_id": doc_id,
        "title": f"Title {doc_id}",
        "owner": "Test Owner",
        "last_updated": "2026-01-01",
        "section": section,
        "text": text,
    }


# ---------------------------------------------------------------------------
# split_sentences()
# ---------------------------------------------------------------------------

class TestSplitSentences(unittest.TestCase):

    def test_splits_on_period(self):
        # Sentences must exceed the 20-char minimum enforced by split_sentences().
        text = (
            "Use the self-service portal to reset your forgotten password. "
            "Contact the IT Help Desk if you do not have access to your recovery email."
        )
        sentences = split_sentences(text)
        self.assertGreaterEqual(len(sentences), 2)

    def test_minimum_length_20_chars(self):
        # Short sentences (< 20 chars) must be dropped.
        text = "Yes. No. This is a sentence that is long enough to pass the filter."
        sentences = split_sentences(text)
        for s in sentences:
            self.assertGreaterEqual(len(s), 20, f"Short sentence passed filter: {s!r}")

    def test_newlines_treated_as_spaces(self):
        text = "First long sentence here.\nSecond long sentence here."
        sentences = split_sentences(text)
        for s in sentences:
            self.assertNotIn("\n", s)

    def test_empty_text_returns_empty(self):
        self.assertEqual(split_sentences(""), [])

    def test_single_sentence_returns_one(self):
        text = "This is a single sentence that is long enough."
        sentences = split_sentences(text)
        self.assertEqual(len(sentences), 1)


# ---------------------------------------------------------------------------
# Fallback: low score
# ---------------------------------------------------------------------------

class TestFallbackLowScore(unittest.TestCase):

    def _make_chunk_with_matching_text(self):
        return _chunk(
            text="Use the self-service portal to reset your password immediately."
        )

    def test_fallback_on_score_below_threshold(self):
        chunk = self._make_chunk_with_matching_text()
        retriever = _StubRetriever([(chunk, 0.05)])  # well below 0.30
        result = answer("reset password", retriever, "tfidf", threshold=0.30)
        self.assertTrue(result["fallback"])
        self.assertEqual(result["citations"], [])

    def test_fallback_answer_text_matches_constant(self):
        chunk = self._make_chunk_with_matching_text()
        retriever = _StubRetriever([(chunk, 0.05)])
        result = answer("reset password", retriever, "tfidf", threshold=0.30)
        self.assertEqual(result["answer"], FALLBACK_TEXT)

    def test_fallback_still_returns_retrieved_list(self):
        chunk = self._make_chunk_with_matching_text()
        retriever = _StubRetriever([(chunk, 0.05)])
        result = answer("reset password", retriever, "tfidf", threshold=0.30)
        self.assertEqual(len(result["retrieved"]), 1)
        self.assertEqual(result["retrieved"][0]["doc_id"], "DOC-T")

    def test_fallback_on_empty_retrieval(self):
        retriever = _StubRetriever([])
        result = answer("anything", retriever, "tfidf", threshold=0.30)
        self.assertTrue(result["fallback"])

    def test_fallback_flag_true_in_result(self):
        chunk = self._make_chunk_with_matching_text()
        retriever = _StubRetriever([(chunk, 0.01)])
        result = answer("x", retriever, "tfidf", threshold=0.30)
        self.assertIs(result["fallback"], True)


# ---------------------------------------------------------------------------
# Fallback: no sentence overlap (second path)
# ---------------------------------------------------------------------------

class TestFallbackNoOverlap(unittest.TestCase):

    def test_fallback_when_sentences_have_zero_overlap(self):
        # Score is high enough but no sentence tokens match the query.
        chunk = _chunk(text="Apple orange banana cherry mango grape lemon.")
        retriever = _StubRetriever([(chunk, 0.99)])
        result = answer("reset password vpn certificate", retriever, "tfidf", threshold=0.30)
        self.assertTrue(result["fallback"])
        self.assertEqual(result["citations"], [])


# ---------------------------------------------------------------------------
# Successful answer
# ---------------------------------------------------------------------------

class TestSuccessfulAnswer(unittest.TestCase):

    def _make_retriever_with_matching_chunk(self):
        text = (
            "Use the self-service password reset portal to change your password. "
            "Visit password.company.example to start the reset process. "
            "A reset link is valid for thirty minutes."
        )
        chunk = _chunk(doc_id="DOC-001", section="Self-service reset", text=text)
        return _StubRetriever([(chunk, 0.50)])

    def test_no_fallback_on_high_score_with_overlap(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("how do I reset my password", retriever, "tfidf", threshold=0.30)
        self.assertFalse(result["fallback"])

    def test_answer_text_has_prefix(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("how do I reset my password", retriever, "tfidf", threshold=0.30)
        self.assertTrue(result["answer"].startswith("Based on the approved support documents:"))

    def test_at_least_one_citation(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("how do I reset my password", retriever, "tfidf", threshold=0.30)
        self.assertGreaterEqual(len(result["citations"]), 1)

    def test_citation_has_required_fields(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("how do I reset my password", retriever, "tfidf", threshold=0.30)
        for cite in result["citations"]:
            for field in ("n", "title", "section", "owner", "last_updated", "doc_id"):
                self.assertIn(field, cite, f"Citation missing field: {field}")

    def test_citation_numbering_starts_at_1(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("how do I reset my password", retriever, "tfidf", threshold=0.30)
        self.assertEqual(result["citations"][0]["n"], 1)

    def test_at_most_2_sentences_from_single_chunk(self):
        # Provide a chunk with many matching sentences.
        sentences = " ".join([
            f"Reset your password using the portal number {i}."
            for i in range(10)
        ])
        chunk = _chunk(text=sentences)
        retriever = _StubRetriever([(chunk, 0.80)])
        result = answer("reset password portal", retriever, "tfidf", threshold=0.30)
        if not result["fallback"]:
            # Count sentences attributed to the single chunk in the answer.
            # The answer text uses [1] inline markers; count them.
            marker_count = result["answer"].count("[1]")
            self.assertLessEqual(marker_count, 2)

    def test_metadata_fields_present(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("reset password", retriever, "tfidf", threshold=0.30)
        for field in ("question", "answer", "citations", "retrieved",
                      "fallback", "backend", "threshold", "latency_ms", "mode"):
            self.assertIn(field, result, f"Result missing field: {field}")

    def test_backend_field_matches_input(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("reset password", retriever, "tfidf", threshold=0.30)
        self.assertEqual(result["backend"], "tfidf")

    def test_threshold_field_matches_input(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("reset password", retriever, "tfidf", threshold=0.25)
        self.assertEqual(result["threshold"], 0.25)

    def test_mode_field_indicates_extractive(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("reset password", retriever, "tfidf", threshold=0.30)
        self.assertIn("extractive", result["mode"].lower())

    def test_latency_ms_is_non_negative(self):
        retriever = self._make_retriever_with_matching_chunk()
        result = answer("reset password", retriever, "tfidf", threshold=0.30)
        self.assertGreaterEqual(result["latency_ms"], 0.0)


# ---------------------------------------------------------------------------
# Default threshold handling
# ---------------------------------------------------------------------------

class TestDefaultThreshold(unittest.TestCase):

    def test_default_threshold_used_when_none_passed(self):
        chunk = _chunk(text="Connecting to the VPN requires corporate credentials.")
        # Score just above the default tfidf threshold (0.30)
        retriever = _StubRetriever([(chunk, 0.35)])
        result = answer("vpn connect credentials", retriever, "tfidf", threshold=None)
        self.assertEqual(result["threshold"], DEFAULT_THRESHOLDS["tfidf"])

    def test_unknown_backend_uses_fallback_default(self):
        chunk = _chunk(text="Some content about network access and credentials.")
        retriever = _StubRetriever([(chunk, 0.05)])
        # Should not raise; uses DEFAULT_THRESHOLDS.get(backend, 0.10)
        result = answer("network", retriever, "unknown_backend", threshold=None)
        self.assertIn("threshold", result)


if __name__ == "__main__":
    unittest.main()
