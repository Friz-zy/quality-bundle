# E2E Self-Test Plan

Self-testing plan for quality-bundle: the framework's own e2e suite exercises the framework
through its public interfaces only (console script, pytest plugin fixtures, `bin/` wrappers,
artifacts), treating the framework itself as the SUT. Produced by workflow analysis
(20 usage scenarios US-01..US-20, command/config/fixture/artifact surfaces, 9 behavioral
defects). Sequence approved by the repository owner: **record plan → fix defects → implement
tests in waves**.

## 1. Roles

| Step | Executor |
|---|---|
| Plan recording | orchestrator (this document) |
| Defect fixes F1-F10 | backend-engineer-middle |
| Post-fix verification | coordinator (direct run commands) + qa-engineer-senior (read-only diff gate) |
| Wave 1-4 test implementation | backend-engineer-middle |
| Per-wave verification | coordinator (direct pytest runs) + qa-engineer-senior (read-only review gate) |
| CI wiring for container tier | PROPOSAL ONLY - `.github/**` is a protected path; requires explicit human approval |

## 2. Defect fixes (applied BEFORE tests are written)

Tests assert the FIXED behavior. Intentional non-fixes are listed in §8.

- **F1** `src/quality_bundle/main.py:100` - `print("\\nQuality summary")` prints a literal
  backslash-n. Fix: real newline (`print("\\nQuality summary")` with a true escape).
- **F2** `src/quality_bundle/main.py:143` - `quality list` joins names with literal `"\\n"`.
  Fix: real `"\n".join(...)`, one suite per line.
- **F3** `src/quality_bundle/suites.py:48` - performance auto-discovery globs `*.js` only,
  while the runner and all templates use `locustfile.py`. Fix: discover `performance` when the
  directory contains `locustfile.py` OR any `*.js` (k6 legacy kept working).
- **F4** `src/quality_bundle/main.py:53-66` - unknown explicit suite (`quality run bogus`)
  raises an uncaught RuntimeError traceback, exit 1. Fix: clean `error: Unknown suites: bogus`
  on stderr, exit 2 (matches the existing command-build error pattern at main.py:156-157).
  Applies to `run` and `plan`.
- **F5** `src/quality_bundle/main.py:70-73` - empty discovery returns 0 without writing
  `summary.json`, which looks like success with no record. Fix: keep exit 0 and the
  `No suites discovered.` message, but still write `summary.json` (status `passed`,
  `suites: []`, zero totals) when `json_summary` is enabled.
- **F6** `bin/performance:4` - `QUALITY_CONFIG` defaults to `e2e.toml` while `load_config`
  defaults to `quality.toml`. Fix: default to `quality.toml`.
- **F7** `bin/compose-test:4` - default compose file `$KIT/docker-compose.yml` does not exist.
  Fix: default to `$KIT/compose.quality.yml`.
- **F8** `src/quality_bundle/suites.py:15-33` - `contract` (README-documented layout, marker
  registered) and `container` (shipped `templates/tests/containers/`) are unreachable through
  `quality run/plan/list`. Fix: add `contract` suite (dir `contract`, marker `contract`) and
  `container` suite (alias dir `containers`, marker `container`), both without extras.
- **F9** `README.md` drift: CI template filenames (`templates/github/quality*.yml`, not
  `e2e.yml`), `e2e.toml` -> `quality.toml` in the target layout, performance phase row
  (Locust via `bin/performance`, k6 optional via `bin/k6`), testcontainers dependency
  paragraph (core dependency; nested rootless podman socket), `docker-compose.yml` ->
  `compose.quality.yml`, target layout tree gains `contract/` and `containers/`.
- **F10** Unit tests in `tests/` updated/added for F1-F8; the existing 20 stay green.
  No new dependencies, no `pyproject.toml`/`uv.lock` changes.

Fixes F11-F13 were discovered BY the e2e tests during implementation and approved by the
coordinator under the same defect-fixing mandate:

