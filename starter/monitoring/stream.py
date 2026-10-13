"""Send production headlines to the API and log each observation window in MLflow."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("API_HOST", "localhost")
if host == "0.0.0.0":
    host = "localhost"
API_URL = os.getenv("API_BASE_URL", f"http://{host}:{os.getenv('API_PORT', '8000')}")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_MONITORING_EXPERIMENT_NAME", "finbert-production-monitoring")
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "50"))
SLEEP_MS = int(os.getenv("SLEEP_MS", "100"))


def predict(text: str) -> dict:
    response = requests.post(API_URL + "/predict", json={"text": text}, timeout=60)
    response.raise_for_status()
    return response.json()


def log_window(window: list[dict], window_idx: int) -> dict:
    if not window or any(item["sentiment"] not in {"positive", "negative", "neutral"} for item in window):
        raise ValueError("Monitoring window must contain valid sentiment predictions")
    metrics = {f"pct_{sentiment}": 100 * sum(item["sentiment"] == sentiment for item in window) / len(window)
               for sentiment in ("positive", "negative", "neutral")}
    metrics.update(avg_confidence=mean(item["confidence"] for item in window),
                   avg_latency_ms=mean(item["latency_ms"] for item in window))
    mlflow.log_metrics(metrics, step=window_idx)
    return metrics


def main():
    if WINDOW_SIZE <= 0 or SLEEP_MS < 0:
        raise ValueError("Window size must be positive and delay nonnegative")
    path = Path("data/stream.csv")
    texts = pd.read_csv(path)["text"].tolist()
    limit = int(os.getenv("MONITORING_LIMIT", "0"))
    if limit > 0:
        texts = texts[:limit]
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    windows = []
    with mlflow.start_run(tags={"task": "monitoring"}) as run:
        mlflow.log_params({"api_url": API_URL, "window_size": WINDOW_SIZE,
            "headlines": len(texts), "stream_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        window = []
        for text in texts:
            window.append(predict(text))
            if len(window) == WINDOW_SIZE:
                windows.append({"step": len(windows), "samples": len(window),
                    "metrics": log_window(window, len(windows))})
                window = []
            time.sleep(SLEEP_MS / 1000)
        if window:
            windows.append({"step": len(windows), "samples": len(window),
                "metrics": log_window(window, len(windows))})
        report = {"run_id": run.info.run_id, "experiment": MLFLOW_EXPERIMENT_NAME,
            "api_url": API_URL, "predictions": len(texts), "windows": windows}
        Path("reports").mkdir(exist_ok=True)
        Path("reports/monitoring.json").write_text(json.dumps(report, indent=2))
        mlflow.log_artifact("reports/monitoring.json")
        print(f"Logged {len(texts)} predictions in {len(windows)} windows. Run: {run.info.run_id}")


if __name__ == "__main__":
    main()
