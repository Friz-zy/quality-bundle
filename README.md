# quality-bundle

Reusable Git submodule for language-agnostic functional black-box testing.
The toolkit owns runners, pytest fixtures, dependency profiles, CI templates and AI instructions.
The target repository owns all product-specific tests.

## Why one repository
Use one toolkit repository with optional dependency profiles instead of separate repositories.
This keeps the public test API, CI behavior and AI policy versioned together while avoiding
UI/mobile dependencies unless a project needs them.

## Supported layers

| Layer | Default tool | Profile |
|---|---|---|
| CLI | pytest + subprocess | core |
| HTTP API | pytest + httpx | core |
| Runtime/dependencies | Testcontainers | core |
| HTTP scenarios | Hurl CLI | external |
| OpenAPI property/contract | Schemathesis | api |
| BDD/Gherkin | pytest-bdd | bdd |
| Browser UI | Playwright pytest plugin | ui |
| Mobile | Appium Python client | mobile |
| gRPC | grpcio | grpc |
| Cross-interface workflows | pytest | core |

Performance/load, security scanning and accessibility are intentionally not hidden inside
the core runner. Add k6/Locust, OWASP ZAP, axe, etc. as separate CI phases when the product needs them.

## Add as a submodule

```bash
git submodule add git@github.com:Friz-zy/quality-bundle.git tools/quality
git submodule update --init --recursive
cp tools/quality/quality.example.toml quality.toml
mkdir -p tests/e2e/{cli,api,workflows,hurl}
```

Commit `.gitmodules`, the submodule pointer, `quality.toml`, and `tests/e2e`.

Clone a target repository with:

```bash
git clone --recurse-submodules <TARGET_REPOSITORY>
```

## Run

```bash
./tools/quality/bin/quality doctor
./tools/quality/bin/quality test
./tools/quality/bin/quality cli
./tools/quality/bin/quality api
./tools/quality/bin/quality workflow
```

The wrapper uses `uv run --project tools/quality` so the target project does not need to own
the toolkit's Python dependencies.

Optional profiles:

```bash
QUALITY_EXTRAS=api ./tools/quality/bin/quality schema
QUALITY_EXTRAS=bdd ./tools/quality/bin/quality bdd
QUALITY_EXTRAS=ui ./tools/quality/bin/quality ui
QUALITY_EXTRAS=mobile ./tools/quality/bin/quality mobile
QUALITY_EXTRAS=grpc ./tools/quality/bin/quality grpc
```

For Playwright, install browser binaries once:

```bash
./tools/quality/bin/install-ui chromium
```

Hurl is a native external CLI and must be installed on the developer machine/CI image.

## Configuration precedence
Environment variables override `quality.toml`. Useful variables:
`E2E_CLI`, `E2E_BASE_URL`, `E2E_IMAGE`, `E2E_PORT`, `E2E_HEALTH_PATH`,
`E2E_STARTUP_TIMEOUT`, `E2E_OPENAPI`, `E2E_TESTS_PATH`, `QUALITY_ARTIFACTS_DIR`,
`E2E_HURL_PATH`, and `E2E_APP_ENV_*`.

Two runtime modes are supported:
1. `E2E_BASE_URL`: test an already running deployment.
2. `E2E_IMAGE`: pytest starts the production image through Testcontainers.

## Target repository layout

```text
tools/quality/                 # pinned submodule
e2e.toml
tests/e2e/
  conftest.py              # optional project fixtures only
  cli/
  api/
  workflows/
  hurl/
  bdd/
  ui/
  mobile/
  grpc/
```

Do not copy shared fixtures into the target repository. Extend them only when the project
needs project-specific authentication, data factories, capabilities or selectors.

## CI templates
- `templates/github/e2e.yml`
- `templates/gitlab/e2e.gitlab-ci.yml`

They are templates, not drop-in assumptions: the target repository must provide its build/start
step and environment variables. GitHub checks out submodules recursively; GitLab explicitly
initializes them. Artifacts are retained even when tests fail.

## Updating
A target repository pins an exact toolkit commit through the submodule pointer.

```bash
git -C tools/quality fetch
git -C tools/quality checkout <NEW_VERSION_OR_COMMIT>
git add tools/quality
git commit
```

Run E2E before merging the pointer update. Prefer tagged toolkit releases for production projects.

## AI agents
Reference `tools/quality/SKILL.md` from the target repository's `AGENTS.md`.
The skill requires black-box boundaries, deterministic waits, regression preservation and explicit
reporting of tests actually executed.

