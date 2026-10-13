# Task 0 setup and evidence

Verified on 13 October 2026 on macOS arm64 with Python 3.12.8.
This records environment validation, not model evaluation or rubric completion
for later tasks.

## Local setup

Run from `starter/` with Python 3.12. Keep this environment separate from
other coursework. The Udacity workspace already has dependencies installed;
these installation steps apply to a local machine.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python scripts/smoke_test.py
mkdir -p mlruns
.venv/bin/mlflow server --host 127.0.0.1 --port 5001 \
  --backend-store-uri sqlite:///mlruns/mlflow.db \
  --artifacts-destination ./mlartifacts
```

The agent used `uv` to install the same requirements in `.venv`.
MLflow is available at http://127.0.0.1:5001. Port 5000 was already occupied
by macOS Control Center. The installed MLflow 2.16.2 does not offer the
`--allowed-hosts` option shown in the setup screenshot, so the local server
binds to loopback using the options supported by this version.

`.env`, `.venv`, `mlruns`, and `mlartifacts` are ignored by Git. No AWS
credentials are needed for this task. No Docker build or AWS resource was run.

## Compatibility changes

- Pin Transformers to 4.44.2 and its sentence-transformers dependency to 3.0.1
  to retain the course's Transformers 4 API alongside MLflow 2.16.2.
- Pin SQLAlchemy to 2.0.54. The original unconstrained dependency selected
  SQLAlchemy 2.1.4, which prevented MLflow from starting with an import error
  for `FallbackAsyncAdaptedQueuePool`.
- Share the Hugging Face loader between the service utility and smoke test.
  Correct the supplied FinBERT configuration in memory with labels negative,
  neutral, and positive and integer label IDs. Load the model with that
  configuration explicitly. Do not edit cached Hub configuration files.
- Enable CPU inference and tokenizer truncation at 512 tokens in the loader.

## Observed evidence

| Check | Result |
| --- | --- |
| Dependency consistency | `uv pip check` passed for 283 installed packages |
| Imports | MLflow Transformers, datasets, and Deepchecks NLP TextData imported successfully |
| Model | `baptle/FinBERT_market_based`, revision `ec5ffa074fc00da4de8b28554a57aa1debf92508` |
| Smoke inference | Record-profits headline returned positive, confidence approximately 0.545465 |
| Clean configuration | Original Hub config with float-valued labels loaded with corrected string output labels; cached config checksum stayed unchanged |
| MLflow server | `/health` returned HTTP 200 and `OK` |
| Tracking | Setup run parameter and metric were written and read back |
| Artifacts | Setup text artifact was uploaded, downloaded, and checked |

Setup experiment: `finbert-setup-validation`.
Setup run ID: `21cd8d68ac734da6a243365f9d80acb8`.
The setup run is separate from `finbert-evaluation` so it cannot be mistaken
for a qualifying model evaluation.

Observed main packages: torch 2.12.1, torchvision 0.27.1,
Transformers 4.44.2, MLflow 2.16.2, SQLAlchemy 2.0.54,
datasets 2.19.1, DVC 3.50.1, Deepchecks 0.19.1, and NumPy 1.26.4.
Installation and inference were verified on macOS; Linux container validation
remains part of Task 4. Broad transitive requirements are not a complete
environment lock.

## Remaining work

Task 1 starts with the DVC pipeline. No evaluation, model registration,
prediction endpoints, container deployment, or monitoring is claimed complete
by this setup check.
