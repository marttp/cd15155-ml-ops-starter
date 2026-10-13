# Building a Real-Time Financial News Sentiment Service 

This is marttp's coursework implementation fork of the Udacity starter.
All required project criteria have implementation and observed evidence in the
[final rubric audit](docs/rubric-audit.md). Task PRs #1 through #7 cover setup,
DVC, the registry, API, containers, delivery, and production monitoring.

The executable CI/CD workflow is at [.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml).
Application commands run from `starter/`. See [setup evidence](docs/task-0-setup.md)
for Python 3.12 installation and the verified MLflow server configuration.
The inherited license is retained.


Operationalise a pre-trained financial news sentiment classifier by building the full MLOps stack: data versioning, model registry, REST API, containerisation, CI/CD, and production monitoring.

By the end of this project, you will be able to:

- Load and version datasets using DVC

- Evaluate and register a model in MLflow

- Write a prediction API 

- Package and deploy the prediction service using Docker and Docker-compose

- Write a CI/CD pipeline that pushes the image to ECR and deploys the service in AWS

- Collect service metrics using Prometheus

- Add production monitoring using MLflow


## Start the full stack

`stack.sh` is the single entry point, runnable from any directory. Local startup
includes DVC preparation, a persistent MLflow server, evaluation and production
promotion, the registry-backed API, Prometheus, and the complete monitoring stream.
It fails if promotion or service verification fails. Re-running local startup
creates a new evaluation/model version and monitoring run.

On a local machine outside the Udacity workspace, install Python 3.12, Git,
Docker with Compose v2 supporting `--wait`, and the project dependencies once:

```bash
python3.12 -m venv starter/.venv
starter/.venv/bin/python -m pip install -r starter/requirements.txt
./stack.sh local-up
```

Internet access is required for the initial dataset, model and container downloads.
No manual values or AWS credentials are needed for local startup. The script copies
`.env.example` when `.env` is absent and supplies the required local settings.
Ports 5001, 8000 and 9090 must be free; stop any separately started MLflow/API
processes first. Docker persists registry/artifacts in the `finbert-stack_mlflow-state`
volume. MLflow is bound to loopback; the existing API/Prometheus Compose ports
remain published on the host. Model downloads and evaluation can take several minutes.
An interrupted startup leaves containers available for inspection; `local-down`
stops them without deleting the registry volume.

```bash
./stack.sh local-status
./stack.sh local-down
```

The course workspace must not build or run Docker. Use the AWS commands there
instead. They require GitHub CLI (`gh`), an authenticated account with Actions
write access, and these **repository Actions secrets**, entered once in GitHub
Settings → Secrets and variables → Actions:

| Secret | Required input |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | Lab/account credential ID |
| `AWS_SECRET_ACCESS_KEY` | Matching secret credential |
| `AWS_SESSION_TOKEN` | Matching temporary lab session token; renew when expired |
| `AWS_REGION` | `us-east-1` for this project |
| `ECR_REGISTRY` | `<12-digit-account-id>.dkr.ecr.us-east-1.amazonaws.com`, without a repository suffix |

These values already exist in `marttp/cd15155-ml-ops-starter`. Never put credential
values in this file, shell arguments or Git. For another fork, set `GH_REPO=owner/repo`.
The AWS account needs a default VPC/public subnet and permissions for the existing
ECR/ECS/EC2/IAM/CloudWatch bootstrap. The workflow creates project resources;
it does not create an AWS account, credentials or the default network.

```bash
./stack.sh aws-deploy  # Full checks, image build, infrastructure, deployment and monitoring evidence
./stack.sh aws-up      # Resume an already deployed service
./stack.sh aws-down    # Pause its tasks, retaining infrastructure and images
```

