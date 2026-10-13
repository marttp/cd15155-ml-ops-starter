# Task 4 container evidence

GitHub Actions Linux validation passed on 13 October 2026:
https://github.com/marttp/cd15155-ml-ops-starter/actions/runs/38375076457

The python:3.12-slim image installs a CPU PyTorch wheel and a runtime requirements
file, copies app/, caches the immutable FinBERT model during its smoke test,
exposes port 8000, and starts the FastAPI service. It runs as a non-root user.
Development, DVC, load-testing, and NLP quality-check dependencies remain outside
the serving image. Environment files and generated artifacts are excluded from
its build context.

Compose has a build context, 8000:8000 port mapping, .env reference, MLflow
artifact mounts, host-gateway mapping, and GET /health health check. It overrides
the local MLflow hostname for container access and binds the API to all container
interfaces. The default local Compose mode loads the production MLflow alias;
GitHub verification uses the cached Hugging Face model.

Observed GitHub results: Compose configuration validation, successful Docker
build including real smoke inference, container startup with HF_HUB_OFFLINE=1,
HTTP health response, and valid real single and batch prediction responses.
The workflow includes container logs and state diagnostics. Only configuration
validation ran locally; image build and container execution ran in GitHub Actions
as required by the starter restriction. No AWS resources or credentials were used.
