# Three-minute final demonstration

Record the working local application. Use the NumPy-only environment described in README.md to reproduce the committed TF-IDF baseline. Do not present synthetic policies as real policies or claim LLM, IBM Bob or watsonx.ai integration.

## 0:00–0:25 — Introduction
"Hello, my name is Swamy Gorla. My project is the RAG Knowledge Assistant for IT support and operations, developed for the IBM SkillsBuild AI Experiential Learning Lab. The goal is to make support information easier to find while providing traceable answers and reducing unsupported responses."

## 0:25–0:50 — Architecture
Show README.md and corpus/.
"The prototype processes eight synthetic support documents into searchable sections. It uses TF-IDF and cosine similarity to retrieve relevant passages. The answer engine extracts sentences and attaches citations. When relevance is insufficient, it attempts to return a fallback response."

## 0:50–1:30 — Supported question
Start python -m rag_mvp.app and open http://127.0.0.1:8080.
Ask: How do I reset my password if I forgot it?
"Here the assistant retrieves password-reset information and returns an extractive answer with numbered citations. Each citation identifies the document, section, owner and update date. Users can trace the information to its source."

## 1:30–1:55 — Unsupported question
Ask: What is the Wi-Fi password for the guest network?
"This information is not in the pilot corpus. The assistant declines to guess and directs the user to the sample help desk. This illustrates its intended fallback behavior."

## 1:55–2:35 — Evaluation
Show python -m rag_mvp.eval output and the committed eval/results.json.
"Following coach feedback, the evaluation grew from ten to twenty questions. The committed TF-IDF run passed sixteen, with 83.3 percent grounded-answer rate, 100 percent citation coverage and 75 percent correct-fallback rate. Two supported questions were declined and two unsupported questions received out-of-scope answers. These results show why more robust semantic retrieval and scope checks are needed."

## 2:35–3:00 — Conclusion
"The current implementation is a local, retrieval-augmented extractive QA prototype. No generative model or IBM Cloud service is configured. Future work includes watsonx.ai integration, stronger scope validation, and testing on approved real documents. This MVP demonstrates document retrieval, source transparency, fallback behavior and measurable evaluation. Thank you."

Before uploading: verify the demo actually runs, check the recording duration and audio, and verify the public video link in a signed-out browser.