Each AWS command waits for its workflow and propagates failure. Avoid concurrent
manual dispatches of the same workflow while it is locating its newly created run.
The deployment run's `reports/deployment.json` artifact contains the current public
URL; its monitoring artifacts contain the MLflow database and window metrics.
AWS hosts the API and Prometheus; evaluation/monitoring MLflow runs execute in
GitHub Actions and are retained as artifacts, rather than a public MLflow server.
Pausing tasks does not remove ECR storage charges. After course review, set the repository variable `AWS_DEPLOY_ENABLED=false`
to keep push-triggered checks running without rebuilding or deploying AWS resources.
Explicit `aws-deploy` remains available when valid credentials and cloud access
are restored. The course cloud resources are no longer assumed active.

## Prerequisites

- Python 3.12
- An AWS account with ECR access
- Git

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/marttp/cd15155-ml-ops-starter.git
cd cd15155-ml-ops-starter
```

> Udacity workspaces have preinstalled dependencies. Local machines use an isolated Python 3.12 environment as described in the setup evidence.

Navigate to the project root 
```bash
cd starter
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in the required values in `.env`.

### 3. Download and patch the model, then validate your setup

```bash
python scripts/smoke_test.py
```

### 4. Launch Mlflow server
```
mkdir -p mlruns
mlflow server --host 127.0.0.1 --port 5001 --backend-store-uri sqlite:///mlruns/mlflow.db --artifacts-destination ./mlartifacts
```

## Project Structure

```
starter/
├── app/
│   ├── main.py              # FastAPI service (Tasks 3 and 6)
│   └── utils.py             # Model loading 
├── data/                    # DVC-tracked datasets
│   ├── raw_stream.csv       # Raw Bluesky financial posts
├── monitoring/
│   └── stream.py            # MLflow monitoring loop (Task 6)
├── scripts/
│   ├── load_data.py         # Downloads financial dataset
│   ├── clean_data.py        # Cleans raw Bluesky stream
│   ├── evaluate.py          # Evaluates model on test set, logs to MLflow (Task 2)
│   ├── promote.py           # Promotes model to production alias if F1 >= threshold (Task 2)
│   ├── run_deepchecks.py    # CI quality gate: property drift + prediction drift (Task 5)
│   └── locustfile.py        # Locust load testing (Task 3)
├── tests/
│   └── test_api.py          # pytest integration tests for the API (Task 3)
├── dvc.yaml                 # DVC pipeline definition (Task 1)
├── params.yaml              # Configuration parameters 
├── docker-compose.yml       # Local API service orchestration (Task 4)
├── Dockerfile               # Production image (Task 4)
├── prometheus.yml           # Prometheus scrape configuration (Task 6)
├── requirements.txt         # All dependencies
└── .env.example             # Environment variable template
```

## Project Tasks

### Task 0 — Project Setup
Configure your environment and confirm the model loads correctly.

### Task 1 — Data Versioning (DVC)
Complete [dvc.yaml](starter/dvc.yaml) to define the data preparation pipeline, run `dvc repro`.

```bash
dvc init
dvc repro
```

**Deliverable:** [dvc.yaml](starter/dvc.yaml), `dvc.lock`

### Task 2 — Model Evaluation and Registration (MLflow)
Complete [scripts/evaluate.py](starter/scripts/evaluate.py) to track the evaluation run with MLflow: set the tracking URI and experiment name, log model parameters and metrics, then log and register the pipeline in the Model Registry. Then complete [scripts/promote.py](starter/scripts/promote.py) to automatically promote the model to Production if it meets the F1 threshold.

```bash
python scripts/evaluate.py
python scripts/promote.py
```

**Deliverable:** [scripts/evaluate.py](starter/scripts/evaluate.py), model registered in MLflow, [scripts/promote.py](starter/scripts/promote.py)

### Task 3 — Prediction API (FastAPI)
Complete [app/main.py](starter/app/main.py) to implement three endpoints:
- `POST /predict` — single headline → `{sentiment, confidence, latency_ms}`
- `POST /predict/batch` — list of headlines → list of above
- `GET /health` — service health status

