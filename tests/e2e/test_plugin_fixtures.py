"""E2E-028..035: plugin fixtures, polling and runtime-mode contract (T1)."""
import httpx, pytest

FAILING_BODY = "def test_cli_fail():\n    assert False\n"


def art_env(tmp_path):
    return {"QUALITY_ARTIFACTS_DIR": str(tmp_path / "artifacts")}


def test_e2e_028_plugin_fixtures_dogfood(demo_sut, e2e_config, e2e_base_url, base_url, api,
                                         artifacts_dir):
    from quality_bundle.config import E2EConfig
    assert isinstance(e2e_config, E2EConfig)
    assert e2e_base_url == demo_sut
    assert base_url == e2e_base_url  # legacy alias stays consistent
    assert artifacts_dir.is_dir()
    response = api.get("/api/data")
    assert response.status_code == 200
    assert response.json() == {"items": [1, 2, 3]}


COMPETING_CONFTEST = '''\
import pytest


@pytest.fixture(scope="session")
def base_url():
    """Simulates pytest-base-url's session-scoped shadowing fixture."""
    return "http://127.0.0.1:1"
'''


def test_competing_base_url_fixture_does_not_break_api(invoke_cli, make_project, demo_sut,
                                                       tmp_path):
    """Regression: a conftest-level `base_url` fixture (as co-installed
    pytest-base-url provides) must not shadow the base URL the framework's
    `api` fixture uses; `api` depends on the uniquely named `e2e_base_url`."""
    root = make_project(tmp_path, {"api": []})
    (root / "conftest.py").write_text(COMPETING_CONFTEST)
    r = invoke_cli(["run", "api"], cwd=root,
                   env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "artifacts" / "api-junit.xml").exists()


def test_e2e_029_health_polling_recovers_from_flap(demo_sut, fresh_app_env):
    httpx.get(f"{demo_sut}/_ctl/health?mode=flap", timeout=5)
    with fresh_app_env() as env:  # readiness predicate status<500 rides out 2x503
        assert env.base_url == demo_sut


def test_e2e_030_persistent_418_counts_as_ready(demo_sut, fresh_app_env):
    try:
        httpx.get(f"{demo_sut}/_ctl/health?code=418", timeout=5)
        with fresh_app_env() as env:
            assert env.base_url == demo_sut
    finally:
        httpx.get(f"{demo_sut}/_ctl/health?code=0", timeout=5)  # reset pin


def test_e2e_031_custom_health_path_honored(demo_sut, fresh_app_env):
    with fresh_app_env(extra_env={"E2E_HEALTH_PATH": "/ready"}) as env:
        assert env.base_url == demo_sut


def test_e2e_032_unreachable_base_url_times_out(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": []}, toml=(
        '[app]\nbase_url = "http://127.0.0.1:1"\nstartup_timeout = 1\n'))
    r = invoke_cli(["run", "cli"], cwd=root,
                   env_overrides=art_env(tmp_path), timeout=120)
    assert r.returncode == 1
    assert "Timed out waiting for readiness at http://127.0.0.1:1/health" in r.stdout


def test_e2e_033_cli_fixture_skips_when_unconfigured(request, e2e_config):
    assert e2e_config.app.cli is None
    with pytest.raises(pytest.skip.Exception) as exc:
        request.getfixturevalue("cli")
    assert "CLI is not configured" in str(exc.value)


def test_e2e_034_neither_base_url_nor_image_fails(demo_sut, fresh_app_env):
    env = fresh_app_env(base_url=None)
    with pytest.raises(RuntimeError, match="Configure app.base_url/E2E_BASE_URL or container.image/E2E_IMAGE"):
        env.__enter__()


def test_e2e_035_no_sut_log_in_base_url_mode(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": []})
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "cli"], cwd=root,
                   env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (art / "cli-junit.xml").exists()
    assert not (art / "sut.log").exists()
