# Task 3 API evidence

Verified on 13 October 2026 against the real corrected Hugging Face FinBERT
model. The design follows the starter endpoint contract and course API examples.

`GET /health` returns status ok when loaded and HTTP 503 otherwise.
`POST /predict` returns text, sentiment, confidence, and measured latency_ms.
`POST /predict/batch` preserves the input ordering and returns one result per text.
Pydantic rejects empty or whitespace text, empty lists, and blank batch items
with HTTP 422. Both prediction routes return HTTP 503 when unloaded.
`run_prediction(text)` and `run_predictions(texts)` share measured inference.
For a batch, each result reports the full batch inference duration, not an
independently measured per-item duration. Inputs over 2,000 characters produce
a warning; tokenizer truncation limits inference to 512 tokens.

All 22 API and promotion tests passed with normal pytest process teardown.
The starter's unconditional os._exit teardown override was removed because
this verified environment exits successfully without hiding teardown failures.

Locust used four concurrent users, spawn rate two per second, and a 20-second
run against the local HTTP server. Tasks have weights 3, 1, 1 for single,
batch, and health, with a 0.5 to 1.5 second wait interval. Observed aggregate:
75 requests, 0 failures,
29.03 ms mean HTTP response time.
The CSV is saved in evidence/task-3-load.csv. This short local run verifies
concurrent operation; it does not establish AWS throughput or a production SLO.
