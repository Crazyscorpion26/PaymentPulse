# Runbook: High API 5xx error rate

**Trigger:** `HighApiErrorRate` (>5% 5xx ratio for 2 minutes).

1. Confirm alert time window and whether the API target is healthy in Prometheus.
2. Open Grafana's PaymentPulse SRE Overview dashboard; correlate request rate, p95 latency and 5xx responses.
3. In Explore, query Loki with `{container="paymentpulse-api"}` and inspect `severity="error"`, `remittance_callback_failed` and recent deployment timestamps.
4. Reproduce only with synthetic test transactions; do not use production credentials or real payment data.
5. Check recent application changes, dependency/connectivity symptoms and resource saturation.
6. Mitigate by rolling back the latest known-bad demo deployment or restarting the local service if appropriate.
7. Verify 5xx rate returns to baseline and health endpoint responds.
8. Record timeline, impact, contributing factors and follow-up actions.

**Escalate:** If the service remains unavailable after initial checks, preserve logs and escalate to the application/platform owner. Never change real payment records.