- **F11** `src/quality_bundle/main.py` - suite/test subcommands used argparse REMAINDER,
  which fails on option-like first extra tokens (`quality cli -k health` -> exit 2
  `unrecognized arguments`). Fix: pre-argparse argv split (`split_argv`) - everything after
  the suite/`test` token passes through to pytest; unknown bare tokens get the F4-style
  clean `error: Unknown suites: <name>` exit 2; all previously valid invocation forms
  preserved (`--config X`/`--config=X` in front, bare suites, `-h` passthrough).
- **F12** `bin/quality` - the wrapper execed the nonexistent script `quality-bundle`
  (installed console script is `quality`), so the documented primary entry point always
  failed. Fix: exec `quality`.
- **F13** `src/quality_bundle/main.py external_command('schema')` - used
  `python -m schemathesis`, but schemathesis 4.x ships no `__main__`, so the schema suite
  could never run. Fix: resolve the `schemathesis` console script via `shutil.which`;
  clean `RuntimeError("Schemathesis is not installed")` when absent.

## 3. Harness design (`tests/e2e/`)

- **Demo SUT** (`tests/e2e/sut/demo_sut.py`): stdlib `http.server.ThreadingHTTPServer` bound
  to `('127.0.0.1', 0)` (real port read after bind; per-xdist-worker instance, no collisions).
  Endpoints: `GET /health` 200 (controllable `/_ctl/health?mode=flap` -> 503 twice then 200;
  `?code=418` persistent), `GET /ready` 200, `GET /api/data` 200 JSON, `POST /api/echo` echo,
  `GET /events` SSE (comments + 3 events, held open), `GET /boom` 500, `GET /a11y` HTML.
  Session-scoped autouse fixture starts it.
- **Dogfood env stamping**: the autouse fixture exports `E2E_BASE_URL`/`E2E_HEALTH_PATH`/
  `E2E_STARTUP_TIMEOUT` so the plugin's own fixtures (`e2e_config`, `app_env`, `e2e_base_url`
  (canonical), `base_url` (deprecated alias), `api`) resolve against the demo SUT when
  self-tests request them; restored at teardown.
- **CLI invocation**: T1 uses `[sys.executable, '-m', 'quality_bundle.main']` via
  `subprocess.run(cwd=tmp_project, capture_output=True, text=True, timeout=...)` with a
  scrubbed env (all `E2E_*`/`QUALITY_*` removed, then per-test overrides). `bin/quality`
  (uv wrapper) is covered separately as T3 (E2E-062).
- **PATH shims**: generated executables in a tmp PATH dir (fake `hurl`, `docker`, `podman`,
  `k6`) that log argv and exit with canned codes/stdout - exercises binary-dependent code
  paths without the binaries.
- **Fixture project builder**: `make_project(tmp_path, suites, toml)` writes `quality.toml`,
  a `pytest.ini` registering suite markers (prevents inner exit 5), and `tests/<dir>/test_*.py`
  bodies; the demo SUT URL is baked into the tmp `quality.toml`; `QUALITY_ARTIFACTS_DIR`
  always points into `tmp_path`.
- **Recursion guard**: the repo's own `tests/e2e` stays FLAT (no suite-named subdirs, no
  `hurl/`, no `performance/`, no `security/`), so self-discovery at repo root is empty
  (pinned by E2E-026 plus a layout self-check).

## 4. Tier model

| Tier | Meaning | Gating |
|---|---|---|
| T1 (180) | 122 e2e + 58 unit; runs anywhere with the synced uv env; localhost only; no containers/binaries | none (default) |
| T2 (12) | Needs a working rootless podman / docker socket | marker `container` |
| T3 (9) | Needs external binaries/extras (hurl, locust, schemathesis, playwright/axe, uv extras) | `skipif` + marker `slow` where heavy |

Final static recount of the FINAL tree (after the parametrized podman-doctor tests and the
E2E-085 marker move): 201 expected collected items = 163 test functions (61 under `tests/`
and 102 under `tests/e2e/`) + 38 net parametrized expansion (17 parametrized decorators,
55 total parameter cases, 55-17=38) = 180 default T1 + 9 slow + 12 container (180+9+12=201);
143 e2e + 58 unit items. This is static/expected collection arithmetic only, NOT a fresh
`pytest --collect-only` or execution result.

