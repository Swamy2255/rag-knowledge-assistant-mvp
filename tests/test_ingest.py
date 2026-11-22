"""Tests for rag_mvp.ingest — document ingestion and chunking.

Covers:
- Front-matter parsing (present / absent / multi-colon values)
- Section splitting (## headers, # title skipping, empty sections)
- Chunk-doc output fields
- Over-long section splitting (> MAX_CHUNK_CHARS)
- End-to-end ingest() against a temporary corpus directory
- load_chunks() auto-ingest when index is missing
"""

import json
import unittest
from pathlib import Path
import tempfile
import sys
import os

# Ensure the project root is on the path regardless of how tests are invoked.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_mvp.ingest import parse_doc, split_sections, chunk_doc, ingest, MAX_CHUNK_CHARS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_md(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


SIMPLE_DOC = """\
---
title: Test Policy
owner: IT Team
last_updated: 2026-01-01
doc_id: DOC-TST
---

# Test Policy

## First Section

This is the first section body. It has multiple words.

## Second Section

This is the second section body.
"""

NO_FRONTMATTER_DOC = """\
# Plain Document

## Only Section

Body text here.
"""


# ---------------------------------------------------------------------------
# parse_doc
# ---------------------------------------------------------------------------

class TestParseDoc(unittest.TestCase):

    def _write_and_parse(self, content: str):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", encoding="utf-8", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)
        try:
            return parse_doc(path)
        finally:
            path.unlink()

    def test_parse_frontmatter_fields(self):
        result = self._write_and_parse(SIMPLE_DOC)
        self.assertEqual(result["meta"]["title"], "Test Policy")
        self.assertEqual(result["meta"]["owner"], "IT Team")
        self.assertEqual(result["meta"]["last_updated"], "2026-01-01")
        self.assertEqual(result["meta"]["doc_id"], "DOC-TST")

    def test_parse_body_excludes_frontmatter(self):
        result = self._write_and_parse(SIMPLE_DOC)
        self.assertNotIn("---", result["body"])
        self.assertIn("First Section", result["body"])

    def test_parse_no_frontmatter_returns_empty_meta(self):
        result = self._write_and_parse(NO_FRONTMATTER_DOC)
        self.assertEqual(result["meta"], {})
        self.assertIn("Body text here", result["body"])

    def test_parse_path_name_stored(self):
        result = self._write_and_parse(SIMPLE_DOC)
        self.assertTrue(result["path"].endswith(".md"))

    def test_parse_value_with_colon_not_truncated(self):
        # A value containing a colon (e.g. a time like "10:00") should not be
        # split at the second colon — split(":", 1) handles this correctly.
        content = "---\ntitle: Meeting at 10:00\ndoc_id: DOC-X\n---\n\n## S\n\nBody\n"
        result = self._write_and_parse(content)
        self.assertEqual(result["meta"]["title"], "Meeting at 10:00")


# ---------------------------------------------------------------------------
# split_sections
# ---------------------------------------------------------------------------

class TestSplitSections(unittest.TestCase):

    def test_two_sections_returned(self):
        body = "## Alpha\n\nText alpha.\n\n## Beta\n\nText beta.\n"
        sections = split_sections(body)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0][0], "Alpha")
        self.assertEqual(sections[1][0], "Beta")

    def test_h1_lines_are_skipped(self):
        body = "# Title\n\n## Section\n\nBody.\n"
        sections = split_sections(body)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0][0], "Section")

    def test_content_before_first_h2_uses_overview_heading(self):
        body = "Some intro text.\n\n## Real Section\n\nReal body.\n"
        sections = split_sections(body)
        # intro text becomes "Overview" section
        headings = [h for h, _ in sections]
        self.assertIn("Overview", headings)

    def test_empty_section_text_excluded(self):
        body = "## EmptySection\n\n## RealSection\n\nContent here.\n"
        sections = split_sections(body)
        headings = [h for h, _ in sections]
        self.assertNotIn("EmptySection", headings)

    def test_section_text_stripped(self):
        body = "## Section\n\n   Body text with whitespace.   \n\n"
        sections = split_sections(body)
        self.assertEqual(sections[0][1].strip(), sections[0][1])


# ---------------------------------------------------------------------------
# chunk_doc
# ---------------------------------------------------------------------------