## Design notes
- Project tests remain reviewable with the product code.
- The framework can evolve independently.
- Optional extras keep mobile/UI stacks out of API-only projects.
- The pytest plugin is auto-loaded when the package is installed by uv.
- Hurl and Schemathesis remain independent phases so failures are easy to reproduce.
- UI artifacts should use Playwright traces/screenshots/video on failure in CI.
- Mobile device/emulator lifecycle is intentionally project/CI specific.


## Extended quality profiles

The toolkit also provides intentionally separate quality phases:

| Phase | Tool | Runner | Recommended cadence |
|---|---|---|---|
| Performance smoke/load | k6 | `bin/performance` | PR smoke + scheduled load |
| Accessibility | axe + Playwright | `bin/accessibility` | PR for UI changes |
| Dynamic security | OWASP ZAP baseline | `bin/security` | scheduled + pre-release |
| Toolkit container | Docker | `Dockerfile` | reusable CI image |

These phases remain separate from functional E2E because their failure semantics,
runtime cost and CI permissions differ.

### Performance

Keep k6 scripts in `tests/e2e/performance/`. Start with a cheap smoke threshold in pull
requests. Run heavier load/stress/soak tests only against isolated environments.

### Accessibility

Keep axe/Playwright checks in `tests/e2e/accessibility/`. Accessibility checks complement,
but do not replace, functional UI tests or manual accessibility review.

### Security

The default ZAP runner performs a baseline scan against `E2E_BASE_URL`. Authentication
contexts, exclusions and accepted-risk policy belong to the target repository. Use an isolated
test environment and never point destructive active scans at production by default.

### Container image

The included `Dockerfile` packages the Python toolkit and optional profiles:

```bash
docker build --build-arg QUALITY_EXTRAS=all -t quality-bundle .
docker run --rm -v "$PWD:/workspace" -w /workspace quality-bundle test
```

For Testcontainers from inside this image, mount the container-runtime socket only in trusted CI.
Treat access to `/var/run/docker.sock` as privileged host access.

### Recommended CI split

Use fast functional tests on every pull request:

```text
CLI + API + workflow + Hurl + OpenAPI contract
```

Run browser/BDD only when the project uses them. Run performance, accessibility and security as
separate jobs so their artifacts and failure policy remain explicit. Heavy load and security jobs
are best scheduled or run before release.


## Quality harness orchestration

Version 0.2 adds declarative suite discovery and a unified quality plan.

```bash
./tools/quality/bin/quality list
./tools/quality/bin/quality plan
./tools/quality/bin/quality run
```

`list` discovers suites from `tests/e2e/` and configured OpenAPI/Hurl inputs.
`plan` prints the commands without executing them.
`run` executes the selected suites and writes:

```text
artifacts/quality/
  cli-junit.xml
  api-junit.xml
  ...
  summary.json
```

Explicit selection overrides discovery:

```bash
./tools/quality/bin/quality run cli api workflow hurl schema
```

The configuration can define defaults and exclusions:

```toml
[quality]
auto_discover = true
fail_fast = false
parallel = false
default_suites = []
exclude_suites = ["mobile"]
junit = true
json_summary = true
```

### Compatibility matrix

Compatibility is project policy, so the toolkit provides artifact resolution rather than hard-coded
support rules. Configure version identifiers in `quality.toml` and map them to released CLI binaries or
container images through CI environment variables. See `docs/COMPATIBILITY.md`.

### Reliability

The `toxiproxy` pytest fixture starts an isolated Toxiproxy container. Project-owned tests create
proxies/toxics and verify retry, timeout, idempotency and recovery through public interfaces.
See `docs/RELIABILITY.md`.

### WebSocket and SSE

The `realtime` profile adds WebSocket support and the core HTTP client is used for SSE streaming.
Helpers are available in `quality_bundle.realtime`. See `docs/REALTIME.md`.

### Recommended repository quality model

```text
tests/e2e/
  cli/             fast public CLI behavior
  api/             explicit HTTP behavior
  contract/        hand-written contracts where useful
  workflows/       cross-interface business flows
  hurl/            declarative HTTP scenarios
  bdd/             business-readable scenarios
  ui/              browser behavior
  accessibility/   axe checks
  mobile/          Appium flows
  grpc/            public gRPC behavior
  realtime/        WebSocket/SSE
  compatibility/   N/N-1 and migration scenarios
  reliability/     injected faults and recovery
  performance/     k6
  security/        ZAP policy/context
```

