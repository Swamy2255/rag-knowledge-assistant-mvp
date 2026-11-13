"""CLI for the RAG knowledge assistant MVP.

Usage (from the project root, with the venv active):
    python -m rag_mvp.cli ingest          # (re)build the chunk index
    python -m rag_mvp.cli ask "question"  # ask one question
    python -m rag_mvp.cli repl            # interactive question loop
    python -m rag_mvp.cli eval            # run the eval harness
    python -m rag_mvp.cli demo            # the two demo questions
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_mvp.answer import answer  # noqa: E402
from rag_mvp.ingest import ingest, load_chunks  # noqa: E402
from rag_mvp.retrieval import get_retriever  # noqa: E402


def _load():
    chunks = load_chunks()
    retriever, backend = get_retriever(chunks)
    return retriever, backend


def _print_result(result: dict) -> None:
    print()
    print(f"Q: {result['question']}")
    print(f"A: {result['answer']}")
    if result["fallback"]:
        print("   [fallback — no passage scored above the threshold]")
    for cite in result["citations"]:
        print(f"   [{cite['n']}] {cite['title']} — {cite['section']} "
              f"(Owner: {cite['owner']}, updated {cite['last_updated']})")
    print(f"   — backend: {result['backend']}, mode: {result['mode']}, "
          f"latency: {result['latency_ms']} ms")


def cmd_ingest(_args) -> None:
    chunks = ingest()
    print(f"Ingested {len(chunks)} chunks from the corpus.")


def cmd_ask(args) -> None:
    retriever, backend = _load()
    result = answer(args.question, retriever, backend, threshold=args.threshold)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_result(result)


def cmd_repl(args) -> None:
    retriever, backend = _load()
    print("RAG knowledge assistant (type 'quit' to exit).")
    while True:
        try:
            question = input("\nAsk: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if question.lower() in {"quit", "exit", "q"}:
            print("Bye.")
            break
        if not question:
            continue
        _print_result(answer(question, retriever, backend,
                             threshold=args.threshold))


def cmd_eval(args) -> None:
    from rag_mvp.eval import main as eval_main
    sys.argv = ["eval"] + (["--threshold", str(args.threshold)]
                           if args.threshold is not None else [])
    eval_main()


def cmd_demo(_args) -> None:
    retriever, backend = _load()
    print("=== Demo 1: answerable question (citations expected) ===")
    _print_result(answer(
        "How do I reset my password if I forgot it?", retriever, backend))
    print()
    print("=== Demo 2: unanswerable question (fallback expected) ===")
    _print_result(answer(
        "What is the Wi-Fi password for the guest network?", retriever, backend))


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG knowledge assistant MVP")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Retrieval score threshold for the fallback")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest")
    ask_p = sub.add_parser("ask")
    ask_p.add_argument("question")
    ask_p.add_argument("--json", action="store_true")
    sub.add_parser("repl")
    sub.add_parser("eval")
    sub.add_parser("demo")
    args = parser.parse_args()
    {"ingest": cmd_ingest, "ask": cmd_ask, "repl": cmd_repl,
     "eval": cmd_eval, "demo": cmd_demo}[args.command](args)


if __name__ == "__main__":
    main()
