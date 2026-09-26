import httpx,pytest
from pathlib import Path
from .config import load_config
from .cli_runner import CLI
from .environment import ApplicationEnvironment
def pytest_addoption(parser):parser.getgroup("quality-bundle").addoption("--e2e-config",default=None)
@pytest.fixture(scope="session")
def e2e_config(request):return load_config(request.config.getoption("--e2e-config"))
@pytest.fixture(scope="session")
def artifacts_dir(e2e_config):
    p=Path(e2e_config.paths.artifacts);p.mkdir(parents=True,exist_ok=True);return p
@pytest.fixture(scope="session")
def app_env(e2e_config):
    with ApplicationEnvironment(e2e_config) as env:yield env
@pytest.fixture(scope="session")
def base_url(app_env):return app_env.base_url
@pytest.fixture
def api(base_url):
    with httpx.Client(base_url=base_url.rstrip("/"),timeout=10) as c:yield c
@pytest.fixture(scope="session")
def cli(e2e_config):
    if not e2e_config.app.cli:pytest.skip("CLI is not configured")
    return CLI(e2e_config.app.cli)

from .compatibility import artifacts_from_env
from .reliability import ToxiproxyEnvironment

@pytest.fixture(scope="session")
def compatibility_artifacts(e2e_config):
    return artifacts_from_env(e2e_config.compatibility.versions)

@pytest.fixture(scope="session")
def toxiproxy(e2e_config):
    with ToxiproxyEnvironment(e2e_config.reliability.toxiproxy_image) as env:
        yield env


from .runtime import runtime_from_environment
from .testcontainers_runtime import configure_testcontainers_for_podman

@pytest.fixture(scope="session")
def container_runtime():
    """Native Podman CLI runtime for low-level lifecycle/fault operations."""
    return runtime_from_environment()

@pytest.fixture(scope="session")
def testcontainers_podman():
    """Configure Testcontainers to use the rootless Podman Docker-compatible API."""
    return configure_testcontainers_for_podman()
