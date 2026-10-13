"""Promote the latest evaluated model only when weighted F1 meets the threshold."""

import math
import os

import yaml
from dotenv import load_dotenv
from mlflow.tracking import MlflowClient

load_dotenv()


def load_params() -> dict:
    with open("params.yaml") as f:
        return yaml.safe_load(f)["promote"]


def get_latest_f1(client: MlflowClient, experiment_name: str) -> tuple[str, float]:
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise ValueError(f"Evaluation experiment does not exist: {experiment_name}")
    model_name = os.getenv("MODEL_NAME", "finbert")
    runs = client.search_runs(
        [experiment.experiment_id],
        filter_string=f"attributes.status = 'FINISHED' AND tags.task = 'evaluation' AND tags.model_name = '{model_name}'",
        order_by=["attributes.start_time DESC"], max_results=1,
    )
    if not runs or "f1_weighted" not in runs[0].data.metrics:
        raise ValueError("No completed evaluation with weighted F1 was found")
    score = float(runs[0].data.metrics["f1_weighted"])
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError("Evaluation F1 is invalid")
    return runs[0].info.run_id, score


def promote(client: MlflowClient, model_name: str, expected_run_id: str) -> str:
    versions = client.search_model_versions(f"name = '{model_name}'")
    if not versions:
        raise ValueError(f"No registered versions for {model_name}")
    latest = max(versions, key=lambda version: int(version.version))
    if latest.run_id != expected_run_id or latest.status != "READY":
        raise ValueError("Latest registered model does not match the evaluated run or is not ready")
    client.set_registered_model_alias(model_name, "production", latest.version)
    print(f"Promoted {model_name} version {latest.version} to production")
    return latest.version


def main():
    client = MlflowClient(tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001"))
    run_id, score = get_latest_f1(client, os.getenv("MLFLOW_EXPERIMENT_NAME", "finbert-evaluation"))
    threshold = float(load_params()["f1_threshold"])
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Promotion threshold must be between zero and one")
    if score >= threshold:
        promote(client, os.getenv("MODEL_NAME", "finbert"), run_id)
    else:
        print(f"Model not promoted: weighted F1 {score:.4f} is below threshold {threshold:.4f}")


if __name__ == "__main__":
    main()
