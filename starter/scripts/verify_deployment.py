"""Verify the current ECS task over its public HTTP endpoint and save evidence."""
import json
import os
from pathlib import Path

import boto3
import requests


def main():
    session = boto3.Session(region_name=os.environ["AWS_REGION"])
    ecs = session.client("ecs")
    tasks = ecs.list_tasks(cluster="finbert-cluster", serviceName="finbert-api-service", desiredStatus="RUNNING")["taskArns"]
    if len(tasks) != 1:
        raise ValueError(f"Expected one running task, found {len(tasks)}")
    task = ecs.describe_tasks(cluster="finbert-cluster", tasks=tasks)["tasks"][0]
    api_container = next(container for container in task["containers"] if container["name"] == "finbert-api")
    expected_image = os.environ["EXPECTED_IMAGE_URI"]
    if api_container["image"] != expected_image:
        raise ValueError("Running ECS image does not match the successful build")
    eni = next(detail["value"] for attachment in task["attachments"]
        for detail in attachment["details"] if detail["name"] == "networkInterfaceId")
    interface = session.client("ec2").describe_network_interfaces(NetworkInterfaceIds=[eni])["NetworkInterfaces"][0]
    url = "http://" + interface["Association"]["PublicIp"]
    response = requests.get(url + "/health", timeout=15)
    response.raise_for_status()
    assert response.json() == {"status": "ok"}
    responses = []
    for endpoint, payload in [("/predict", {"text": "The company reported record profits."}),
        ("/predict/batch", {"texts": ["The company reported record profits.", "Stocks closed flat."]})]:
        response = requests.post(url + endpoint, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        items = result if isinstance(result, list) else [result]
        assert len(items) == (2 if endpoint.endswith("batch") else 1)
        assert all(item["sentiment"] in {"positive", "neutral", "negative"} and
            0 <= item["confidence"] <= 1 and item["latency_ms"] >= 0 for item in items)
        responses.append({"endpoint": endpoint, "response": result})
    evidence = {"url": url, "commit": os.environ.get("GITHUB_SHA"), "task_definition": task["taskDefinitionArn"],
        "images": [{"name": container["name"], "digest": container.get("imageDigest")} for container in task["containers"]],
        "responses": responses}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/deployment.json").write_text(json.dumps(evidence, indent=2))
    print("Live ECS health and predictions verified:", url)


if __name__ == "__main__":
    main()
