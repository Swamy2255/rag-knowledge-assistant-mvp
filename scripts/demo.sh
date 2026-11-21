#!/bin/bash
# Demo script for the RAG knowledge assistant MVP.
# Run from the project root:  bash scripts/demo.sh
# Shows: (1) a cited answer, (2) the "not found" fallback, (3) the eval run.
set -e
cd "$(dirname "$0")/.."

echo "================ RAG KNOWLEDGE ASSISTANT — DEMO ================"
echo
echo "--- 1. Answerable question (citations expected) ---"
python3 -m rag_mvp.cli ask "How do I reset my password if I forgot it?"
echo
echo "--- 2. Unanswerable question (fallback expected) ---"
python3 -m rag_mvp.cli ask "What is the Wi-Fi password for the guest network?"
echo
echo "--- 3. Eval harness (20 questions) ---"
python3 -m rag_mvp.eval
echo
echo "--- 4. Web UI ---"
echo "Run: python3 -m rag_mvp.app   then open http://127.0.0.1:8080"
