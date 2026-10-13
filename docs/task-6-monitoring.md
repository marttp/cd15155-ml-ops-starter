# Task 6 monitoring evidence

The implementation follows module-21-monitoring and the supplied rubric.
Local verification on 13 October 2026 passed 33 tests, including real API
metrics, prediction-error counting, JSON logs, five window metrics, and the
partial final monitoring window.

The API exports a sentiment-labelled prediction Counter, a latency Histogram
in milliseconds, an error Counter, and /metrics using Prometheus exposition
headers. JSON log entries include timestamp, level, and message, with model
loading, predictions, and errors recorded. A batch increments counters once
per prediction; each result's latency is the complete batch duration.

The local stream sent all 444 cleaned headlines to the real API and logged
nine windows, eight of 50 predictions and one of 44. All five metric histories
were read back from MLflow with steps 0 through 8. The report is committed in
`evidence/task-6-local-monitoring.json`. Evaluation and monitoring use separate
experiments and distinct run tags.

Compose adds Prometheus with job finbert-api, 15-second scrapes, and api:8000.
ECS adds Prometheus inside the same small Fargate task. A short-lived config
container writes the shared scrape configuration, substituting localhost for
Compose's service hostname. The proxy exposes its UI under /prometheus/.
The API's Prometheus metrics remain available at /metrics. No extra Fargate
task, public port, NAT gateway, or load balancer is added.

CI verifies container scraping. Deployment verifies the real production target
and then sends the entire production stream, recording MLflow metrics and
saving the monitoring database and JSON evidence as workflow artifacts.
Production verification passed on 13 October 2026:
https://github.com/marttp/cd15155-ml-ops-starter/actions/runs/38381974733

The deployed API, production Prometheus target, up query, and full monitoring
stream all passed. The production run processed 444 headlines into nine windows
and logged all five required metrics with steps 0 through 8. Actual target,
deployment, and monitoring records are committed under evidence/task-6-production-*.json.
The workflow artifact also contains the MLflow SQLite database for inspection.
Read-only ECS diagnostics verified a healthy one-task service and support later
rollout troubleshooting without changing resources.
