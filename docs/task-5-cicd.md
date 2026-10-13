# Task 5 CI/CD evidence

The implementation follows modules 15, 17, and 19 and the final project rubric.
The executable workflow is at repository-root .github/workflows/ci-cd.yml;
the starter's nested placeholder was removed because GitHub does not execute it.

Local verification on 13 October 2026: 27 tests passed; Ruff's standard error
and undefined-name checks passed. Real Deepchecks over 1,629 reference headlines
and 444 production posts measured Sentiment property drift 0.29129544 and
prediction drift 0.23166959, below the unchanged 0.5 and 0.6 thresholds.
Boundary and excessive-drift tests verify fail-closed behavior.

The pipeline runs lint, then parallel real-model tests and Deepchecks, followed
by build and deploy on pushes. Pull requests run validation without AWS writes.
Build pushes the commit SHA and latest tags to ECR. Deploy downloads the current
ECS definition, renders the SHA-tagged image, uses amazon-ecs-deploy-task-definition,
waits for service stability, and verifies public health and predictions.
Evidence JSON files are uploaded as workflow artifacts.

AWS bootstrap uses one 0.5-vCPU, 2-GiB Fargate task, the existing default VPC,
a public subnet, security group finbert-sg with port 80, ECR finbert-api,
cluster finbert-cluster, task family finbert-api, and service finbert-api-service.
A same-task nginx proxy exposes port 80 while the API stays on port 8000.
No NAT gateway or load balancer is provisioned. Log retention is seven days;
ECR retains three images. These limits reduce ongoing lab costs but do not
measure or guarantee the remaining Udacity credit balance.

Temporary AWS credentials stay in GitHub secrets. The execution role can be
supplied through the ECS_EXECUTION_ROLE_ARN repository variable; otherwise the
bootstrap reuses a compatible existing role or creates a task execution role.
AWS execution passed on 13 October 2026:
https://github.com/marttp/cd15155-ml-ops-starter/actions/runs/38377033671

Linux tests, Deepchecks, ECR SHA/latest uploads, ECS provisioning, task rendering,
service stability, and public endpoint verification all passed. Task revision 2
returned valid health, single, and batch predictions. Evidence is committed in
`evidence/task-5-deployment.json`, `evidence/task-5-deepchecks.json`, and
`evidence/task-5-aws-resources.json`; account identifiers are redacted in the
committed copies. A real CLI rejection returned nonzero status with an excessive
drift score. The original threshold was restored.

The MLflow-backed API path also passed all 15 API tests. This complements CI's
Hugging Face path. The production endpoint uses the Fargate task's public IP,
which can change on deployment. The one-task deployment permits brief downtime
while replacing a task to limit concurrent resource usage.
