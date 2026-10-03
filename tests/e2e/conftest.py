"""Shared e2e scaffolding for the quality-bundle self-test suite (plan §3).

Fixtures:
  demo_sut    session-scoped autouse; starts the demo SUT and stamps E2E_* env so the
              framework's own pytest11 fixtures resolve against it; restores env and stops
              the server at teardown.
  invoke_cli  subprocess runner for [python -m quality_bundle.main ...] with a scrubbed env.
  invoke_bin  subprocess runner for bash <repo>/bin/<script> with a scrubbed env.
  make_project builds a throwaway target project (quality.toml + pytest.ini + suite dirs).
  shim        writes executable bash shims into a session-unique tmp dir for PATH prepending.
"""
from __future__ import annotations
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = Path(__file__).resolve().parent
if str(E2E_DIR) not in sys.path:
    sys.path.insert(0, str(E2E_DIR))

# ALL suite markers the harness can select with -m; inner pytest.ini must register them
# or deselection yields exit 5 ("no tests ran").
ALL_MARKERS = ["cli", "api", "contract", "workflow", "bdd", "ui", "accessibility",
               "mobile", "grpc", "realtime", "compatibility", "reliability", "container"]


@pytest.fixture(scope="session")
def demo_sut():
    from sut.demo_sut import serve
    server, port = serve()
    url = f"http://127.0.0.1:{port}"
    stamped = {"E2E_BASE_URL": url, "E2E_HEALTH_PATH": "/health", "E2E_STARTUP_TIMEOUT": "10"}
    previous = {key: os.environ.get(key) for key in stamped}
    os.environ.update(stamped)
    yield url
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def e2e_config(request, demo_sut, tmp_path_factory):
    """Re-assert quality-bundle's e2e_config with an explicit demo_sut dependency.

    The plugin fixture reads E2E_* env at first resolution; depending on demo_sut
    guarantees the stamping fixture has run first (fixture ordering alone does not:
    pytest may order the base_url -> app_env -> e2e_config chain ahead of session
    autouse fixtures).

    QUALITY_ARTIFACTS_DIR is redirected into a session tmp dir around load_config
    (plan §8: repo used read-only) and restored immediately after - the returned
    config snapshot keeps the tmp path, subprocesses scrub QUALITY_* anyway.
    """
    from quality_bundle.config import load_config
    previous = os.environ.get("QUALITY_ARTIFACTS_DIR")
    os.environ["QUALITY_ARTIFACTS_DIR"] = str(tmp_path_factory.mktemp("e2e-artifacts"))
    try:
        return load_config(request.config.getoption("--e2e-config"))
    finally:
        if previous is None:
            os.environ.pop("QUALITY_ARTIFACTS_DIR", None)
        else:
            os.environ["QUALITY_ARTIFACTS_DIR"] = previous


@pytest.fixture(scope="session")
def base_url(app_env):
    """Re-assert quality-bundle's base_url.

    The pytest-base-url plugin (pulled into the venv by a transitive dependency)
    also registers a session-scoped `base_url` fixture returning the --base-url
    option ('' when unset) and shadows the plugin fixture. Conftest fixtures
    outrank entry-point plugins, so this restores the documented chain
    base_url -> app_env -> e2e_config for everything under tests/e2e.
    """
    return app_env.base_url


@pytest.fixture
def fresh_app_env(monkeypatch, demo_sut, tmp_path):
    """Build a private ApplicationEnvironment from a monkeypatched env.

    The plugin's app_env/base_url fixtures are session-cached, so per-test env
    overrides (health path, unreachable URLs, unset credentials) cannot reach them;
    tests that need custom E2E_* values construct their own instance instead.
    """
    from quality_bundle.config import load_config
    from quality_bundle.environment import ApplicationEnvironment

    def build(base_url=demo_sut, extra_env=None):
        monkeypatch.delenv("E2E_BASE_URL", raising=False)
        if base_url:
            monkeypatch.setenv("E2E_BASE_URL", base_url)
        for key, value in (extra_env or {}).items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, str(value))
        monkeypatch.chdir(tmp_path)  # keep quality.toml resolution out of the repo
        return ApplicationEnvironment(load_config(None))

    return build


def _scrubbed_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items()
            if not key.startswith(("E2E_", "QUALITY_"))}


@pytest.fixture
def invoke_cli():
    def run(args, cwd, env_overrides=None, timeout=60):
        env = _scrubbed_env()
        env.update(env_overrides or {})
        return subprocess.run([sys.executable, "-m", "quality_bundle.main", *[str(a) for a in args]],
                              cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout)
    return run


@pytest.fixture
def invoke_bin():
    def run(script_name, args=(), cwd=".", env_overrides=None, timeout=60):
        env = _scrubbed_env()
        env.update(env_overrides or {})
        return subprocess.run(["bash", str(REPO_ROOT / "bin" / script_name), *[str(a) for a in args]],
                              cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout)
    return run


DEFAULT_TEST_BODY = 'def test_{suite}_health(api):\n    assert api.get("/health").status_code == 200'

PYTEST_INI = "[pytest]\n" + "markers:\n" + "".join(f"    {m}: {m} suite\n" for m in ALL_MARKERS)

# Target-project-side fixture: the pytest-base-url plugin (transitive dep of
# pytest-playwright, present in shared venvs) shadows quality-bundle's base_url
# fixture, so projects using the api fixture must re-assert it. Mirrors the same
# override our e2e conftest applies in-process.
INNER_CONFTEST = '''\
import pytest


@pytest.fixture(scope="session")
def base_url(app_env):
    return app_env.base_url
'''


