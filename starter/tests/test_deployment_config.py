"""Keep public networking and the single-task resource contract explicit."""
from scripts.bootstrap_aws import task_definition


def test_small_task_keeps_api_internal_and_proxy_public():
    task = task_definition("registry/finbert:sha", "execution-role", "us-east-1")
    assert task["cpu"] == "512" and task["memory"] == "2048"
    api, proxy = task["containerDefinitions"]
    assert api["image"] == "registry/finbert:sha"
    assert api["portMappings"][0]["containerPort"] == 8000
    assert proxy["portMappings"][0]["containerPort"] == 80
    assert proxy["dependsOn"] == [{"containerName": "finbert-api", "condition": "HEALTHY"}]
