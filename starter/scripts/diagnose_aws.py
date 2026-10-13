"""Read ECS service events and task stop reasons without changing AWS resources."""
import json
import os

import boto3


def main():
    session = boto3.Session(region_name=os.environ["AWS_REGION"])
    ecs = session.client("ecs")
    service = ecs.describe_services(cluster="finbert-cluster", services=["finbert-api-service"])["services"][0]
    print(json.dumps({"desired": service["desiredCount"], "running": service["runningCount"],
        "pending": service["pendingCount"], "deployments": service["deployments"],
        "events": service["events"][:8]}, default=str, indent=2))
    for state in ("RUNNING", "STOPPED"):
        arns = [arn for page in ecs.get_paginator("list_tasks").paginate(cluster="finbert-cluster",
            serviceName="finbert-api-service", desiredStatus=state) for arn in page["taskArns"]]
        if arns:
            tasks = ecs.describe_tasks(cluster="finbert-cluster", tasks=arns[:100])["tasks"]
            for task in tasks[:8]:
                print(json.dumps({"state": state, "last_status": task["lastStatus"],
                    "stopped_reason": task.get("stoppedReason"), "health": task.get("healthStatus"),
                    "containers": [{key: container.get(key) for key in ("name", "lastStatus", "exitCode", "reason", "healthStatus")}
                        for container in task["containers"]]}, indent=2))


if __name__ == "__main__":
    main()
