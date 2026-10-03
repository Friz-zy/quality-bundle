"""E2E-012..016 and 018..025: quality run and CLI passthrough contract (T1).

Artifact convention: QUALITY_ARTIFACTS_DIR points at an absolute tmp dir; summary.json
and <suite>-junit.xml land DIRECTLY under it (verified behavior of write_summary +
pytest_command).
"""
import json, re, shutil
import pytest

FAILING_BODY = "def test_cli_fail():\n    assert False\n"
CLI_TWO = ("def test_health(api):\n"
           "    assert api.get('/health').status_code == 200\n\n"
           "def test_other(api):\n"
           "    assert api.get('/api/data').status_code == 200\n")
BDD_EXTRAS = ("import os\nimport pytest\npytestmark = pytest.mark.bdd\n"
              "def test_extras():\n"
              "    assert os.environ.get('QUALITY_EXTRAS') == 'bdd'\n")
NO_EXTRAS = ("import os\n"
             "def test_no_extras():\n"
             "    assert os.environ.get('QUALITY_EXTRAS') is None\n")


def art_env(tmp_path):
    return {"QUALITY_ARTIFACTS_DIR": str(tmp_path / "artifacts")}


def summary(art):
    return json.loads((art / "summary.json").read_text())


def test_e2e_012_run_happy_path(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": [], "api": []})
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "cli", "api"], cwd=root, env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Suites: cli, api" in r.stdout
    assert "-m cli" in r.stdout and "-m api" in r.stdout and "--junitxml" in r.stdout
    assert (art / "cli-junit.xml").exists() and (art / "api-junit.xml").exists()
    data = summary(art)
    assert set(data) == {"status", "suites", "totals"}
    assert data["status"] == "passed"
    assert [s["suite"] for s in data["suites"]] == ["cli", "api"]
    assert all(s["exit_code"] == 0 and s["status"] == "passed" for s in data["suites"])
    assert set(data["suites"][0]) == {"suite", "command", "exit_code", "duration_seconds", "status"}
    totals = data["totals"]
    assert set(totals) == {"suites", "passed", "failed", "duration_seconds"}
    assert totals["suites"] == 2 and totals["passed"] == 2 and totals["failed"] == 0
    assert totals["duration_seconds"] > 0


def test_e2e_013_run_failing_suite(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": [FAILING_BODY], "api": []})
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "cli", "api"], cwd=root, env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 1
    assert "-m cli" in r.stdout and "-m api" in r.stdout  # fail_fast off: both ran
    data = summary(art)
    assert data["status"] == "failed"
    t = data["totals"]
    assert t["suites"] == 2 and t["passed"] == 1 and t["failed"] == 1
    assert (art / "cli-junit.xml").exists() and (art / "api-junit.xml").exists()


