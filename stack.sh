#!/usr/bin/env bash
# Run from any directory. See README.md for prerequisites and AWS inputs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${GH_REPO:-marttp/cd15155-ml-ops-starter}"
help() {
  cat <<'HELP'
Usage: ./stack.sh COMMAND
  local-up     Prepare data, register/promote model, start Compose, log monitoring.
  local-down   Stop local containers; retain the model registry and artifacts.
  local-status Show local container state.
  aws-deploy   Run and wait for the existing complete GitHub CI/CD pipeline.
  aws-up       Resume the existing AWS service and wait for stability.
  aws-down     Pause AWS tasks and wait for stability.
Inputs: PYTHON_BIN (default starter/.venv/bin/python), GH_REPO (fork owner/repo).
No AWS credentials are accepted by this script. Store them in GitHub secrets.
HELP
}
need() { command -v "$1" >/dev/null || { echo "Missing prerequisite: $1. See README.md." >&2; exit 1; }; }
compose() { docker compose --project-name finbert-stack -f docker-compose.yml -f stack.compose.yml "$@"; }
aws_run() {
  need gh
  gh auth status >/dev/null
  # Wait for a newly dispatched run rather than the previous completed run.
  local workflow="$1"; shift
  local before run attempt
  before="$(gh api "repos/$REPO/actions/workflows/$workflow/runs?per_page=1" --jq '.workflow_runs[0].id // 0')"
  gh workflow run "$workflow" --repo "$REPO" --ref main "$@"
  for attempt in $(seq 1 30); do
    run="$(gh api "repos/$REPO/actions/workflows/$workflow/runs?event=workflow_dispatch&branch=main&per_page=1" --jq '.workflow_runs[0].id // 0')"
    if [[ "$run" -gt "$before" ]]; then
      gh run watch "$run" --repo "$REPO" --exit-status
      echo "Run and downloadable evidence: https://github.com/$REPO/actions/runs/$run"
      return
    fi
    sleep 2
  done
  echo 'Dispatch sent, but its run was not found. Check GitHub Actions.' >&2
  exit 1
}
case "${1:-help}" in
  help|--help|-h) help ;;
  aws-deploy) aws_run ci-cd.yml -f diagnostics=false ;;
  aws-up) aws_run service-control.yml -f desired_count=1 ;;
  aws-down) aws_run service-control.yml -f desired_count=0 ;;
  local-down|local-status)
    need docker; cd "$ROOT/starter"
    if [[ "$1" == local-down ]]; then compose down; else compose ps; fi ;;
  local-up)
    need docker; need git; cd "$ROOT/starter"
    PYTHON="${PYTHON_BIN:-$ROOT/starter/.venv/bin/python}"
    [[ -x "$PYTHON" ]] || { echo 'Python environment missing. See README.md.' >&2; exit 1; }
    "$PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 required"; import dvc, mlflow, datasets, torch'
    docker info >/dev/null
    [[ -f .env ]] || cp .env.example .env
    export MLFLOW_TRACKING_URI=http://127.0.0.1:5001 MODEL_NAME=finbert MODEL_STAGE=production MODEL_SOURCE=mlflow
    export MLFLOW_EXPERIMENT_NAME=finbert-evaluation API_BASE_URL=http://127.0.0.1:8000
    export HF_MODEL_ID=baptle/FinBERT_market_based HF_MODEL_REVISION=ec5ffa074fc00da4de8b28554a57aa1debf92508
    export HF_DATASET_ID=baptle/financial_headlines_market_based MODEL_NUM_THREADS=2
    "$PYTHON" -m dvc repro
    compose up -d mlflow
    "$PYTHON" - <<'PY'
import time, urllib.request, urllib.error
for attempt in range(60):
    try:
        with urllib.request.urlopen('http://127.0.0.1:5001/health', timeout=3) as response:
            assert response.status == 200
        break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(2)
else:
    raise SystemExit('MLflow did not start. Inspect docker compose logs.')
PY
    "$PYTHON" scripts/evaluate.py
    "$PYTHON" scripts/promote.py
    "$PYTHON" - <<'PY'
from mlflow import MlflowClient
client = MlflowClient()
alias = client.get_model_version_by_alias('finbert', 'production')
latest = max(client.search_model_versions("name = 'finbert'"), key=lambda v: int(v.version))
if alias.version != latest.version:
    raise SystemExit('Latest model failed promotion; API startup aborted.')
PY
    compose up -d --build --wait --wait-timeout 600 api prometheus
    "$PYTHON" monitoring/stream.py
    "$PYTHON" - <<'PY'
import time, requests
requests.get('http://127.0.0.1:8000/health', timeout=10).raise_for_status()
for attempt in range(20):
    try:
        response = requests.get('http://127.0.0.1:9090/api/v1/targets', timeout=10)
        response.raise_for_status()
        targets = response.json()['data']['activeTargets']
    except requests.RequestException:
        time.sleep(2)
        continue
    if any(t['labels'].get('job') == 'finbert-api' and t['health'] == 'up' for t in targets):
        break
    time.sleep(2)
else:
    raise SystemExit('Prometheus did not scrape the API successfully.')
PY
    echo 'Ready: API http://127.0.0.1:8000/docs | MLflow http://127.0.0.1:5001 | Prometheus http://127.0.0.1:9090'
    ;;
  *) help >&2; exit 2 ;;
esac
