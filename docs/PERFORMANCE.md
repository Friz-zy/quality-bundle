# Performance testing with Locust

Locust is the default engine because scenarios are Python, stateful user journeys are easy to model,
and the harness can evaluate its statistics without introducing a second scenario language.

## Suggested scenario classes

- Smoke: 1-5 users, 30-60 seconds, validates that the scenario works.
- Load: expected concurrency/RPS, several minutes, validates normal SLOs.
- Stress: increase beyond expected load to identify degradation behavior.
- Soak: expected load for a long duration to expose leaks and resource accumulation.
- Spike: rapid increase/decrease to test elasticity and queueing behavior.

Do not assume one universal user count. Configure each project/environment.

## Default measured gates

The harness supports:
- maximum p50 latency
- maximum p95 latency
- maximum p99 latency
- maximum failure ratio
- minimum aggregate RPS

Raw Locust CSV remains available for deeper analysis.

## Percentiles

Use p95 as the usual primary tail metric and p99 for rare slow requests. Avoid using averages alone:
a good average can hide a small but important population of very slow responses.

## Dynamic endpoints

Give requests stable Locust names:

```python
self.client.get(f"/v1/tasks/{task_id}", name="GET /v1/tasks/:id")
```

This prevents every resource ID from becoming a separate statistics row.
