"""E2E-005..011: quality list/plan contract (T1)."""
import os, shutil
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_e2e_005_no_subcommand_usage_exit_2(invoke_cli, tmp_path):
    r = invoke_cli([], cwd=tmp_path)
    assert r.returncode == 2
    assert "usage:" in r.stderr


def test_e2e_005_help_lists_all_commands_and_suites(invoke_cli, tmp_path):
    r = invoke_cli(["--help"], cwd=tmp_path)
    assert r.returncode == 0
    for token in ["run", "plan", "list", "doctor", "test", "cli", "api", "workflow", "bdd",
                  "ui", "accessibility", "mobile", "grpc", "realtime", "compatibility",
                  "reliability", "contract", "container", "hurl", "schema", "performance",
                  "security"]:
        assert token in r.stdout


def test_e2e_006_list_one_per_line(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": [], "api": []})
    r = invoke_cli(["list"], cwd=root)
    assert r.returncode == 0
    assert r.stdout.splitlines() == ["cli", "api"]
    assert "\\n" not in r.stdout


def test_e2e_007_list_empty_discovery_blank_line(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {})
    r = invoke_cli(["list"], cwd=root)
    assert r.returncode == 0
    assert r.stdout == "\n"  # pinned actual behavior: print("") emits exactly one newline


@pytest.mark.parametrize("mode", ["env", "toml"])
def test_e2e_008_exclude_suites(invoke_cli, make_project, tmp_path, mode):
    if mode == "env":
        root = make_project(tmp_path, {"cli": [], "api": []})
        r = invoke_cli(["list"], cwd=root, env_overrides={"QUALITY_EXCLUDE_SUITES": "api"})
    else:
        root = make_project(tmp_path, {"cli": [], "api": []},
                            toml='[app]\nbase_url = "http://x"\n\n[quality]\nexclude_suites = ["api"]\n')
        r = invoke_cli(["list"], cwd=root)
    assert r.returncode == 0
    assert r.stdout.splitlines() == ["cli"]


@pytest.mark.parametrize("with_hurl", [
    False,
    pytest.param(True, marks=pytest.mark.skipif(
        shutil.which("hurl") is not None,
        reason="hurl is installed; the absent-binary error path cannot be exercised")),
])
def test_e2e_009_plan_commands_and_hurl_error(invoke_cli, make_project, tmp_path, with_hurl):
    root = make_project(tmp_path, {"cli": [], "api": []})
    if with_hurl:
        (root / "tests/e2e/hurl").mkdir()
        (root / "tests/e2e/hurl/health.hurl").write_text("GET http://127.0.0.1/health\n")
    r = invoke_cli(["plan"], cwd=root)
    assert r.returncode == 0
    assert r.stdout.splitlines()[0] == "Suites: cli, api" + (", hurl" if with_hurl else "")
    assert "-m cli" in r.stdout and "-m api" in r.stdout
    if with_hurl:
        assert "hurl: Hurl is not installed" in r.stderr
        assert "hurl --test" not in r.stdout
    else:
        assert r.stderr == ""


def test_e2e_010_plan_creates_artifacts_dir_no_summary(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": []})
    art = tmp_path / "nonexistent-artifacts"
    r = invoke_cli(["plan"], cwd=root, env_overrides={"QUALITY_ARTIFACTS_DIR": str(art)})
    assert r.returncode == 0
    assert art.is_dir()
    assert not (art / "summary.json").exists()


def test_e2e_011_plan_schema_local_openapi(invoke_cli, shim, make_project, tmp_path):
    shim("schemathesis")  # post-F13 the argv resolves via which(); plan mode never executes it
    root = make_project(tmp_path, {"cli": []}, toml=(
        '[app]\nbase_url = "http://127.0.0.1:5"\n\n[paths]\ntests = "tests/e2e"\n'
        'openapi = "openapi/mini.yaml"\n'))
    (root / "openapi").mkdir()
    shutil.copy(REPO_ROOT / "tests/e2e/fixtures/openapi/mini.yaml", root / "openapi/mini.yaml")
    r = invoke_cli(["plan", "schema"], cwd=root,
                   env_overrides={"PATH": f"{shim.dir}:{os.environ['PATH']}"})
    assert r.returncode == 0
    assert "schemathesis run" in r.stdout  # post-F13: console script, not python -m
    assert "--report-junit-path" in r.stdout
    assert "--url http://127.0.0.1:5" in r.stdout
