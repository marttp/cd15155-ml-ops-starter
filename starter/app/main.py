"""Financial headline sentiment inference service."""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field, field_validator

if __package__:
    from .utils import load_classifier
else:
    from utils import load_classifier

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("finbert-api")
classifiers = {}


def log(level: str, message: str, **kwargs) -> None:
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(),
             "level": level.upper(), "message": message, **kwargs}
    logger.log(getattr(logging, level.upper()), json.dumps(entry))


PREDICTION_REQUESTS = Counter("finbert_prediction_requests_total", "Successful predictions", ["sentiment"])
PREDICTION_LATENCY = Histogram("finbert_prediction_latency_ms", "Inference call completion latency in milliseconds",
                             buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000])
PREDICTION_ERRORS = Counter("finbert_prediction_errors_total", "Prediction failures")


class PredictRequest(BaseModel):
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def nonempty_text(cls, value):
        if not value.strip():
            raise ValueError("Text must contain non-whitespace characters")
        return value


class PredictBatchRequest(BaseModel):
    texts: list[str] = Field(min_length=1)

    @field_validator("texts")
    @classmethod
    def nonempty_items(cls, values):
        if any(not value.strip() for value in values):
            raise ValueError("Every text must contain non-whitespace characters")
        return values


class PredictionResult(BaseModel):
    text: str
    sentiment: str
    confidence: float = Field(ge=0, le=1)
    latency_ms: float = Field(ge=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        log("INFO", "Loading model", source=os.getenv("MODEL_SOURCE", "mlflow"))
        classifiers["sentiment"] = load_classifier()
        log("INFO", "Model loaded successfully")
    except Exception as error:
        log("ERROR", "Model loading failed", error=str(error))
    try:
        yield
    finally:
        classifiers.clear()
        log("INFO", "Model unloaded")


app = FastAPI(title="Sentiment Analysis API", lifespan=lifespan)


def run_predictions(texts: list[str]) -> list[PredictionResult]:
    if "sentiment" not in classifiers:
        raise HTTPException(status_code=503, detail="Model not loaded")
    try:
        if any(len(text) > 2000 for text in texts):
            log("WARNING", "Long input will be truncated to the model token limit")
        start = perf_counter()
        results = classifiers["sentiment"](texts, batch_size=32, truncation=True, max_length=512)
        latency_ms = (perf_counter() - start) * 1000
        predictions = [PredictionResult(text=text, sentiment=result["label"],
                                 confidence=result["score"], latency_ms=latency_ms)
                for text, result in zip(texts, results, strict=True)]
        PREDICTION_LATENCY.observe(latency_ms)
        for prediction in predictions:
            PREDICTION_REQUESTS.labels(sentiment=prediction.sentiment).inc()
            log("INFO", "Prediction completed", sentiment=prediction.sentiment,
                confidence=prediction.confidence, latency_ms=prediction.latency_ms)
        return predictions
    except Exception as error:
        PREDICTION_ERRORS.inc()
        log("ERROR", "Prediction failed", error=str(error))
        raise


def run_prediction(text: str) -> PredictionResult:
    return run_predictions([text])[0]


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


@app.get("/health")
def health():
    if "sentiment" not in classifiers:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ok"}


@app.post("/predict", response_model=PredictionResult)
def predict(request: PredictRequest):
    return run_prediction(request.text)


@app.post("/predict/batch", response_model=list[PredictionResult])
def predict_batch(request: PredictBatchRequest):
    return run_predictions(request.texts)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("API_HOST", "0.0.0.0"), port=int(os.getenv("API_PORT", "8000")))
