"""
Model loading utilities.
"""

import json
import os

from huggingface_hub import hf_hub_download
from transformers import AutoConfig, AutoModelForSequenceClassification, pipeline


def load_huggingface_classifier(model_id: str):
    """Correct the supplied FinBERT label configuration without editing its cache."""
    config_path = hf_hub_download(repo_id=model_id, filename="config.json")
    with open(config_path) as f:
        config_data = json.load(f)
    config_data["id2label"] = {0: "negative", 1: "neutral", 2: "positive"}
    config_data["label2id"] = {"negative": 0, "neutral": 1, "positive": 2}
    model_type = config_data.pop("model_type")
    config = AutoConfig.for_model(model_type, **config_data)
    model = AutoModelForSequenceClassification.from_pretrained(model_id, config=config)
    return pipeline(
        "text-classification",
        model=model,
        tokenizer=model_id,
        device="cpu",
        truncation=True,
        max_length=512,
    )


def load_classifier():
    """
    Load the sentiment classifier.

    Controlled by the MODEL_SOURCE environment variable:
      - "mlflow" (default) — loads from the MLflow Model Registry
      - "huggingface"       — loads directly from HuggingFace Hub (used in CI/prod)
    """
    model_source = os.getenv("MODEL_SOURCE", "mlflow")

    if model_source == "huggingface":
        hf_model_id = os.getenv("HF_MODEL_ID", "baptle/FinBERT_market_based")
        print(f"Loading model from HuggingFace: {hf_model_id}")
        return load_huggingface_classifier(hf_model_id)

    import mlflow.transformers

    model_name = os.getenv("MODEL_NAME", "finbert")
    model_alias = os.getenv("MODEL_STAGE", "production")
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    print(f"Loading model from MLflow: models:/{model_name}@{model_alias}")
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.transformers.load_model(f"models:/{model_name}@{model_alias}")
