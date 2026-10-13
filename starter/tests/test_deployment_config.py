"""Keep public networking and the single-task resource contract explicit."""
from scripts.bootstrap_aws import task_definition


def test_small_task_keeps_api_internal_and_proxy_public():
    task = task_definition("registry/finbert:sha", "execution-role", "us-east-1")
    assert task["cpu"] == "512" and task["memory"] == "2048"
    containers = {container["name"]: container for container in task["containerDefinitions"]}
    api, proxy = containers["finbert-api"], containers["http-proxy"]
    assert api["image"] == "registry/finbert:sha"
    assert api["portMappings"][0]["containerPort"] == 8000
    assert proxy["portMappings"][0]["containerPort"] == 80
    assert proxy["dependsOn"] == [{"containerName": "finbert-api", "condition": "HEALTHY"}]


def test_prometheus_has_completed_config_dependency():
    task = task_definition("registry/finbert:sha", "execution-role", "us-east-1")
    prometheus = next(container for container in task["containerDefinitions"] if container["name"] == "prometheus")
    assert prometheus["dependsOn"] == [{"containerName": "monitoring-config", "condition": "SUCCESS"}]
    assert prometheus["mountPoints"][0]["readOnly"] is True
