"""E2E-074/075: E2E_IMAGE journey through the native Podman runtime (T2)."""
import json, subprocess
import pytest
from conftest import _require_podman, SUT_IMAGE

APP_BODY = ("def test_container_health(api):\n"
            "    response = api.get('/health')\n"
            "    assert response.status_code == 200\n"
            "    assert response.json()['status'] == 'ok'\n")
APP_MSG_BODY = ("def test_container_app_msg(api):\n"
                "    response = api.get('/health')\n"
                "    assert response.status_code == 200\n"
                "    assert 'hello-selftest' in response.json()['app_msg']\n")


def _container_names():
    return subprocess.run(["podman", "ps", "-a", "--format", "{{.Names}}"],
                          capture_output=True, text=True, timeout=30).stdout.split()


@pytest.mark.container
def test_e2e_074_e2e_image_journey(request, invoke_cli, make_project, sut_image, tmp_path):
    _require_podman(request)  # ApplicationEnvironment publishes an allocated host port
    # No app.base_url in the toml: the E2E_IMAGE env must drive the container path.
    root = make_project(tmp_path, {"api": [APP_BODY]},
                        toml='[paths]\ntests = "tests/e2e"\n')
    art = tmp_path / "artifacts"
    env = {"E2E_IMAGE": sut_image, "QUALITY_ARTIFACTS_DIR": str(art)}
    r = invoke_cli(["run", "api"], cwd=root, env_overrides=env, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    sut_log = art / "sut.log"
    assert sut_log.exists() and sut_log.stat().st_size > 0
    assert not [n for n in _container_names() if n.startswith("e2e-sut-")]
    data = json.loads((art / "summary.json").read_text())
    assert data["status"] == "passed"
    # sequential re-run works (container cleaned up properly)
    r2 = invoke_cli(["run", "api"], cwd=root, env_overrides=env, timeout=600)
    assert r2.returncode == 0, r2.stdout + r2.stderr


@pytest.mark.container
def test_e2e_075_e2e_image_app_env_reaches_sut(request, invoke_cli, make_project, sut_image,
                                               tmp_path):
    _require_podman(request)
    root = make_project(tmp_path, {"api": [APP_MSG_BODY]},
                        toml='[paths]\ntests = "tests/e2e"\n')
    art = tmp_path / "artifacts"
    env = {"E2E_IMAGE": sut_image, "E2E_APP_ENV_APP_MSG": "hello-selftest",
           "QUALITY_ARTIFACTS_DIR": str(art)}
    r = invoke_cli(["run", "api"], cwd=root, env_overrides=env, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