Historical last full run before the final small test additions: `uv run pytest tests -q` ->
186 passed, 2 skipped, 0 xfailed (agent-reported). This predates the final parametrized
podman-doctor tests and the E2E-085 marker-only correction (classification-only: an
unnecessary `container` marker was removed from E2E-085, which stays T1 and is pinned by a
dedicated runtime-independence test). After those final edits only targeted checks ran: the
E2E-085 journey + tier pin, the runtime unit tests, the podman-doctor shim tests (10 passed,
including actual E2E-072), and the entrypoint tests (15 passed). No fresh full-suite result
exists after the final edits; rerun the full suite before claiming final full local
verification.

CI does NOT use a marker filter: the existing `.github/workflows/toolkit.yml` `test` job
already executes unfiltered `uv run pytest tests`, so that job runs every marker tier, with
T2/T3 tests self-skipping when their probes (podman, external binaries) are absent. CI smoke
jobs run `smoke/` tests, not `tests/e2e`. No `.github/**` file was changed by this work, and
NO remote GitHub CI run exists for it: the worktree is uncommitted/untracked on `main` at
`ea49843`, so a remote run cannot see the local changes (commit+push was not explicitly
authorized), and independent security review found the workflow's privileged/container-socket
jobs (`--privileged` image and nested-podman smokes, host Docker socket mount in the
Docker-out-of-Docker smoke) lack verified fail-closed isolation, so CI execution is BLOCKED
under current policy. The reviewed timeout + JUnit-artifact patch for the `test` job passes
in principle but was not applied (`.github/**` is a protected path requiring explicit human +
security approval). Do not bypass either blocker.

## 5. Test inventory (planned 85 rows -> 201 statically expected collected items; behavior reflects §2 fixes and the post-gate runtime fixes; post-implementation adjustments marked ✔)

Legend: P0/P1/P2 priority; ✱ = intentional-behavior pin (see §8).

### CLI contract (T1)
- E2E-001 P0 `doctor` prints the 11-key table, always exit 0 ✱ (main.py:105-122)
- E2E-002 P0 `doctor --config` reflects toml values; missing file -> silent defaults (config.py:83-88)
- E2E-003 P0 `doctor` env overrides (E2E_BASE_URL/E2E_IMAGE/E2E_TESTS_PATH/E2E_OPENAPI, param) (config.py:98-113)
- E2E-004 P0 `QUALITY_CONFIG` selects the config file (config.py:84)
- E2E-005 P0 argparse contract: no subcommand -> usage exit 2; `--help` exit 0 lists all suites incl. contract, container (main.py:124-138)
- E2E-006 P0 `list` prints discovered suites one per line (post-F2) (main.py:142-143, suites.py:36-53)
- E2E-007 P0 `list` empty discovery -> exit 0, stdout exactly one blank line (`\n`, actual `print` of empty join - pinned)
- E2E-008 P1 `exclude_suites` filters list output (env + toml param) (suites.py:52-53)
- E2E-009 P0 `plan` prints `Suites:` header + per-suite commands, exit 0, no execution; hurl-without-binary branch skips when hurl IS installed (main.py:68-97)
- E2E-010 P1 `plan` creates the artifacts dir without executing anything ✱ (main.py:14-27,96-99)
- E2E-011 P0 `plan schema` builds schemathesis command from local mini OpenAPI (post-F13; fake `schemathesis` PATH-shim keeps the test T1-always) (main.py)
- E2E-012 P0 `run` happy path: exit 0, `summary.json` payload exact keys, per-suite junit, command echo (main.py:68-103, reporting.py:14-26)
- E2E-013 P0 `run` failing suite: exit 1, failed totals, junit still written
- E2E-014 P0 `run` summary block after a real newline header (post-F1), row format `16/7/8.3f` (main.py:100-102)
- E2E-015 P0 empty discovery: exit 0, `No suites discovered.`, `summary.json` written with empty suites (post-F5) (main.py:70-73,98-99)
- E2E-016 P0 unknown explicit suite: exit 2, stderr `error: Unknown suites: bogus`, no summary (post-F4)
- E2E-017 P0 selection precedence matrix, 8 params: explicit>QUALITY_SUITES-env>toml-default>auto-discover>fallback; exclusions post-validation; comma-string parsing (main.py:53-66, config.py:76-81,116-120)
- E2E-018 P0 single-suite subcommand runs `pytest -m <marker>`, option passthrough (`quality cli -k health`; works post-F11) (main.py)
- E2E-019 P0 `quality hurl` without binary -> stderr `error: Hurl is not installed`, exit 2; skips when hurl present
- E2E-020 P0 `quality schema` unconfigured -> exit 2 (main.py:37-39)
- E2E-021 P0 `quality test` runs cfg tests, `--e2e-config` only when `--config` given (main.py:146-149)
- E2E-022 P0 `fail_fast` stops after first failure; off -> all suites run (param) (main.py:76-95)
- E2E-023 P1 `parallel=true` adds `-n auto` (plan) and a parallel run stays green (main.py:22-23)
- E2E-024 P1 artifact toggles: junit=false / json_summary=false (param) (main.py:20-21,98-99)
- E2E-025 P1 `QUALITY_EXTRAS` injected into child env for extras-gated suites; absent for cli (main.py:84-86, suites.py:15-33)
- E2E-026 P0 recursion guard: repo-root discovery empty + flat-layout self-check (suites.py:36-53)