def test_e2e_014_summary_header_and_row_format(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": []})
    r = invoke_cli(["run", "cli"], cwd=root, env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0
    assert "\nQuality summary" in r.stdout
    assert re.findall(r"^cli +passed +\d+\.\d{3}s$", r.stdout, re.M)


def test_e2e_015_empty_discovery_writes_empty_summary(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {})
    art = tmp_path / "artifacts"
    r = invoke_cli(["run"], cwd=root, env_overrides=art_env(tmp_path))
    assert r.returncode == 0
    assert "No suites discovered." in r.stdout
    data = summary(art)
    assert data["status"] == "passed"
    assert data["suites"] == []
    assert data["totals"]["suites"] == 0


def test_e2e_016_unknown_suite_exit_2(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": []})
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "bogus"], cwd=root, env_overrides=art_env(tmp_path))
    assert r.returncode == 2
    assert "error: Unknown suites: bogus" in r.stderr
    assert not art.exists()


def test_e2e_018_single_suite_remainder_passthrough(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": [CLI_TWO]})
    r = invoke_cli(["cli", "-k", "health"], cwd=root,
                   env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "-m cli" in r.stdout and "-k health" in r.stdout
    assert "1 passed" in r.stdout and "1 deselected" in r.stdout


@pytest.mark.skipif(shutil.which("hurl") is not None,
                    reason="hurl is installed; the absent-binary error path cannot be exercised")
def test_e2e_019_hurl_without_binary_exit_2(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": []})
    r = invoke_cli(["hurl"], cwd=root)
    assert r.returncode == 2
    assert r.stderr.strip() == "error: Hurl is not installed"


def test_e2e_020_schema_unconfigured_exit_2(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": []})
    r = invoke_cli(["schema"], cwd=root)
    assert r.returncode == 2
    assert "error: OpenAPI schema is not configured" in r.stderr


@pytest.mark.parametrize("with_config", [False, True])
def test_e2e_021_test_subcommand_e2e_config_flag(invoke_cli, make_project, tmp_path, with_config):
    root = make_project(tmp_path, {"cli": [CLI_TWO]})
    args = (["--config", str(root / "quality.toml")] if with_config else []) + ["test", "-k", "health"]
    r = invoke_cli(args, cwd=root, env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    if with_config:
        assert "--e2e-config" in r.stdout and str(root / "quality.toml") in r.stdout
    else:
        assert "--e2e-config" not in r.stdout
    assert "1 passed" in r.stdout


@pytest.mark.parametrize("mode", ["env", "toml", "off"])
def test_e2e_022_fail_fast(invoke_cli, make_project, demo_sut, tmp_path, mode):
    toml = None
    overrides = art_env(tmp_path)
    if mode == "env":
        overrides["QUALITY_FAIL_FAST"] = "1"
    elif mode == "toml":
        # base_url must stay: the api suite body uses the api fixture
        toml = f'[app]\nbase_url = "{demo_sut}"\n\n[quality]\nfail_fast = true\n'
    root = make_project(tmp_path, {"cli": [FAILING_BODY], "api": []}, toml=toml)
    r = invoke_cli(["run", "cli", "api"], cwd=root, env_overrides=overrides, timeout=240)
    assert r.returncode == 1
    data = summary(tmp_path / "artifacts")
    names = [s["suite"] for s in data["suites"]]
    if mode == "off":
        assert names == ["cli", "api"]
        assert "-m api" in r.stdout
    else:
        assert names == ["cli"]
        assert "-m api" not in r.stdout


@pytest.mark.parametrize("mode", ["env", "toml"])
def test_e2e_023_parallel_plan_and_run(invoke_cli, make_project, demo_sut, tmp_path, mode):
    toml = None
    overrides = art_env(tmp_path)
    if mode == "env":
        overrides["QUALITY_PARALLEL"] = "1"
    else:
        toml = f'[app]\nbase_url = "{demo_sut}"\n\n[quality]\nparallel = true\n'
    root = make_project(tmp_path, {"cli": [], "api": []}, toml=toml)
    p = invoke_cli(["plan"], cwd=root, env_overrides=overrides)
    assert p.returncode == 0
    assert "-n auto" in p.stdout
    r = invoke_cli(["run"], cwd=root, env_overrides=overrides, timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    data = summary(tmp_path / "artifacts")
    assert data["status"] == "passed" and data["totals"]["passed"] == 2


@pytest.mark.parametrize("mode", ["no_junit", "no_json"])
def test_e2e_024_artifact_toggles(invoke_cli, make_project, demo_sut, tmp_path, mode):
    extra = "junit = false" if mode == "no_junit" else "json_summary = false"
    toml = f'[app]\nbase_url = "{demo_sut}"\n\n[quality]\n{extra}\n'
    root = make_project(tmp_path, {"cli": []}, toml=toml)
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "cli"], cwd=root, env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    if mode == "no_junit":
        assert list(art.glob("*-junit.xml")) == []
        assert (art / "summary.json").exists()
    else:
        assert (art / "cli-junit.xml").exists()
        assert not (art / "summary.json").exists()


def test_e2e_025_extras_gated_for_bdd(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"bdd": [BDD_EXTRAS]})
    r = invoke_cli(["run", "bdd"], cwd=root, env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr


def test_e2e_025_no_extras_for_cli(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": [NO_EXTRAS]})
    r = invoke_cli(["run", "cli"], cwd=root, env_overrides=art_env(tmp_path), timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