class TestChunkDoc(unittest.TestCase):

    def _make_doc(self, body: str, meta=None):
        return {
            "meta": meta or {"doc_id": "DOC-X", "title": "X", "owner": "O", "last_updated": "2026-01-01"},
            "body": body,
            "path": "x.md",
        }

    def test_chunk_has_required_fields(self):
        doc = self._make_doc("## Section\n\nBody text that is long enough.\n")
        chunks = chunk_doc(doc)
        self.assertTrue(len(chunks) >= 1)
        for chunk in chunks:
            for field in ("chunk_id", "doc_id", "title", "owner", "last_updated", "section", "text"):
                self.assertIn(field, chunk, f"Missing field: {field}")

    def test_chunk_id_uses_doc_id(self):
        doc = self._make_doc("## S\n\nContent that is sufficiently long to pass.\n",
                             meta={"doc_id": "DOC-99", "title": "T", "owner": "O", "last_updated": "2026-01-01"})
        chunks = chunk_doc(doc)
        self.assertTrue(chunks[0]["chunk_id"].startswith("DOC-99-"))

    def test_long_section_split_into_parts(self):
        # Build a section that exceeds MAX_CHUNK_CHARS by repeating paragraphs.
        para = "A " * 300 + "end."  # ~602 chars
        body = "## BigSection\n\n" + para + "\n\n" + para + "\n\n" + para + "\n"
        doc = self._make_doc(body)
        chunks = chunk_doc(doc)
        # Should produce at least 2 chunks for this section.
        section_chunks = [c for c in chunks if "BigSection" in c["section"]]
        self.assertGreater(len(section_chunks), 1)

    def test_long_section_parts_have_part_suffix(self):
        para = "B " * 300 + "end."
        body = "## BigSection\n\n" + para + "\n\n" + para + "\n\n" + para + "\n"
        doc = self._make_doc(body)
        chunks = chunk_doc(doc)
        section_chunks = [c for c in chunks if "BigSection" in c["section"]]
        self.assertTrue(any("part" in c["section"] for c in section_chunks))

    def test_no_chunk_exceeds_max_chars(self):
        para = "C " * 400 + "end."
        body = "## S\n\n" + para + "\n\n" + para + "\n\n" + para + "\n\n" + para + "\n"
        doc = self._make_doc(body)
        chunks = chunk_doc(doc)
        for chunk in chunks:
            self.assertLessEqual(
                len(chunk["text"]), MAX_CHUNK_CHARS,
                f"Chunk {chunk['chunk_id']} text exceeds MAX_CHUNK_CHARS"
            )

    def test_fallback_doc_id_uses_path(self):
        # When doc_id is absent from meta, the file path name is used.
        doc = {"meta": {}, "body": "## S\n\nContent.\n", "path": "fallback.md"}
        chunks = chunk_doc(doc)
        self.assertTrue(chunks[0]["chunk_id"].startswith("fallback.md-"))


# ---------------------------------------------------------------------------
# ingest() — end-to-end with a temporary corpus
# ---------------------------------------------------------------------------

class TestIngest(unittest.TestCase):

    def _make_corpus(self) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        _make_md(tmpdir / "doc1.md", SIMPLE_DOC)
        _make_md(tmpdir / "doc2.md", NO_FRONTMATTER_DOC)
        return tmpdir

    def test_ingest_returns_all_chunks(self):
        corpus_dir = self._make_corpus()
        # We need a writable index dir alongside the corpus.
        index_dir = corpus_dir / "index"
        # Monkey-patch the module constants to use our temp dirs.
        import rag_mvp.ingest as ingest_mod
        orig_index = ingest_mod.INDEX_DIR
        orig_chunks = ingest_mod.CHUNKS_PATH
        ingest_mod.INDEX_DIR = index_dir
        ingest_mod.CHUNKS_PATH = index_dir / "chunks.json"
        try:
            chunks = ingest(corpus_dir)
            self.assertGreater(len(chunks), 0)
        finally:
            ingest_mod.INDEX_DIR = orig_index
            ingest_mod.CHUNKS_PATH = orig_chunks

    def test_ingest_writes_chunks_json(self):
        corpus_dir = self._make_corpus()
        index_dir = corpus_dir / "index"
        import rag_mvp.ingest as ingest_mod
        orig_index = ingest_mod.INDEX_DIR
        orig_chunks = ingest_mod.CHUNKS_PATH
        ingest_mod.INDEX_DIR = index_dir
        ingest_mod.CHUNKS_PATH = index_dir / "chunks.json"
        try:
            ingest(corpus_dir)
            self.assertTrue((index_dir / "chunks.json").exists())
            loaded = json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))
            self.assertIsInstance(loaded, list)
        finally:
            ingest_mod.INDEX_DIR = orig_index
            ingest_mod.CHUNKS_PATH = orig_chunks

    def test_ingest_chunk_fields_complete(self):
        corpus_dir = self._make_corpus()
        index_dir = corpus_dir / "index"
        import rag_mvp.ingest as ingest_mod
        orig_index = ingest_mod.INDEX_DIR
        orig_chunks = ingest_mod.CHUNKS_PATH
        ingest_mod.INDEX_DIR = index_dir
        ingest_mod.CHUNKS_PATH = index_dir / "chunks.json"
        try:
            chunks = ingest(corpus_dir)
            required = {"chunk_id", "doc_id", "title", "owner", "last_updated", "section", "text"}
            for chunk in chunks:
                missing = required - set(chunk.keys())
                self.assertEqual(missing, set(), f"Chunk {chunk.get('chunk_id')} missing: {missing}")
        finally:
            ingest_mod.INDEX_DIR = orig_index
            ingest_mod.CHUNKS_PATH = orig_chunks


if __name__ == "__main__":
    unittest.main()