### Plugin fixtures & polling (T1)
- E2E-027 P0 fixtures e2e_config/artifacts_dir/e2e_base_url (canonical)/base_url (deprecated alias)/api dogfood against demo SUT (pytest_plugin.py)
- E2E-028 P1 api fixture GET/POST + trailing-slash rstrip (pytest_plugin.py:17-19)
- E2E-029 P0 health polling succeeds after transient 503s; predicate status<500 (environment.py:39-45, polling.py:2-9)
- E2E-030 P0 persistent 418 counts as ready (environment.py:42)
- E2E-031 P1 custom `E2E_HEALTH_PATH=/ready` honored (config.py:102)
- E2E-032 P0 unreachable base_url + E2E_STARTUP_TIMEOUT=1 -> TimeoutError message, run exit 1 (polling.py:2-10)
- E2E-033 P1 `cli` fixture skips with 'CLI is not configured' when app.cli unset (pytest_plugin.py:20-23)
- E2E-034 P0 neither base_url nor image -> configure error, exit 1 (environment.py:17-20)
- E2E-035 P1 no `sut.log` in base_url mode (environment.py:48-58)

### Realtime (T1/T3)
- E2E-036 P0 `read_sse` parses events, ignores comments, honors limit (realtime.py:5-21)
- E2E-037 P1 `read_sse` raises on non-200 (realtime.py:7-8)
- E2E-038 P1 T3 slow `websocket_json` echo roundtrip (websockets extra, local echo server) (realtime.py:23-30)
- E2E-039 P1 `quality run realtime` template journey vs SSE SUT (templates/tests/realtime/)

### Performance (T1/T3)
- E2E-040 P0 `read_locust_stats` parses Aggregated CSV exactly (performance.py:18-36)
- E2E-041 P1 missing Aggregated row -> RuntimeError (performance.py:22-24)
- E2E-042 P1 `evaluate` verdicts: pass/fail/None-disabled (param, CSV chain) (performance.py:38-52)
- E2E-043 P1 `write_reports` emits performance.json + junit failure embedding (performance.py:54-67)
- E2E-044 P0 performance discovery: locustfile.py discovered, *.js discovered, neither not (post-F3) (suites.py:48-49)
- E2E-045 P0 `bin/performance` without E2E_BASE_URL -> exit 1, no artifacts (bin/performance:6)
- E2E-046 P0 non-locust backend guard -> exit 2, offline (bin/performance:18-20)
- E2E-047 P0 `quality performance` delegates; run-mode records exit_code=1 (main.py:47-48,87-93)
- E2E-048 P1 T3 slow full locust pipeline green (users=5, 10s, loose thresholds) (bin/performance:22-46)
- E2E-049 P1 T3 slow threshold failure -> exit 1 + failure list (bin/performance:36-45)
- E2E-050 P2 T3 slow `bin/performance` reads quality.toml by default (post-F6; users from [performance]) (bin/performance:4, config.py:84)

