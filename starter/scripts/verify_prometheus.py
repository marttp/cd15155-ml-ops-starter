"""Verify real production scraping and save the target/metric evidence."""
import json
import time
from pathlib import Path

import requests


def main():
    url = json.loads(Path("reports/deployment.json").read_text())["url"]
    metrics = requests.get(url + "/metrics", timeout=15)
    metrics.raise_for_status()
    assert "finbert_prediction_requests_total" in metrics.text
    for attempt in range(20):
        try:
            response = requests.get(url + "/prometheus/api/v1/targets", timeout=15)
            response.raise_for_status()
            targets = response.json()["data"]["activeTargets"]
        except requests.RequestException:
            time.sleep(2)
            continue
        if any(target["labels"].get("job") == "finbert-api" and target["health"] == "up" for target in targets):
            break
        time.sleep(2)
    else:
        raise ValueError("Production Prometheus did not report a healthy API target")
    query = requests.get(url + "/prometheus/api/v1/query", params={"query": 'up{job="finbert-api"}'}, timeout=15)
    query.raise_for_status()
    assert query.json()["data"]["result"][0]["value"][1] == "1"
    Path("reports/prometheus.json").write_text(json.dumps({"api_url": url, "targets": targets,
        "up_query": query.json()}, indent=2))
    print("Production Prometheus target is up")


if __name__ == "__main__":
    main()
