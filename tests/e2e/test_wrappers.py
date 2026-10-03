"""E2E-051 discovery channels matrix, E2E-052/053 zap guards, E2E-054..058 hurl/k6 wrappers."""
import os, shutil, sys
from pathlib import Path
import pytest


def test_e2e_051_discovery_workflows_alias(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"workflows": []})
    assert invoke_cli(["list"], cwd=root).stdout.splitlines() == ["workflow"]


@pytest.mark.parametrize("suite", ["bdd", "ui", "mobile", "grpc", "realtime",
                                   "compatibility", "reliability", "contract"])
def test_e2e_051_discovery_same_name_channels(invoke_cli, make_project, tmp_path, suite):
    root = make_project(tmp_path, {suite: []})
    assert invoke_cli(["list"], cwd=root).stdout.splitlines() == [suite]


def test_e2e_051_discovery_containers_alias(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"containers": []})
    assert invoke_cli(["list"], cwd=root).stdout.splitlines() == ["container"]


def test_e2e_051_discovery_security_bare_dir(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {})
    (root / "tests/e2e/security").mkdir()  # bare dir: existence alone discovers security
    assert invoke_cli(["list"], cwd=root).stdout.splitlines() == ["security"]


def test_e2e_051_discovery_hurl_glob(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {}, toml='[paths]\ntests = "tests/e2e"\nhurl = "tests/e2e/hurl"\n')
    hurl = root / "tests/e2e/hurl"
    hurl.mkdir()
    (hurl / "health.hurl").write_text("GET http://127.0.0.1/health\n")
    assert invoke_cli(["list"], cwd=root).stdout.splitlines() == ["hurl"]


def test_e2e_051_discovery_openapi_schema(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {}, toml='[paths]\ntests = "tests/e2e"\nopenapi = "openapi/mini.yaml"\n')
    (root / "openapi").mkdir()
    shutil.copy(Path(__file__).resolve().parents[2] / "tests/e2e/fixtures/openapi/mini.yaml",
                root / "openapi/mini.yaml")
    assert invoke_cli(["list"], cwd=root).stdout.splitlines() == ["schema"]


def test_e2e_051_discovery_empty_cli_dir_negative(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {})
    (root / "tests/e2e/cli").mkdir()  # bare dir, no test_*.py -> not discovered
    r = invoke_cli(["list"], cwd=root)
    assert r.returncode == 0
    assert r.stdout == "\n"


def test_e2e_052_zap_requires_base_url(invoke_bin, tmp_path):
    r = invoke_bin("zap", cwd=tmp_path)  # scrubbed: no E2E_BASE_URL
    assert r.returncode == 1
    assert "E2E_BASE_URL is required" in r.stderr
    # DEVIATION from plan E2E-052 row ("zap dir created"): the guard in bin/zap line 4
    # fires before the mkdir on line 5, so no directory is created. Pinned as actual.
    assert not (tmp_path / "artifacts/quality/zap").exists()