Write integration tests in [tests/test_api.py](starter/tests/test_api.py). Complete [scripts/locustfile.py](starter/scripts/locustfile.py) to simulate concurrent users hitting the API endpoints under load.

```bash
python app/main.py
pytest tests/
locust -f scripts/locustfile.py --host http://localhost:8000
```

**Deliverable:** [app/main.py](starter/app/main.py), [tests/test_api.py](starter/tests/test_api.py), [scripts/locustfile.py](starter/scripts/locustfile.py)

### Task 4 — Containerisation
Complete [Dockerfile](starter/Dockerfile) and [docker-compose.yml](starter/docker-compose.yml) to run the FastAPI service with proper port mapping, environment variables, volume mounts for MLflow artifacts, and a health check.

> DO NOT run docker-compose or build images in the Udacity workspace. The local runner is for a separate local machine.

**Deliverable:** [Dockerfile](starter/Dockerfile), [docker-compose.yml](starter/docker-compose.yml)

### Task 5 — CI/CD Pipeline
Complete [scripts/run_deepchecks.py](starter/scripts/run_deepchecks.py) to run property drift and prediction drift checks. 
Then complete [.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml) to build a pipeline that on every push to `main`:
1. Runs integration tests
2. Runs Deepchecks model quality checks
3. Builds and pushes the Docker image to Amazon ECR
4. Deploys the service on AWS

```bash
python scripts/run_deepchecks.py
```

#### AWS Setup

Before the pipeline can deploy, create the following AWS resources:

1. **ECR repository** named `finbert-api` to store Docker images
2. **Security group** named `finbert-sg` — inbound HTTP on port 80 from 0.0.0.0/0
2. **ECS cluster** named `finbert-cluster`
3. **ECS task definition** named `finbert-api` configured to run the container
4. **ECS service** named `finbert-api-service` on the cluster

> You can follow this [guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started-fargate.html#first-run-linux-prereqs)

Then add these secrets to your GitHub repository 

```bash
gh secret set AWS_ACCESS_KEY_ID --body "..."
gh secret set AWS_SECRET_ACCESS_KEY --body "..."
gh secret set AWS_REGION --body "us-east-1"
gh secret set ECR_REGISTRY --body ""
```

**Deliverable:** [scripts/run_deepchecks.py](starter/scripts/run_deepchecks.py), [.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml)

### Task 6 — Monitoring
Add structured JSON logging and instrument [app/main.py](starter/app/main.py) with Prometheus counters and histograms. Configure [prometheus.yml](starter/prometheus.yml) to scrape the `/metrics` endpoint. Then complete [monitoring/stream.py](starter/monitoring/stream.py) to simulate production traffic and log aggregated metrics (sentiment distribution, confidence, latency) to MLflow.

```bash
python monitoring/stream.py
```

**Deliverable:** [app/main.py](starter/app/main.py), [prometheus.yml](starter/prometheus.yml), [monitoring/stream.py](starter/monitoring/stream.py)


## Resources

- [FinBERT Market Based](https://huggingface.co/baptle/FinBERT_market_based) — pre-trained financial sentiment model
- [Financial Headlines Market Based](https://huggingface.co/datasets/baptle/financial_headlines_market_based) — financial news headlines dataset
- [HuggingFace Pipeline](https://huggingface.co/docs/transformers/pipeline_tutorial) — model loading and inference pipeline
- [DVC](https://dvc.org/) — data version control
- [MLflow](https://mlflow.org/) — experiment tracking and model registry
- [FastAPI](https://fastapi.tiangolo.com/) — REST API framework
- [Docker](https://www.docker.com/) — containerisation
- [Prometheus](https://prometheus.io/)  — monitoring
- [Deepchecks](https://deepchecks.com/) — model quality checks
- [GitHub Actions](https://docs.github.com/en/actions) — CI/CD
- [Amazon ECR](https://docs.aws.amazon.com/ecr/) — container registry
- [AWS Fargate on ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started-fargate.html) — serverless container deployment

## License

[License](LICENSE.txt)