FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    HF_MODEL_ID=baptle/FinBERT_market_based \
    HF_MODEL_REVISION=ec5ffa074fc00da4de8b28554a57aa1debf92508 \
    MODEL_SOURCE=huggingface \
    MODEL_NUM_THREADS=2 \
    API_HOST=0.0.0.0 \
    API_PORT=8000

WORKDIR /service
COPY requirements-service.txt ./
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-service.txt
COPY app/ ./app/
COPY scripts/smoke_test.py ./scripts/smoke_test.py
RUN python scripts/smoke_test.py \
    && useradd --uid 10001 --create-home service \
    && mkdir -p /service/mlruns /service/mlartifacts \
    && chown -R service:service /service /opt/huggingface
USER service
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["python", "app/main.py"]