### Wrappers & onboarding (T1/T3)
- E2E-051 P0 discovery channels matrix (~13 params: workflows alias, bdd, ui, mobile, grpc, realtime, compatibility, reliability, contract, containers, security bare dir, hurl glob, openapi schema; negative: empty cli dir) (suites.py:36-53)
- E2E-052 P0 `bin/zap` without E2E_BASE_URL -> exit 1 ✔ pinned ACTUAL: no zap dir created (E2E_BASE_URL guard fires before mkdir) (bin/zap:3-5)
- E2E-053 P1 `bin/zap` docker argv + E2E_ZAP_IMAGE override via docker shim (bin/zap:3-8)
- E2E-054 P1 hurl command construction via hurl shim: base_url rstrip, junit path, sorted files (main.py:29-36)
- E2E-055 P1 T3 real hurl run -> hurl-junit.xml (skipif hurl absent)
- E2E-056 P1 T3 slow schemathesis green on mini OpenAPI ✔ green after F13 (real schemathesis v4 ran against demo SUT)
- E2E-057 P1 `bin/k6` missing binary -> exit 127; skips when k6 present (bin/k6:3-4)
- E2E-058 P1 `bin/k6` argv + exit-code passthrough via shim (bin/k6:5)
- E2E-059 P0 `init-project` scaffolds target (dir + quality.toml byte-equal + template list) (bin/init-project)
- E2E-060 P0 `init-project` never overwrites existing quality.toml
- E2E-061 P1 `init-project` default target is cwd (param)
- E2E-062 P2 T3 `bin/quality` uv wrapper roundtrip ✔ green after F12 (`--help` exit 0)
- E2E-063 P1 T3 slow `bin/accessibility` axe scan on clean page (playwright/axe present)
- E2E-064 P2 T3 `bin/install-ui --help` side-effect free (bin/install-ui)

### Runtime adapter (T1)
- E2E-065 P0 `E2E_CONTAINER_RUNTIME` non-podman -> RuntimeError (runtime.py:120-125)
- E2E-066 P1 PodmanRuntime command shapes via podman shim: run argv, port parse, stop; every subprocess call timeout-bounded post-fix (runtime.py)

### Container runner (T1 guards / T2 journeys)
- E2E-067 P1 T2 entrypoint invalid `E2E_PODMAN_MODE` -> exit 2 (containers/entrypoint.sh)
- E2E-068 P1 T2 entrypoint SERVICE=0 execs without socket
- E2E-069 P0 `bin/compose-test` unknown engine -> exit 2 (bin/compose-test:14-17)
- E2E-070 P1 compose-test default file `compose.quality.yml` EXISTS (post-F7) + shim argv uses it (bin/compose-test:4)
- E2E-071 P0 compose-test engine command construction (param docker/podman, shims)
- E2E-072 P1 T2 `bin/podman-doctor` full pass path (bounded by E2E_PODMAN_TIMEOUT; port probe mirrors PodmanRuntime: preallocated free host port on the `podman` bridge)
- E2E-073 P1 T2 `PodmanRuntime.probe` report shape + volume cleanup (runtime.py:98-118)
- E2E-074 P0 T2 E2E_IMAGE journey: run green, sut.log written, container cleaned, re-run ok (environment.py:17-58)
- E2E-075 P1 T2 E2E_APP_ENV_* reaches the SUT container (environment.py:22-33)
- E2E-076 P2 T2 entrypoint fails closed when required socket cannot start
- E2E-077 P1 T2 testcontainers_podman fixture: DOCKER_HOST socket + RYUK disabled (testcontainers_runtime.py:7-19)
- E2E-078 P0 T2 generic_container publishes and serves a port ✔ PASSES (no longer xfail): `PodmanDockerContainer` overrides host/port resolution for explicitly published ports (preallocated free host port via `free_host_port`; HostConfig-free host-IP override returns 127.0.0.1) and pins the `podman` bridge network, sidestepping the podman compat-inspect KeyError (testcontainers_runtime.py)
- E2E-079 P2 T2 templates/tests/containers journey via `quality test` REMAINDER (main.py:146-149)