@pytest.mark.parametrize("image", [None, "zap/custom:1"])
def test_e2e_053_zap_docker_argv_via_shim(invoke_bin, shim, tmp_path, image):
    shim.docker()  # logs argv to $SHIM_LOG, exits 0
    log = tmp_path / "shim.log"
    env = {"PATH": f"{shim.dir}:{os.environ['PATH']}",
           "E2E_BASE_URL": "http://127.0.0.1:1",
           "SHIM_LOG": str(log)}
    if image:
        env["E2E_ZAP_IMAGE"] = image
    r = invoke_bin("zap", cwd=tmp_path, env_overrides=env, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    argv = log.read_text().strip().splitlines()[-1].split()
    assert argv[:4] == ["run", "--rm", "--network", "host"]
    assert argv[4] == "-v"
    assert argv[5] == f"{tmp_path}/artifacts/quality/zap:/zap/wrk/:rw"
    assert argv[6] == (image or "ghcr.io/zaproxy/zaproxy:stable")
    assert argv[7:] == ["zap-baseline.py", "-t", "http://127.0.0.1:1",
                        "-J", "zap.json", "-r", "zap.html"]


def test_e2e_054_hurl_plan_sorted_files_and_variable(invoke_cli, shim, make_project, tmp_path):
    shim.hurl()  # argv logged, exit 0; external_command only needs which("hurl")
    hurl = tmp_path / "hurlfiles"
    hurl.mkdir()
    (hurl / "b.hurl").write_text("GET http://x/b\n")
    (hurl / "a.hurl").write_text("GET http://x/a\n")
    root = make_project(tmp_path, {"cli": []}, toml=(
        '[app]\nbase_url = "http://127.0.0.1:9/"\n\n'
        f'[paths]\ntests = "tests/e2e"\nhurl = "{hurl}"\n'))
    r = invoke_cli(["plan", "hurl"], cwd=root,
                   env_overrides={"PATH": f"{shim.dir}:{os.environ['PATH']}"})
    assert r.returncode == 0
    line = [l for l in r.stdout.splitlines() if l.startswith("hurl")][0]
    assert "--test" in line
    assert "--variable base_url=http://127.0.0.1:9" in line  # trailing slash rstripped
    assert "--report-junit" in line
    assert line.index("a.hurl") < line.index("b.hurl")  # sorted


@pytest.mark.slow
def test_e2e_056_schemathesis_real_run(invoke_cli, make_project, demo_sut, tmp_path):
    pytest.importorskip("schemathesis")
    root = make_project(tmp_path, {"cli": []}, toml=(
        f'[app]\nbase_url = "{demo_sut}"\n\n[paths]\ntests = "tests/e2e"\n'
        'openapi = "openapi/mini.yaml"\n'))
    (root / "openapi").mkdir()
    shutil.copy(Path(__file__).resolve().parents[2] / "tests/e2e/fixtures/openapi/mini.yaml",
                root / "openapi/mini.yaml")
    art = tmp_path / "artifacts"
    # F13 resolves the schemathesis console script via shutil.which in the SUBPROCESS,
    # so the venv scripts dir must be on the child PATH regardless of how pytest itself
    # was launched (`uv run pytest` vs bare `.venv/bin/python -m pytest`)
    r = invoke_cli(["schema"], cwd=root,
                   env_overrides={"QUALITY_ARTIFACTS_DIR": str(art),
                                  "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}"},
                   timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (art / "schema-junit.xml").exists()


@pytest.mark.slow
def test_e2e_055_hurl_real_run(invoke_cli, shim, make_project, demo_sut, tmp_path):
    if shutil.which("hurl") is None:
        pytest.skip("hurl is not installed")
    hurl = tmp_path / "hurlfiles"
    hurl.mkdir()
    (hurl / "health.hurl").write_text("GET {{base_url}}/health\nHTTP 200\n")
    root = make_project(tmp_path, {"cli": []}, toml=(
        f'[app]\nbase_url = "{demo_sut}"\n\n[paths]\ntests = "tests/e2e"\nhurl = "{hurl}"\n'))
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "hurl"], cwd=root,
                   env_overrides={"QUALITY_ARTIFACTS_DIR": str(art)}, timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (art / "hurl-junit.xml").exists()


@pytest.mark.skipif(shutil.which("k6") is not None,
                    reason="k6 is installed; the absent-binary error path cannot be exercised")
def test_e2e_057_k6_missing_binary_exit_127(invoke_bin, tmp_path):
    r = invoke_bin("k6", ["run", "script.js"], cwd=tmp_path)  # scrubbed: no shim on PATH
    assert r.returncode == 127
    assert "error: k6 is not installed" in r.stderr


def test_e2e_058_k6_shim_exit_code_passthrough(invoke_bin, shim, tmp_path):
    shim.k6(exit_code=7)
    log = tmp_path / "shim.log"
    r = invoke_bin("k6", ["run", "script.js"], cwd=tmp_path,
                   env_overrides={"PATH": f"{shim.dir}:{os.environ['PATH']}",
                                  "SHIM_LOG": str(log)})
    assert r.returncode == 7
    assert log.read_text().strip().splitlines()[-1] == "run script.js"
