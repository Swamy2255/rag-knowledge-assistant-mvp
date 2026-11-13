"""Ingestion: parse the pilot corpus (Markdown + YAML-ish front matter) into
searchable chunks and write them to index/chunks.json.

Chunking rule (per the Technical Architecture doc): one chunk per "##"
section. Sections in the pilot corpus are short, so no further splitting is
needed; a hard cap of 1,500 characters guards against a runaway section.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"
INDEX_DIR = PROJECT_ROOT / "index"
CHUNKS_PATH = INDEX_DIR / "chunks.json"

MAX_CHUNK_CHARS = 1500


def parse_doc(path: Path) -> dict:
    """Parse one corpus Markdown file into metadata + sections."""
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            front = text[3:end].strip()
            for line in front.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip()
            body = text[end + 4:].strip()
    return {"meta": meta, "body": body, "path": path.name}


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split a document body into (section heading, section text) pairs."""
    sections: list[tuple[str, str]] = []
    current_heading = "Overview"
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line[3:].strip()
            current_lines = []
        elif line.startswith("# "):
            continue  # document title, already in metadata
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return [(h, t) for h, t in sections if t]


def chunk_doc(doc: dict) -> list[dict]:
    """Turn one parsed document into chunk records."""
    meta = doc["meta"]
    chunks = []
    for section, section_text in split_sections(doc["body"]):
        # Hard cap: split over-long sections on paragraph boundaries.
        parts = [section_text]
        if len(section_text) > MAX_CHUNK_CHARS:
            parts = []
            buf = ""
            for para in section_text.split("\n\n"):
                if len(buf) + len(para) + 2 > MAX_CHUNK_CHARS and buf:
                    parts.append(buf.strip())
                    buf = para
                else:
                    buf = f"{buf}\n\n{para}" if buf else para
            if buf:
                parts.append(buf.strip())
        for i, part in enumerate(parts):
            suffix = f" (part {i + 1})" if len(parts) > 1 else ""
            chunks.append(
                {
                    "chunk_id": f"{meta.get('doc_id', doc['path'])}-{len(chunks) + 1:02d}",
                    "doc_id": meta.get("doc_id", doc["path"]),
                    "title": meta.get("title", doc["path"]),
                    "owner": meta.get("owner", "Unknown"),
                    "last_updated": meta.get("last_updated", "Unknown"),
                    "section": section + suffix,
                    "text": part,
                }
            )
    return chunks


def ingest(corpus_dir: Path = CORPUS_DIR) -> list[dict]:
    """Ingest every .md file in the corpus directory. Returns all chunks."""
    all_chunks: list[dict] = []
    for path in sorted(corpus_dir.glob("*.md")):
        all_chunks.extend(chunk_doc(parse_doc(path)))
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_PATH.write_text(
        json.dumps(all_chunks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return all_chunks


def load_chunks() -> list[dict]:
    if not CHUNKS_PATH.exists():
        return ingest()
    return json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    chunks = ingest()
    docs = {c["doc_id"] for c in chunks}
    print(f"Ingested {len(chunks)} chunks from {len(docs)} documents.")
    for chunk in chunks:
        print(f"  {chunk['chunk_id']}: {chunk['title']} — {chunk['section']}")