### Reliability & compatibility
- E2E-080 P0 T2 toxiproxy fixture lifecycle (reliability.py:4-33)
- E2E-081 P1 T2 reliability template journey (fault injection)
- E2E-082 P0 compat artifacts_from_env mapping: dots/dashes/missing (param) (compatibility.py:11-20)
- E2E-083 P1 compatibility_artifacts fixture ✔ consistency pin: fixture == artifacts_from_env(config versions) (session-cached e2e_config makes per-test env unreachable; env mapping covered by E2E-082)
- E2E-084 P1 `run_upgrade_command` ✔ pins ACTUAL: `echo {old}->{new}` contains a shell redirection -> side-effect file `2.0` contains `1.4.0-`, stdout empty (compatibility.py:22-24)
- E2E-085 P2 T1 (re-tiered from T2; `container` marker removed) compatibility template journey with fake old CLIs; runtime independence pinned by a dedicated tier-pin test

## 6. Test data strategy

- `tests/e2e/fixtures/data/locust_stats_{good,bad,noagg}.csv` - full locust header + Aggregated row variants.
- `tests/e2e/fixtures/openapi/mini.yaml` - 2-path OpenAPI 3 schema (never requires schemathesis at design time).
- Fixture `quality.toml` variants written by `make_project` (defaults, selection, toggles, health, openapi, performance thresholds).
- Inner test files generated as strings; per-project `pytest.ini` registers suite markers.
- Tmp hurl placeholders for discovery/argv ordering; `templates/tests/hurl/health.hurl` reused for real hurl (T3).
- PATH shims generated at runtime into tmp (never in the repo).
- `tests/e2e/fixtures/container_sut/{Dockerfile,server.py}` - tiny image serving /health with APP_MSG echo (T2, Wave 4).

## 7. Coverage matrix (area -> tier -> tests)

- CLI doctor: T1 [001-004] - unit: none
- CLI list/plan: T1 [006-011, 054] - unit: test_suites (discovery only)
- CLI run + exit codes: T1 [012-016] - unit: test_reporting
- Suite selection: T1 [008, 017, 051] - unit: test_suites
- Single-suite/test passthrough: T1 [005, 018-021]
- fail_fast/parallel: T1 [022-023]
- Artifacts/toggles: T1 [012-013, 024] - unit: test_reporting
- Extras gating: T1/T3 [025, 062-063]
- Config/env precedence: T1 [002-004, 017] - unit: test_config
- Plugin fixtures: T1 [027-028, 033, 083] - unit: none (plugin had zero tests)
- Health polling: T1 [029-032, 034-035]
- Realtime: T1/T3 [036-039]
- Performance: T1/T3 [040-050] - unit: test_performance (evaluate only)
- Security/zap: T1 guards [052-053]; real scan deferred (docker+image pull; CI image jobs cover)
- Hurl: T1 shim [054]; T3 real [055]
- Schema: T1 [011, 020]; T3 [056]
- k6: T1 [057-058]
- Onboarding: T1 [059-061]
- Runtime adapter: T1 [065-066] - unit: test_runtime
- Container runner: T1 [069-071]; T2 [067-068, 072-079] - unit: test_entrypoint
- E2E_IMAGE journey: T2 [074-075]
- Testcontainers: T2 [077-079] - unit: test_testcontainers_runtime
- Toxiproxy: T2 [080-081]
- Compatibility: T1 [082-085] (E2E-085 re-tiered from T2)
- Recursion guard: T1 [026]
- install-ui real download: deferred (network+apt; CI image build covers) [064 = --help smoke]
- `quality doctor` in built image: deferred (already exercised by toolkit.yml image job)

## 8. Execution policy

- Default local: `uv run pytest tests/e2e -m 'not container and not slow'` (budget <= 5 min). Full local: drop the `-m` filter. CI runs `uv run pytest tests` unfiltered (§4).
- Timeouts: 60s default per CLI subprocess; 240s for tests spawning nested `quality run`; 30s for wrappers/entrypoint.
- Flaky policy: no retries ever; port 0 everywhere; a test failing >1 of 20 identical runs is flaky and gets fixed (timeout/env isolation) or quarantined behind `slow` with a root-cause ticket.
- Characterization registry (post-fix remainder), maintained in `tests/e2e/CHARACTERIZATION.md`:
  E2E-001 (doctor always exit 0 - intentional: report, not gate), E2E-010 (plan mkdir side effect - intentional, documented), E2E-007 (empty `list` prints exactly one blank line), E2E-052 (zap guard fires before mkdir - no dir on error path), E2E-083/E2E-084 (compatibility fixture-consistency and `echo` redirection actual-behavior pins). Accepted limitations, unpinned: performance `warmup` parsed but unused; `headless` hardcoded.