Do not create empty directories merely to satisfy this layout. Auto-discovery intentionally runs
only suites that exist and are configured.


## Locust as the default performance engine

Locust is now the default performance backend. This keeps performance scenarios in Python and
under the same `uv` dependency model as the rest of the harness.

A project owns `tests/e2e/performance/locustfile.py`. The shared runner controls users, spawn rate,
duration, CSV collection, threshold evaluation, JUnit generation and JSON reporting.

Example:

```toml
[performance]
backend = "locust"
users = 100
spawn_rate = 10
duration = "5m"
p50_ms = 100
p95_ms = 250
p99_ms = 500
failure_rate = 0.001
min_rps = 100
```

Run:

```bash
E2E_BASE_URL=http://127.0.0.1:8080 ./tools/quality/bin/performance
```

Artifacts include raw Locust CSV files plus:

```text
artifacts/quality/performance.json
artifacts/quality/performance-junit.xml
```

The process exits non-zero when any configured threshold fails.

k6 is no longer the default or required backend. The small `bin/k6` wrapper is retained only for
projects that explicitly want an external k6 phase.

## Project test templates

Starter templates for every supported family are under `templates/tests/`:

```text
cli api workflows hurl bdd ui accessibility mobile grpc realtime
compatibility reliability performance security
```

Run `./tools/quality/bin/init-project` to create `quality.toml` and show the available templates.
Templates are deliberately copied only when selected, so auto-discovery does not start irrelevant suites.

The templates are starting points. Product-specific endpoints, selectors, protocol messages,
performance SLOs, compatibility policy and security exceptions must stay in the target repository.


## Podman-first self-contained runner

The primary container image now runs as UID 1000 and contains a native rootless Podman runtime.
The harness starts SUT/dependency containers through a small `PodmanRuntime` abstraction rather
than requiring access to a host Docker daemon.

The default `restricted` mode uses VFS storage and `ignore_chown_errors`, so the intended launch
does not require `--privileged`, `/dev/fuse`, `/dev/net/tun`, or `/var/run/docker.sock`.

Before using a new CI executor:

```bash
docker build -t quality-bundle tools/quality

docker run --rm \
  -v "$PWD:/workspace" \
  -e E2E_PODMAN_PROBE=1 \
  quality-bundle \
  quality doctor
```

See `docs/PODMAN-RUNNER.md` for limitations and the standard/restricted modes.

### Container runtime compatibility

`testcontainers` is no longer a core dependency. The built-in runtime path uses Podman CLI
directly, which is what allows the self-contained runner to avoid a host Docker socket.
A `legacy-testcontainers` optional dependency profile remains available for project-specific
tests that still need the upstream Testcontainers Python API.


## Testcontainers + nested Podman

Testcontainers remains a first-class dependency. The runner starts:

```text
rootless Podman
  -> podman system service
  -> unix://$XDG_RUNTIME_DIR/podman/podman.sock
  -> Docker-compatible API
  -> Testcontainers Python
```

This socket belongs to the nested Podman instance. It is not a mounted host Docker socket.

The pytest fixture `testcontainers_podman` configures the environment for Testcontainers.
The `container_runtime` fixture exposes the native Podman adapter for operations such as explicit
kill/restart/fault lifecycle control.

Use Testcontainers for normal ephemeral dependencies and its existing service modules. Use the
native adapter when a test specifically needs lower-level Podman lifecycle behavior.

### Docker Compose

A complete runner compose file is included as `docker-compose.yml`.

From the toolkit repository:

```bash
docker compose build
docker compose run --rm e2e quality doctor
docker compose run --rm e2e quality plan
docker compose run --rm e2e quality run
```

For a target repository with the toolkit at `tools/quality`, copy:

```text
tools/quality/templates/target/compose.quality.yml
```

to the project root as `compose.quality.yml`, then run:

```bash
docker compose -f compose.quality.yml build
docker compose -f compose.quality.yml run --rm e2e quality run
```

The compose configuration intentionally requests no privileged mode, host container socket,
`/dev/fuse`, or `/dev/net/tun`.

A debug shell is available through the optional profile:

```bash
docker compose -f compose.quality.yml --profile debug run --rm e2e-shell
```

`bin/compose-test` can invoke the runner using either `docker compose` or `podman compose`.
