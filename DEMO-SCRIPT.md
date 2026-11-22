# Three-minute final demonstration

Use the existing NumPy-only virtual environment. Before recording, run `python -m unittest discover -s tests -v` and `python -m rag_mvp.eval` in separate terminal sessions or save their output. Start the local app and open http://127.0.0.1:8080/. On Windows, replace `python` with `.\.venv\Scripts\python.exe`. Do not present fictional policies as real, or imply IBM Bob or watsonx.ai is the application's runtime model.

## 0:00–0:25 — Introduction
"Hello, my name is Swamy Gorla. My IBM SkillsBuild project is the RAG Knowledge Assistant for IT support and operations. It aims to reduce the time employees spend searching support documents by making information easier to find and trace to its source."

## 0:25–0:50 — Architecture
Show the README architecture and corpus.
"The prototype indexes eight synthetic support documents into 32 sections. TF-IDF and cosine similarity retrieve relevant passages. An extractive answer engine selects sentences, attaches source citations and attempts to decline questions with insufficient evidence."

## 0:50–1:25 — Supported question
In the browser, click the password reset sample question.
"Here, the assistant retrieves password-reset instructions. The source cards identify the document title, section, owner and update date. The interface also displays retrieved passages, similarity scores and retrieval latency."

## 1:25–1:45 — Unsupported question
Click the guest Wi-Fi password sample.
"This information is absent from the pilot documents. The assistant returns an insufficient-evidence response and refers the user to the fictional help desk rather than guessing."

## 1:45–2:15 — IBM Bob and automated tests
Show IBM-BOB-CONTRIBUTIONS.md and the executed test summary.
"I used IBM Bob for a final code review, analysis of failed evaluation cases, HTTP security improvements and automated testing. The local test run passed all 85 tests covering ingestion, retrieval, answering and HTTP behavior. These tests are distinct from the question-answer evaluation."

## 2:15–2:45 — Evaluation findings
Show the 20-question evaluation output.
"Following coach feedback, the evaluation expanded from ten to twenty questions. Sixteen passed, with a grounded-answer rate of 83 percent, citation coverage of 100 percent and correct-fallback rate of 75 percent. Four failures remain: two missed supported questions and two out-of-scope answers."

## 2:45–3:00 — Conclusion
"This is a local extractive QA prototype, not a deployed generative system. Future work includes scope validation, improved semantic retrieval and watsonx.ai integration. Thank you."

Check recording duration and audio. Upload to the program's accepted video platform and verify that the link opens in a signed-out browser.