- All writes under `tmp_path`; repo used read-only; localhost only; no new dependencies.

## 9. Implementation waves

| Wave | Scope | Depends | Verify command |
|---|---|---|---|
| 0 (fixes) | F1-F10 | - | `uv run pytest tests -q` green + coordinator probes |
| 1 | Scaffolding: conftest, demo SUT, shims, make_project, data fixtures, E2E-027 canary | 0 | `uv run pytest tests/e2e -m 'not container and not slow'` |
| 2 | P0 T1 CLI contract: E2E-001..026 | 1 | `uv run pytest tests/e2e/test_cli_*.py tests/e2e/test_selfhost_guard.py` |
| 3 | P1 T1 + T3-lite: E2E-028..066 (minus container) | 1 | `uv run pytest tests/e2e -m 'not container and not slow'` |
| 4 | T2 + container SUT image: E2E-067..085 | 1-3 | `uv run pytest tests/e2e -m container` (skips gracefully without podman); T1 command stays green |

CI wiring proposal (NOT applied; `.github/**` protected): run `-m container` inside the
existing `smoke-nested-podman` image job; testcontainers subset inside `smoke-dood`.
Requires explicit human approval before any workflow edit.

## 10. Decision log

- Empty discovery keeps exit 0 but writes summary.json (F5) - explicit record, CI-safe.
- Unknown suite exits 2 (F4) - consistent with command-build error pattern.
- doctor exit 0 and plan mkdir stay as intentional behavior (pinned by tests, not "fixed").
- `quality container` suite added (F8) so shipped templates/tests/containers become orchestrated.
- Schemathesis red-path (failing schema) dropped: pins schemathesis behavior, not the framework.

## 11. Post-implementation log (final gate: PASS; evidence ladder below)

Implemented across waves 0-4 plus F11-F13, 4 gate-driven robustness fixes, and the post-QA
runtime-fix round summarized at the end of this section. Evidence ladder (precise labels;
no claim beyond them):

1. HISTORICAL (earlier tree state, BEFORE the runtime-fix round; these numbers describe that
   run only and are superseded by the final counts below): `uv run pytest tests -q` ->
   159 passed, 10 skipped, 1 xfailed; tiers T1 148 passed / 22 deselected, slow 7 passed /
   2 skipped (hurl and Chromium absent), container 4 passed / 8 skipped / 1 xfailed
   (E2E-078, since fixed).
2. HISTORICAL - last full run before the final small test additions (the parametrized
   podman-doctor tests and the E2E-085 marker-only correction): `uv run pytest tests -q` ->
   186 passed, 2 skipped, 0 xfailed (agent-reported). In that state the container tier was
   reported as 13 passed twice.
3. After the final edits (podman-doctor parametrization + E2E-085 marker move): targeted
   checks only - E2E-085 journey + tier pin passed, runtime unit tests passed,
   podman-doctor shim tests 10 passed (including actual E2E-072), entrypoint tests 15 passed.
   NO fresh full-suite run exists after these final edits: rerun `uv run pytest tests -q`
   before claiming final full local verification.

Final static recount of the FINAL tree (collection structure, NOT run evidence): 201 expected
collected items = 163 test functions (61 under `tests/`, 102 under `tests/e2e/`) + 38 net
parametrized expansion (17 parametrized decorators, 55 total parameter cases, 55-17=38);
after the E2E-085 marker move: 12 container, 9 slow, 180 default T1 (122 e2e + 58 unit);
143 e2e + 58 unit items total; 180+9+12=201. This is static/expected collection arithmetic
only, NOT a fresh `pytest --collect-only` or execution result.

