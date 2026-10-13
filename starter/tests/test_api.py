"""Integration checks exercise real model inference through FastAPI."""
import pytest

from app.main import classifiers

HEADLINES = [
    "The company reported record profits this quarter.",
    "The firm filed for bankruptcy after massive losses.",
    "Stocks closed flat on Friday.",
]


def assert_prediction(result, text):
    assert set(result) == {"text", "sentiment", "confidence", "latency_ms"}
    assert result["text"] == text
    assert result["sentiment"] in {"positive", "negative", "neutral"}
    assert 0 <= result["confidence"] <= 1
    assert result["latency_ms"] >= 0


@pytest.mark.parametrize("text", HEADLINES)
def test_predict_returns_valid_response(client, text):
    response = client.post("/predict", json={"text": text})
    assert response.status_code == 200
    assert_prediction(response.json(), text)


def test_predict_batch(client):
    response = client.post("/predict/batch", json={"texts": HEADLINES})
    assert response.status_code == 200
    assert len(response.json()) == len(HEADLINES)
    for result, text in zip(response.json(), HEADLINES, strict=True):
        assert_prediction(result, text)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("texts", [[], [""], ["   "], [HEADLINES[0], ""]])
def test_predict_batch_empty_list_returns_422(client, texts):
    assert client.post("/predict/batch", json={"texts": texts}).status_code == 422


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_single_returns_422(client, text):
    assert client.post("/predict", json={"text": text}).status_code == 422


@pytest.mark.parametrize("path,payload", [
    ("/health", None), ("/predict", {"text": HEADLINES[0]}),
    ("/predict/batch", {"texts": HEADLINES}),
])
def test_unloaded_model_returns_503(client, monkeypatch, path, payload):
    monkeypatch.delitem(classifiers, "sentiment")
    response = client.get(path) if payload is None else client.post(path, json=payload)
    assert response.status_code == 503


def test_long_input_truncates_safely(client):
    text = "The company reported record profits. " * 400
    response = client.post("/predict", json={"text": text})
    assert response.status_code == 200
    assert_prediction(response.json(), text)
