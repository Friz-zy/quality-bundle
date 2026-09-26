# Testcontainers with nested rootless Podman

Testcontainers requires a Docker-API-compatible runtime. The quality-bundle image starts
`podman system service` on a private Unix socket and exports that socket as `DOCKER_HOST`.

```text
Testcontainers
     |
     | Docker API
     v
$XDG_RUNTIME_DIR/podman/podman.sock
     |
     v
rootless Podman
```

No host Docker socket is required.

## Environment

The image configures:

```bash
DOCKER_HOST=unix:///tmp/podman-run-1000/podman/podman.sock
TESTCONTAINERS_RYUK_DISABLED=true
```

The resource reaper is disabled by default for the constrained nested-rootless profile.
Tests should use context managers/fixtures so containers are explicitly stopped.

## Recommended division

Use Testcontainers for:
- PostgreSQL, MySQL, Redis, Kafka, RabbitMQ and other supported services
- generic short-lived dependency containers
- normal wait/readiness patterns
- project-specific fixtures

Use `PodmanRuntime` for:
- explicit kill/restart/signal tests
- runtime capability probes
- low-level network/container lifecycle operations
- SUT startup performed by the shared harness

This preserves the Testcontainers ecosystem without making the harness dependent on a host daemon.
