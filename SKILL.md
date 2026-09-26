---
name: quality-bundle
description: Write, review, run, and debug project-owned functional black-box tests using the shared quality-bundle.
---
# Black-box E2E skill

## Core contract
The SUT is a black box. Never import production packages into E2E tests.
Use only public interfaces: executable CLI, HTTP/gRPC/WebSocket APIs, browser UI,
mobile UI, public files, stdout/stderr, exit status, and externally observable side effects.

## Test ownership
Framework code lives in the `tools/quality` submodule.
Product-specific tests, feature files, selectors, fixtures, schemas, and test data live in the target repository.

## Choose the narrowest suitable layer
- CLI: pytest + subprocess helpers.
- Explicit API workflows: pytest + httpx.
- HTTP request/response contracts: Hurl.
- OpenAPI generated/property testing: Schemathesis.
- Cross-interface workflows: pytest.
- Browser UI: pytest + Playwright.
- BDD/Gherkin: pytest-bdd; use only when executable business specifications add value.
- Mobile: Appium; keep capabilities/selectors in the target repository.
- gRPC: grpcio client against the public endpoint.
- Dependencies/SUT images: Testcontainers.

## Hard rules
1. Do not mock the SUT.
2. Do not inspect private database tables as the result oracle.
3. Do not reproduce implementation algorithms in expected-value code.
4. Prefer structured output and stable public identifiers.
5. A test must run independently and must not depend on test order.
6. Use unique resource names and clean up external state when practical.
7. Poll observable state with a deadline; avoid arbitrary sleeps.
8. Preserve a regression assertion when it exposes a real product bug.
9. Never commit credentials or print secrets in artifacts.
10. Collect useful failure evidence: argv, exit code, stdout/stderr, HTTP status/body,
    browser trace/screenshots, Appium logs, and SUT logs as applicable.

## Workflow
1. Read the public requirement.
2. Identify observable input/output.
3. Search existing tests for overlap.
4. Add the smallest failing regression or behavior test.
5. Run the narrowest suite first.
6. Fix product code only if assigned.
7. Re-run the regression.
8. Run the affected suite.
9. Run broader E2E phases when feasible.
10. Report commands, pass/fail/skip counts, and anything not run.

## Canonical commands
`./tools/quality/bin/quality doctor`
`./tools/quality/bin/quality cli`
`./tools/quality/bin/quality api`
`./tools/quality/bin/quality workflow`
`QUALITY_EXTRAS=bdd ./tools/quality/bin/quality bdd`
`QUALITY_EXTRAS=ui ./tools/quality/bin/quality ui`
`QUALITY_EXTRAS=mobile ./tools/quality/bin/quality mobile`
`QUALITY_EXTRAS=api ./tools/quality/bin/quality schema`
`./tools/quality/bin/quality hurl`


## Extended quality phases

### Performance
Use k6 for externally observable latency, error-rate and throughput requirements.
Do not run stress/soak tests against shared or production environments without explicit authorization.
Keep thresholds in project-owned scripts.

### Accessibility
Use axe with Playwright for automated WCAG-oriented checks on stable UI states.
A zero automated violation result is not proof of complete accessibility.

### Security
Use OWASP ZAP baseline scanning as a separate DAST phase.
Do not turn passive/baseline findings into destructive active scanning automatically.
Authentication contexts, exclusions and risk acceptance must be project-specific and reviewable.

### Containerized toolkit
The toolkit Docker image is a transport/runtime convenience, not the SUT.
Do not bake project secrets or product-specific test code into the toolkit image.
Mount or checkout the target repository at runtime.


## Quality harness orchestration

Before a broad run, use `quality-bundle plan` to inspect the suites that will execute.
Prefer `quality-bundle run <suite...>` during development and `quality-bundle run` in CI when auto-discovery is enabled.

### Compatibility
Test only combinations declared supported by the product. Use released artifacts and public
interfaces. Do not infer compatibility from shared internal code.

### Reliability
Fault injection must have a concrete externally observable expectation. Examples include bounded
retry, no duplicate side effect, degraded response, recovery, or explicit failure.
Never inject destructive faults into production by default.

### Realtime
For WebSocket/SSE, assert public protocol semantics: message/event shape, ordering when guaranteed,
authentication, reconnect/resume when specified, and bounded timeout behavior.

### Reporting
A broad run must preserve per-suite JUnit files and `summary.json`. Do not claim an unexecuted suite
passed. A skipped suite is not equivalent to a passing suite.


## Locust performance policy

Locust is the default performance engine.

Use named requests for dynamic URLs so statistics aggregate by logical endpoint.
Model public user behavior with weighted tasks when realistic load shape matters.
Use thresholds as acceptance criteria, not as arbitrary numbers copied from the toolkit.

Prefer:
- `p50` for typical latency when relevant
- `p95` as the primary tail-latency acceptance threshold
- `p99` for severe tail regressions
- failure rate for correctness under load
- minimum RPS only when throughput is itself a requirement

The default `p95=500ms`, `p99=1000ms`, and `failure_rate=1%` are starter template values only.
Replace them with product SLOs before treating performance failures as release gates.

Keep smoke/load/stress/soak intent explicit. Do not run stress or soak workloads on production
without explicit authorization.


## Podman runtime policy

The shared harness is Podman-first. Do not add a host Docker socket merely to make a test pass.
Use the native runtime adapter for SUT/dependency containers.

On a new CI executor, run `podman-doctor` before debugging application tests. Distinguish a
runtime-capability failure from a product failure.

Restricted mode intentionally uses VFS and ownership squashing. If an image requires distinct
Unix ownership, use standard mode on an executor with working subordinate UID/GID mappings rather
than weakening the application test.


## Testcontainers on Podman

Testcontainers is a preferred API for ordinary ephemeral test dependencies. Inside the shared
runner it must use the private nested Podman API socket, never a host Docker socket.

Use the `testcontainers_podman` fixture before project-owned Testcontainers fixtures when explicit
configuration is useful. Always scope containers with context managers or pytest finalizers.

Prefer the native `container_runtime` fixture only for lifecycle/fault operations that are awkward
or unavailable through Testcontainers.
