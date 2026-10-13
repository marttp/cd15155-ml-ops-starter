"""Verify exported metrics, structured logs, and complete monitoring windows."""
import json
import logging
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from prometheus_client.parser import text_string_to_metric_families

from app.main import classifiers
from monitoring import stream


def samples(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    return [sample for family in text_string_to_metric_families(response.text) for sample in family.samples]


def metric_total(client, name):
    return sum(sample.value for sample in samples(client) if sample.name == name)


@pytest.mark.parametrize("texts", [["Stocks closed flat."], ["Stocks closed flat.", "The company reported record profits."]])
def test_metrics_count_predictions_and_latency(client, texts):
    before = metric_total(client, "finbert_prediction_requests_total")
    latency_before = metric_total(client, "finbert_prediction_latency_ms_count")
    sum_before = metric_total(client, "finbert_prediction_latency_ms_sum")
    response = client.post("/predict/batch", json={"texts": texts})
    assert response.status_code == 200
    assert metric_total(client, "finbert_prediction_requests_total") == before + len(texts)
    assert metric_total(client, "finbert_prediction_latency_ms_count") == latency_before + 1
    assert metric_total(client, "finbert_prediction_latency_ms_sum") - sum_before == pytest.approx(response.json()[0]["latency_ms"])


@pytest.mark.parametrize("path,payload", [
    ("/predict", {"text": "Stocks closed flat."}),
    ("/predict/batch", {"texts": ["Stocks closed flat.", "Record profits."]}),
])
def test_unloaded_model_does_not_count_as_prediction_failure(client, monkeypatch, path, payload):
    errors_before = metric_total(client, "finbert_prediction_errors_total")
    latency_before = metric_total(client, "finbert_prediction_latency_ms_count")
    requests_before = metric_total(client, "finbert_prediction_requests_total")
    monkeypatch.delitem(classifiers, "sentiment")
    assert client.post(path, json=payload).status_code == 503
    assert metric_total(client, "finbert_prediction_errors_total") == errors_before
    assert metric_total(client, "finbert_prediction_latency_ms_count") == latency_before
    assert metric_total(client, "finbert_prediction_requests_total") == requests_before


def test_prediction_exception_increments_error_metric(client, monkeypatch):
    before = metric_total(client, "finbert_prediction_errors_total")
    def broken(*args, **kwargs):
        raise RuntimeError("Controlled inference failure")
    monkeypatch.setitem(classifiers, "sentiment", broken)
    with pytest.raises(RuntimeError, match="Controlled inference failure"):
        client.post("/predict", json={"text": "Stocks closed flat."})
    assert metric_total(client, "finbert_prediction_errors_total") == before + 1


def test_prediction_logs_are_structured(client, caplog):
    with caplog.at_level(logging.INFO, logger="finbert-api"):
        assert client.post("/predict", json={"text": "Stocks closed flat."}).status_code == 200
    entries = [json.loads(record.message) for record in caplog.records if record.name == "finbert-api"]
    prediction = next(entry for entry in entries if entry["message"] == "Prediction completed")
    assert {"timestamp", "level", "message", "sentiment", "confidence", "latency_ms"} <= prediction.keys()


def test_window_metrics_and_step(monkeypatch):
    log_metrics = Mock()
    monkeypatch.setattr(stream.mlflow, "log_metrics", log_metrics)
    result = stream.log_window([
        {"sentiment": "positive", "confidence": 0.8, "latency_ms": 10},
        {"sentiment": "negative", "confidence": 0.6, "latency_ms": 30},
    ], 3)
    assert result == {"pct_positive": 50, "pct_negative": 50, "pct_neutral": 0,
                      "avg_confidence": 0.7, "avg_latency_ms": 20}
    log_metrics.assert_called_once_with(result, step=3)


def test_partial_final_window_is_logged(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/stream.csv").write_text("text\nfirst\nsecond\nthird\n")
    @contextmanager
    def start_run(**kwargs):
        yield SimpleNamespace(info=SimpleNamespace(run_id="monitoring-test"))
    monkeypatch.setattr(stream.mlflow, "start_run", start_run)
    for name in ("set_tracking_uri", "set_experiment", "log_params", "log_metrics", "log_artifact"):
        monkeypatch.setattr(stream.mlflow, name, Mock())
    monkeypatch.setattr(stream, "predict", lambda text: {"sentiment": "neutral", "confidence": 0.9, "latency_ms": 10})
    monkeypatch.setattr(stream, "WINDOW_SIZE", 2)
    monkeypatch.setattr(stream, "SLEEP_MS", 0)
    monkeypatch.setenv("MONITORING_LIMIT", "0")
    stream.main()
    report = json.loads((tmp_path / "reports/monitoring.json").read_text())
    assert report["predictions"] == 3
    assert [window["samples"] for window in report["windows"]] == [2, 1]
    assert [window["step"] for window in report["windows"]] == [0, 1]
