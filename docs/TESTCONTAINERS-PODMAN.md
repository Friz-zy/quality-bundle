# Testcontainers with nested rootless Podman

Testcontainers requires a Docker-API-compatible runtime. The quality-bundle image starts
`podman system service` on a private Unix socket and exports that socket as `DOCKER_HOST`.
The service is started only for commands that can use it (`quality test`, `quality run`,
suite commands); diagnostics such as `quality doctor`, `quality list`, and `quality plan`
run without it. See `PODMAN-RUNNER.md` for the lifecycle details.

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

## Alternative: Docker-out-of-Docker mode

The image also supports running Testcontainers against a host Docker engine
instead of nested rootless Podman. Mount the host socket and disable the
internal Podman API service:

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e DOCKER_HOST=unix:///var/run/docker.sock \
  -e E2E_PODMAN_SERVICE=0 \
  quality-bundle quality test
```

`E2E_PODMAN_SERVICE=0` is required in this mode: without it the entrypoint
would start `podman system service` on the mounted socket path. Containers
become siblings of the runner on the host engine, so host-side images,
networks, and volumes are shared.

This mode covers Testcontainers-based tests only. `PodmanRuntime` invokes the
Podman CLI directly and ignores `DOCKER_HOST`, so DooD does not exercise it.
The two modes are tested independently in CI (jobs `smoke-dood` and
`smoke-nested-podman` in `.github/workflows/toolkit.yml`, smoke files under
`smoke/`).

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
