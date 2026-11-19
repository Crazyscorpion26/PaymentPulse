# Runbook: High API p95 latency

**Trigger:** `HighApiLatencyP95` (p95 >1 second for 3 minutes).

1. Check p95 latency and request rate in Grafana.
2. Search Loki for `simulated_dependency_outage`, slow requests and errors.
3. Compare normal and `simulate=slow` requests; this scenario intentionally sleeps for 1.5 seconds.
4. Check container CPU/memory and dependency/network health in the chosen runtime.
5. If caused by the synthetic slow path, remove the test scenario; otherwise isolate the slow endpoint and capture a trace/log sample.
6. Confirm p95 falls below threshold for at least 5 minutes.
7. Document detection, diagnosis, mitigation and prevention.
