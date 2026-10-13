"""
Evaluate sentiment model on the test set and register it
in the MLflow Model Registry.

Run:
    python scripts/evaluate.py
"""

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
import mlflow
import mlflow.transformers
from app.utils import load_huggingface_classifier


load_dotenv()


def load_test_data(test_path: str) -> tuple[list[str], list[str]]:
    df = pd.read_csv(test_path)
    return df["text"].tolist(), df["label"].tolist()


def build_classifier(model_id: str):
    print(f"Loading {model_id}...")
    return load_huggingface_classifier(model_id)


def run_inference(classifier, texts: list[str]) -> list[str]:
    print(f"Running inference on {len(texts)} samples...")
    results = classifier(texts, batch_size=32)
    return [r["label"] for r in results]


def compute_metrics(y_true: list[str], y_pred: list[str]) -> dict:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted"),
        "precision_weighted": precision_score(y_true, y_pred, average="weighted"),
        "recall_weighted": recall_score(y_true, y_pred, average="weighted"),
    }


def main():
    model_id = os.getenv("HF_MODEL_ID", "baptle/FinBERT_market_based")
    test_path = os.path.join("data", "test.csv")

    texts, y_true = load_test_data(test_path)
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001"))
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_NAME", "finbert-evaluation"))
    model_name = os.getenv("MODEL_NAME", "finbert")
    with mlflow.start_run(tags={"task": "evaluation", "model_name": model_name}) as run:
        classifier = build_classifier(model_id)
        mlflow.log_params({
            "model_id": model_id,
            "model_revision": classifier.model.config._commit_hash,
            "test_samples": len(texts),
            "test_sha256": hashlib.sha256(Path(test_path).read_bytes()).hexdigest(),
            "batch_size": 32,
            "max_length": 512,
        })
        y_pred = run_inference(classifier, texts)
        metrics = compute_metrics(y_true, y_pred)
        mlflow.log_metrics(metrics)
        report = classification_report(y_true, y_pred, zero_division=0)
        mlflow.log_text(report, "classification-report.txt")
        mlflow.log_artifact("dvc.lock", artifact_path="provenance")
        mlflow.log_artifact("params.yaml", artifact_path="provenance")
        info = mlflow.transformers.log_model(
            transformers_model=classifier,
            artifact_path="model",
            registered_model_name=model_name,
            task="text-classification",
            input_example=texts[:2],
            pip_requirements=mlflow.transformers.get_default_pip_requirements(classifier.model),
        )
        print(report)
        print("Metrics:", metrics)
        print("Run:", run.info.run_id)
        print("Registered version:", info.registered_model_version)


if __name__ == "__main__":
    main()
