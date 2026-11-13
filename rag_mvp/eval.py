"""Eval harness: runs the fixed question set in eval/questions.jsonl and
reports pass/fail plus the metrics from the Solution Blueprint:

- grounded-answer rate: answerable questions answered correctly
- citation coverage: non-fallback answers carrying >= 1 citation
- fallback rate on unanswerable questions (correct fallbacks)
- false-fallback rate: answerable questions that fell back
- median latency

Usage:  python -m rag_mvp.eval [--threshold 0.30]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_mvp.answer import answer  # noqa: E402
from rag_mvp.ingest import load_chunks  # noqa: E402
from rag_mvp.retrieval import get_retriever  # noqa: E402

QUESTIONS_PATH = PROJECT_ROOT / "eval" / "questions.jsonl"
RESULTS_PATH = PROJECT_ROOT / "eval" / "results.json"


def load_questions() -> list[dict]:
    return [json.loads(line) for line in
            QUESTIONS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_eval(threshold: float | None = None) -> dict:
    chunks = load_chunks()
    retriever, backend = get_retriever(chunks)
    questions = load_questions()
    started = time.perf_counter()
    rows = []
    for q in questions:
        result = answer(q["question"], retriever, backend, threshold=threshold)
        retrieved_ids = {r["doc_id"] for r in result["retrieved"]}
        if q["expect"] == "answer":
            keywords = q.get("keywords", [])
            answer_lower = result["answer"].lower()
            kw_hits = [k for k in keywords if k.lower() in answer_lower]
            passed = (
                not result["fallback"]
                and q["expected_doc"] in retrieved_ids
                and len(kw_hits) >= max(1, len(keywords) // 2)
                and len(result["citations"]) >= 1
            )
            rows.append({
                "question": q["question"], "expect": "answer",
                "expected_doc": q["expected_doc"], "passed": passed,
                "fallback": result["fallback"],
                "top_score": result["retrieved"][0]["score"] if result["retrieved"] else 0.0,
                "retrieved_docs": sorted(retrieved_ids),
                "keyword_hits": f"{len(kw_hits)}/{len(keywords)}",
                "citations": len(result["citations"]),
                "latency_ms": result["latency_ms"],
            })
        else:  # expect fallback
            passed = result["fallback"]
            rows.append({
                "question": q["question"], "expect": "fallback",
                "expected_doc": None, "passed": passed,
                "fallback": result["fallback"],
                "top_score": result["retrieved"][0]["score"] if result["retrieved"] else 0.0,
                "retrieved_docs": sorted(retrieved_ids),
                "keyword_hits": "-",
                "citations": len(result["citations"]),
                "latency_ms": result["latency_ms"],
            })
    answerable = [r for r in rows if r["expect"] == "answer"]
    unanswerable = [r for r in rows if r["expect"] == "fallback"]
    non_fallback = [r for r in rows if not r["fallback"]]
    summary = {
        "backend": backend,
        "threshold": threshold,
        "total": len(rows),
        "grounded_answer_rate": round(
            sum(r["passed"] for r in answerable) / max(1, len(answerable)), 3),
        "citation_coverage": round(
            sum(1 for r in non_fallback if r["citations"] >= 1) / max(1, len(non_fallback)), 3),
        "fallback_correct_rate": round(
            sum(r["passed"] for r in unanswerable) / max(1, len(unanswerable)), 3),
        "false_fallback_rate": round(
            sum(1 for r in answerable if r["fallback"]) / max(1, len(answerable)), 3),
        "median_latency_ms": round(statistics.median(
            [r["latency_ms"] for r in rows]), 1) if rows else 0.0,
        "total_seconds": round(time.perf_counter() - started, 1),
    }
    return {"summary": summary, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG MVP eval harness")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Retrieval score threshold for the fallback")
    args = parser.parse_args()
    report = run_eval(threshold=args.threshold)
    RESULTS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    s = report["summary"]
    print(f"Backend: {s['backend']}  threshold: {s['threshold']}")
    print(f"Questions: {s['total']}  ({s['total_seconds']}s total)")
    print(f"Grounded-answer rate:  {s['grounded_answer_rate']:.0%}  (blueprint target: 90%)")
    print(f"Citation coverage:      {s['citation_coverage']:.0%}  (target: 100%)")
    print(f"Correct-fallback rate:  {s['fallback_correct_rate']:.0%}")
    print(f"False-fallback rate:    {s['false_fallback_rate']:.0%}")
    print(f"Median latency:         {s['median_latency_ms']} ms")
    print()
    for row in report["rows"]:
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"[{mark}] ({row['expect']}, top={row['top_score']:.2f}) {row['question']}")
        if not row["passed"]:
            print(f"       retrieved={row['retrieved_docs']} keywords={row['keyword_hits']} "
                  f"fallback={row['fallback']} citations={row['citations']}")
    print(f"\nFull report: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
