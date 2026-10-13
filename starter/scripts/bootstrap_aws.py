"""Provision the rubric's small ECS deployment using the course's default-VPC pattern."""
import argparse
import json
import os
from pathlib import Path

import boto3


CLUSTER = "finbert-cluster"
SERVICE = "finbert-api-service"
REPOSITORY = "finbert-api"
LOG_GROUP = "/ecs/finbert-api"


def execution_role(session, account):
    if os.getenv("ECS_EXECUTION_ROLE_ARN"):
        return os.environ["ECS_EXECUTION_ROLE_ARN"]
    iam = session.client("iam")
    for name in ("ecsTaskExecutionRole", "LabRole", "finbert-task-execution"):
        try:
            role = iam.get_role(RoleName=name)["Role"]
            trust = json.dumps(role["AssumeRolePolicyDocument"])
            if "ecs-tasks.amazonaws.com" in trust:
                return role["Arn"]
        except iam.exceptions.NoSuchEntityException:
            continue
    role = iam.create_role(RoleName="finbert-task-execution", AssumeRolePolicyDocument=json.dumps({
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow",
        "Principal": {"Service": "ecs-tasks.amazonaws.com"}, "Action": "sts:AssumeRole"}]}))["Role"]
    iam.attach_role_policy(RoleName=role["RoleName"],
        PolicyArn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy")
    return role["Arn"]


def task_definition(image, role_arn, region):
    logging = {"logDriver": "awslogs", "options": {
        "awslogs-group": LOG_GROUP, "awslogs-region": region, "awslogs-stream-prefix": "ecs"}}
    proxy_config = "server { listen 80; location / { proxy_pass http://127.0.0.1:8000; proxy_read_timeout 120s; } }"
    return {
        "family": REPOSITORY, "networkMode": "awsvpc", "requiresCompatibilities": ["FARGATE"],
        "cpu": "512", "memory": "2048", "executionRoleArn": role_arn,
        "runtimePlatform": {"cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX"},
        "containerDefinitions": [
            {"name": REPOSITORY, "image": image, "essential": True,
             "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
             "environment": [{"name": "MODEL_SOURCE", "value": "huggingface"},
                             {"name": "HF_HUB_OFFLINE", "value": "1"}],
             "healthCheck": {"command": ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4)\""],
                             "interval": 15, "timeout": 5, "retries": 3, "startPeriod": 90},
             "logConfiguration": logging},
            {"name": "http-proxy", "image": "public.ecr.aws/docker/library/nginx:1.27-alpine", "essential": True,
             "portMappings": [{"containerPort": 80, "protocol": "tcp"}],
             "dependsOn": [{"containerName": REPOSITORY, "condition": "HEALTHY"}],
             "entryPoint": ["/bin/sh", "-c"],
             "command": [f"printf '%s' '{proxy_config}' > /etc/nginx/conf.d/default.conf; exec nginx -g 'daemon off;'"],
             "logConfiguration": logging},
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image")
    args = parser.parse_args()
    session = boto3.Session(region_name=os.environ["AWS_REGION"])
    account = session.client("sts").get_caller_identity()["Account"]
    ecr = session.client("ecr")
    try:
        ecr.describe_repositories(repositoryNames=[REPOSITORY])
    except ecr.exceptions.RepositoryNotFoundException:
        ecr.create_repository(repositoryName=REPOSITORY)
    ecr.put_lifecycle_policy(repositoryName=REPOSITORY, lifecyclePolicyText=json.dumps({"rules": [{
        "rulePriority": 1, "description": "Keep three recent images for the lab budget",
        "selection": {"tagStatus": "any", "countType": "imageCountMoreThan", "countNumber": 3},
        "action": {"type": "expire"}}]}))
    if not args.image:
        print("ECR repository ready")
        return
    ec2 = session.client("ec2")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise ValueError("The course deployment requires an existing default VPC")
    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "default-for-az", "Values": ["true"]}])["Subnets"]
    if not subnets:
        raise ValueError("No default public subnet was found")
    groups = ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "group-name", "Values": ["finbert-sg"]}])["SecurityGroups"]
    if groups:
        group_id = groups[0]["GroupId"]
    else:
        group_id = ec2.create_security_group(GroupName="finbert-sg", VpcId=vpc_id,
            Description="Financial sentiment HTTP service")["GroupId"]
        ec2.authorize_security_group_ingress(GroupId=group_id, IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    logs = session.client("logs")
    try:
        logs.create_log_group(logGroupName=LOG_GROUP)
    except logs.exceptions.ResourceAlreadyExistsException:
        pass
    logs.put_retention_policy(logGroupName=LOG_GROUP, retentionInDays=7)
    role_arn = execution_role(session, account)
    ecs = session.client("ecs")
    clusters = ecs.describe_clusters(clusters=[CLUSTER])["clusters"]
    if not clusters or clusters[0]["status"] != "ACTIVE":
        ecs.create_cluster(clusterName=CLUSTER)
    services = ecs.describe_services(cluster=CLUSTER, services=[SERVICE])["services"]
    if not services or services[0]["status"] != "ACTIVE":
        definition = task_definition(args.image, role_arn, session.region_name)
        task_arn = ecs.register_task_definition(**definition)["taskDefinition"]["taskDefinitionArn"]
        ecs.create_service(cluster=CLUSTER, serviceName=SERVICE, taskDefinition=task_arn,
            desiredCount=1, launchType="FARGATE",
            deploymentConfiguration={"minimumHealthyPercent": 0, "maximumPercent": 100,
                "deploymentCircuitBreaker": {"enable": True, "rollback": True}},
            networkConfiguration={"awsvpcConfiguration": {"subnets": [subnets[0]["SubnetId"]],
                "securityGroups": [group_id], "assignPublicIp": "ENABLED"}})
    Path("reports").mkdir(exist_ok=True)
    Path("reports/aws-resources.json").write_text(json.dumps({"region": session.region_name,
        "cluster": CLUSTER, "service": SERVICE, "security_group": group_id,
        "cpu": 512, "memory_mb": 2048, "desired_tasks": 1}, indent=2))
    print("ECS deployment resources ready")


if __name__ == "__main__":
    main()
