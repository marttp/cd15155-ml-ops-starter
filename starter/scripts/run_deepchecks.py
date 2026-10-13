"""Fail CI when NLP sentiment properties or FinBERT predictions drift excessively."""
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import yaml
from app.utils import load_classifier
from deepchecks.nlp import TextData
from deepchecks.nlp.checks import PredictionDrift, PropertyDrift
from dotenv import load_dotenv

load_dotenv()


def load_params():
    with open("params.yaml") as f:
        return yaml.safe_load(f)["deepchecks"]


def run_predictions(classifier, texts):
    return [result["label"] for result in classifier(texts, batch_size=32, truncation=True, max_length=512)]


def assess_scores(property_score, prediction_score, params):
    scores = {"property_drift": float(property_score), "prediction_drift": float(prediction_score)}
    for name, value in scores.items():
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Invalid {name} score: {value}")
        if value > params[f"{name}_threshold"]:
            raise ValueError(f"{name} score {value:.6f} exceeds threshold {params[f'{name}_threshold']}")
    return scores


def main():
    params = load_params()
    test_texts = pd.read_csv("data/test.csv")["text"].tolist()
    stream_texts = pd.read_csv("data/stream.csv")["text"].tolist()
    reference = TextData(raw_text=test_texts, task_type="text_classification", name="test-reference")
    current = TextData(raw_text=stream_texts, task_type="text_classification", name="production-stream")
    for dataset in (reference, current):
        dataset.calculate_builtin_properties(include_properties=["Sentiment"],
            ignore_non_english_samples_for_english_properties=False, use_onnx_models=False,
            models_storage=os.getenv("DEEPCHECKS_MODEL_DIR", ".cache/deepchecks"), cache_models=True)
        if not dataset.properties["Sentiment"].notna().all():
            raise ValueError("Sentiment properties contain missing values")
    property_result = PropertyDrift(properties=["Sentiment"]).run(reference, current, with_display=False)
    classifier = load_classifier()
    prediction_result = PredictionDrift(drift_mode="prediction").run(
        reference, current, with_display=False,
        train_predictions=run_predictions(classifier, test_texts),
        test_predictions=run_predictions(classifier, stream_texts),
        model_classes=["negative", "neutral", "positive"],
    )
    property_score = property_result.value["Sentiment"]["Drift score"]
    prediction_score = prediction_result.value["Drift score"]
    scores = {"property_drift": float(property_score), "prediction_drift": float(prediction_score)}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/deepchecks.json").write_text(json.dumps({**scores, "thresholds": params,
        "reference_samples": len(test_texts), "current_samples": len(stream_texts)}, indent=2))
    print(json.dumps(scores))
    assess_scores(property_score, prediction_score, params)
    print("Deepchecks quality gate passed")


if __name__ == "__main__":
    main()
