# PaymentPulse — 14-day build plan

The initial repository scaffold is created. Use this plan to turn it into a polished, demonstrable SRE portfolio.

| Day | Milestone | Deliverable | Status |
|---|---|---|---|
| 1 | Service foundation | FastAPI synthetic payment API, transaction IDs, lifecycle events, failure scenarios | Implemented; unit tests pass |
| 2 | Containerization | Non-root Docker image and health check | Implemented; Docker runtime not available in build environment |
| 3 | Metrics | Prometheus request, transaction, latency and in-flight metrics | Implemented; endpoint covered by tests |
| 4 | Log aggregation | Docker log discovery with Promtail and Loki | Config authored; runtime validation pending |
| 5 | Dashboards | Grafana data sources and SRE overview dashboard | Provisioning authored; runtime validation pending |
| 6 | Alerting | API-down, high-error-rate and high-p95-latency rules | Rules authored; alert firing tests pending |
| 7 | Incident response | High-error-rate and high-latency runbooks | Implemented |
| 8 | Reliability testing | Load, failure injection and alert validation | Next implementation milestone |
| 9 | CI | GitHub Actions tests and image build | Workflow authored; remote CI run pending |
| 10 | AWS image publishing | ECR build/push workflow | Script scaffold included |
| 11 | AWS infrastructure | ECS Fargate, ALB, security groups, IAM execution role, CloudWatch Logs | Terraform scaffold authored; provider validation pending |
| 12 | Cloud verification | Deploy, inspect service events/logs, test endpoint | Requires user's AWS sandbox and approval |
| 13 | Security and cost review | IAM scope, ingress restrictions, budget guardrails, teardown verification | Documentation included; account-specific review pending |
| 14 | Portfolio handoff | README, architecture, evidence, demo script and interview story | README and interview story drafted; screenshots/evidence pending |

## Evidence to collect before claiming completion

- Test output from `pytest -q`.
- `docker compose ps` showing all local services healthy.
- Screenshot of Grafana dashboard with generated request traffic.
- Loki query result for a known synthetic transaction ID.
- Prometheus alert state during a controlled failure scenario.
- Terraform `fmt`, `validate` and reviewed `plan` output.
- If AWS is deployed: ECS service health, ALB health check and CloudWatch log evidence, plus teardown confirmation.

Do not claim a milestone is tested or deployed until the corresponding evidence exists.