Environment findings (this dev container): rootless podman IS usable (`podman info`,
`unshare --user`, pulls, explicit `-p HOST:PORT` all work) but dynamic publish `-p 0:PORT`
is rejected by this podman build - `PodmanRuntime` now preallocates explicit free host ports
instead of relying on dynamic publish; `/workspace` cannot be created (root-owned `/`); `/tmp`
is mounted noexec (test shims live under `~/.cache/quality-e2e-shims/<pid>`).

Post-gate runtime fixes reflected in this plan (compact list; no new test IDs):

- `PodmanRuntime` subprocess operations are timeout-bounded (120 s default per command;
  600 s run; 900 s pull/build), and port allocation is bounded (`MAX_PORT_ATTEMPTS`) with
  preallocated free ephemeral host ports published on the `podman` bridge network
  (annotated: E2E-066, E2E-072..079).
- testcontainers-over-podman no longer depends on the compat-API HostConfig lookup:
  `PodmanDockerContainer` overrides host/port resolution for explicitly published ports
  (annotated: E2E-077/E2E-078).
- Canonical session fixture `e2e_base_url`; `base_url` retained only as a deprecated alias
  (annotated: E2E-027).
- Entrypoint knobs: `E2E_WORKSPACE_DIR` (default `/workspace`), `E2E_KIT_ROOT` (default
  `/opt/quality-bundle`) (annotated: E2E-067/E2E-068); `E2E_PODMAN_TIMEOUT` (positive integer
  seconds, default 120) bounds every `bin/podman-doctor` probe call, whose port probe mirrors
  PodmanRuntime network/publish parity (annotated: E2E-072).

Maintainer handoff - remaining items only. Resolved by the runtime-fix round and removed from
this table: Podman `-p 0:PORT` dynamic publish, testcontainers HostConfig KeyError on podman
compat inspect, entrypoint hard-coded `/workspace` + `/opt/quality-bundle`, `PodmanRuntime`
subprocess timeouts, `podman-doctor` timeout/network mismatch.

| Issue | Severity | Evidence | Remediation direction |
|---|---|---|---|
| Legacy `base_url` fixture can still be shadowed by pytest-base-url wherever both plugins are installed (pytest-playwright pulls it in) | low (mitigated) | src/quality_bundle/pytest_plugin.py docstrings; tests/e2e/conftest.py re-assert; pinned by the E2E-027 regression | migration only: use the canonical `e2e_base_url`; keep `base_url` as a deprecated alias |
| `bin/zap` creates its artifacts dir only after the E2E_BASE_URL guard | none (intentional) | bin/zap:4-5; pinned by E2E-052 | retained as an explicit error-path behavior; product decision, no change planned |
| Allocator prebind close/rebind window carries a small documented TOCTOU race | low (accepted) | src/quality_bundle/runtime.py `free_host_port` - port bound on 127.0.0.1, then released before podman rebinds; bounded by `MAX_PORT_ATTEMPTS` distinctness retries | standard tradeoff (same pattern as testcontainers); revisit only if a collision is ever observed |

CI status for this work - NO remote GitHub CI run exists, and neither blocker may be bypassed:

1. The worktree is uncommitted/untracked on `main` at `ea49843`, so a remote run cannot see
   the local changes; commit+push was not explicitly authorized.
2. Independent security review found the current workflow's privileged/container-socket jobs
   (`--privileged` image and nested-podman smokes, host Docker socket mount in the
   Docker-out-of-Docker smoke) lack verified fail-closed isolation, so CI execution is
   BLOCKED under current policy. The existing `test` job already executes unfiltered
   `uv run pytest tests` (no `.github/**` file was changed by this work); the reviewed
   timeout + JUnit-artifact patch for it passes in principle but was not applied because
   `.github/**` is a protected path requiring explicit human + security approval.

Known environment quirk (pre-existing, not introduced by this work): in this dev container
any `uv run` invocation rewrites `uv.lock` with a 4-line `[options] exclude-newer` block
(the container's uv config uses a relative exclude-newer). Observed on the pristine
baseline before any changes. The current worktree contains this environment-generated
lock delta: 4 metadata lines only, no versions or package entries changed. It is not
intended as a dependency change; `uv.lock` is excluded from this patch and left untouched
(harmless metadata; CI is unaffected) unless a human deliberately wants it committed.