def _with_marker(suite: str, body: str) -> str:
    """Stamp the suite marker so `-m <suite>` actually selects the generated tests."""
    if "pytestmark" in body:
        return body
    return f"import pytest\npytestmark = pytest.mark.{suite}\n\n\n{body}"


@pytest.fixture
def make_project(demo_sut):
    def build(tmp_path, suites, toml=None, name="proj") -> Path:
        root = tmp_path / name
        (root / "tests/e2e").mkdir(parents=True)
        cfg = toml if toml is not None else f'[app]\nbase_url = "{demo_sut}"\n\n[paths]\ntests = "tests/e2e"\n'
        (root / "quality.toml").write_text(cfg)
        (root / "pytest.ini").write_text(PYTEST_INI)
        (root / "conftest.py").write_text(INNER_CONFTEST)
        for suite, bodies in suites.items():
            directory = root / "tests/e2e" / suite
            directory.mkdir(parents=True, exist_ok=True)
            body = "\n\n".join(bodies) if bodies else DEFAULT_TEST_BODY.format(suite=suite)
            (directory / f"test_{suite}.py").write_text(_with_marker(suite, body) + "\n")
        return root
    return build


class ShimFactory:
    """Executable bash shims: log argv to $SHIM_LOG when set, then run the canned body."""

    def __init__(self, directory: Path):
        self.dir = directory

    def __call__(self, name, body_lines=()) -> Path:
        lines = ["#!/usr/bin/env bash",
                 'if [[ -n "${SHIM_LOG:-}" ]]; then printf \'%s\\n\' "$*" >>"$SHIM_LOG"; fi',
                 *body_lines, "exit 0"]
        path = self.dir / name
        path.write_text("\n".join(lines) + "\n")
        path.chmod(0o755)
        return path

    def podman(self, run_stdout="<id>", port_stdout="0.0.0.0:43123") -> Path:
        return self("podman", ["case \"${1:-}\" in",
                               f"  run) echo '{run_stdout}' ;;",
                               f"  port) echo '{port_stdout}' ;;",
                               "esac"])

    def docker(self, run_stdout="<id>") -> Path:
        return self("docker", ["case \"${1:-}\" in",
                               f"  run) echo '{run_stdout}' ;;",
                               "esac"])

    def hurl(self) -> Path:
        return self("hurl", ["exit 0"])

    def k6(self, exit_code=0) -> Path:
        return self("k6", [f"exit {exit_code}"])


@pytest.fixture(scope="session")
def _shims_root():
    # /tmp is mounted noexec in some environments; shims must live on an exec-allowed
    # filesystem, so they go to a session-unique dir under ~/.cache (never the repo).
    root = Path.home() / ".cache" / "quality-e2e-shims" / str(os.getpid())
    root.mkdir(parents=True, exist_ok=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def shim(_shims_root):
    return ShimFactory(Path(tempfile.mkdtemp(dir=_shims_root)))


# --- container-tier (T2) support -------------------------------------------------

_PODMAN_PROBE: dict[str, bool] = {}
SUT_IMAGE = "quality-bundle-e2e-sut:test"


def _podman_usable() -> bool:
    """podman works here: `podman info` exits 0 and user namespaces are available."""
    if "usable" not in _PODMAN_PROBE:
        try:
            info = subprocess.run(["podman", "info"], capture_output=True, timeout=30)
            userns = subprocess.run(["unshare", "--user", "true"], capture_output=True, timeout=15)
            _PODMAN_PROBE["usable"] = info.returncode == 0 and userns.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _PODMAN_PROBE["usable"] = False
    return _PODMAN_PROBE["usable"]


def _require_podman(request):
    if not _podman_usable():
        pytest.skip("podman is not usable in this environment (info/userns probe failed)")


@pytest.fixture(scope="session")
def podman_usable():
    return _podman_usable()


@pytest.fixture(scope="session")
def podman_service(request):
    """Rootless podman Docker-compatible API socket for Testcontainers-based rows."""
    _require_podman(request)
    runtime_dir = Path(tempfile.mkdtemp(prefix="podman-run-"))
    sock = runtime_dir / "podman" / "podman.sock"
    (runtime_dir / "podman").mkdir()
    service = subprocess.Popen(
        ["podman", "system", "service", "--time=0", f"unix://{sock}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = __import__("time").monotonic() + 30
    import time as _time
    while _time.monotonic() < deadline and not sock.exists():
        _time.sleep(0.2)
    if not sock.exists():
        service.terminate()
        pytest.skip("podman system service did not create its socket in time")
    yield runtime_dir
    service.terminate()
    try:
        service.wait(timeout=10)
    except subprocess.TimeoutExpired:
        service.kill()


@pytest.fixture(scope="session")
def sut_image(request):
    """Build tests/e2e/fixtures/container_sut as quality-bundle-e2e-sut:test."""
    _require_podman(request)
    context = Path(__file__).resolve().parent / "fixtures" / "container_sut"
    build = subprocess.run(["podman", "build", "-t", SUT_IMAGE, str(context)],
                           capture_output=True, text=True, timeout=600)
    if build.returncode != 0:
        pytest.skip(f"container SUT image build failed: {build.stderr[-300:]}")
    return SUT_IMAGE


@pytest.fixture(scope="session")
def toxiproxy_pulled(request):
    """Pull the toxiproxy image once, bounded; skip rows when the pull fails."""
    _require_podman(request)
    pull = subprocess.run(["podman", "pull", "ghcr.io/shopify/toxiproxy:2.12.0"],
                          capture_output=True, text=True, timeout=300)
    if pull.returncode != 0:
        pytest.skip(f"toxiproxy image pull failed: {pull.stderr[-200:]}")
    return "ghcr.io/shopify/toxiproxy:2.12.0"
