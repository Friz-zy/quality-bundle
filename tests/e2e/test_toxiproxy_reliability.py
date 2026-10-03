"""E2E-080/081: toxiproxy fixture lifecycle and reliability template journey (T2)."""
import shutil, subprocess
from pathlib import Path
import httpx, pytest
from conftest import _require_podman

REPO_ROOT = Path(__file__).resolve().parents[2]

RELIABILITY_BODY = ("import httpx, pytest\n"
                    "pytestmark = pytest.mark.reliability\n\n\n"
                    "def test_proxy_created(toxiproxy, e2e_base_url):\n"
                    "    created = httpx.post(toxiproxy.api_url + '/proxies', json={\n"
                    "        'name': 'sut',\n"
                    "        'listen': '0.0.0.0:8666',\n"
                    "        'upstream': e2e_base_url.split('//')[-1],\n"
                    "    }, timeout=10)\n"
                    "    assert created.status_code in (200, 201), created.text\n"
                    "    proxies = httpx.get(toxiproxy.api_url + '/proxies', timeout=10).json()\n"
                    "    assert 'sut' in proxies\n")


@pytest.mark.container
def test_e2e_080_toxiproxy_fixture_lifecycle(request, toxiproxy_pulled, tmp_path):
    _require_podman(request)  # ToxiproxyEnvironment publishes allocated host ports
    from quality_bundle.config import ReliabilityConfig
    from quality_bundle.reliability import ToxiproxyEnvironment
    with ToxiproxyEnvironment(ReliabilityConfig().toxiproxy_image) as env:
        assert env.api_url.startswith("http://")
        response = httpx.get(env.api_url + "/proxies", timeout=10)
        assert response.status_code == 200
        assert env.mapped_proxy_port() > 0
    names = subprocess.run(["podman", "ps", "-a", "--format", "{{.Names}}"],
                           capture_output=True, text=True, timeout=30).stdout.split()
    assert "e2e-toxiproxy" not in names  # container stopped on exit


@pytest.mark.container
def test_e2e_081_reliability_template_journey(request, invoke_cli, make_project, demo_sut,
                                               toxiproxy_pulled, tmp_path):
    _require_podman(request)
    root = make_project(tmp_path, {"reliability": [RELIABILITY_BODY]})
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "reliability"], cwd=root,
                   env_overrides={"QUALITY_ARTIFACTS_DIR": str(art)}, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (art / "reliability-junit.xml").exists()
