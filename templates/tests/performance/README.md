# Performance template

Locust is the default performance backend.

Default acceptance thresholds are configured in `quality.toml`:

```toml
[performance]
backend = "locust"
users = 50
spawn_rate = 5
duration = "1m"
p95_ms = 500
p99_ms = 1000
failure_rate = 0.01
```

Available threshold fields:
- `p50_ms`: maximum median response time
- `p95_ms`: maximum 95th percentile
- `p99_ms`: maximum 99th percentile
- `failure_rate`: maximum failed-request ratio, e.g. `0.01` = 1%
- `min_rps`: minimum aggregate requests per second

The harness converts Locust CSV output into `performance.json` and
`performance-junit.xml` and fails CI when a configured threshold is violated.

Treat these defaults as starter values, not universal SLOs. Replace them with
product-specific requirements.
