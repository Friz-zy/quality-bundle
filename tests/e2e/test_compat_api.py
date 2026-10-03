"""E2E-082..085: compatibility artifact API and template journey (all T1: fake CLIs and
artifacts only, no container runtime)."""
import inspect, os, subprocess
from pathlib import Path
import pytest
from quality_bundle.compatibility import artifacts_from_env, run_upgrade_command

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("versions,env,expected", [
    (("1.4.0",), {"E2E_COMPAT_1_4_0_CLI": "/tmp/cli-140", "E2E_COMPAT_1_4_0_IMAGE": "img:1.4.0"},
     [("1.4.0", "/tmp/cli-140", "img:1.4.0")]),
    (("2-0-beta",), {"E2E_COMPAT_2_0_BETA_IMAGE": "img:2b"}, [("2-0-beta", None, "img:2b")]),
    (("3.0",), {}, [("3.0", None, None)]),
])
def test_e2e_082_artifacts_from_env_mapping(monkeypatch, versions, env, expected):
    for key in list(os.environ):
        if key.startswith("E2E_COMPAT_"):
            monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    artifacts = artifacts_from_env(versions)
    assert [(a.version, a.cli, a.image) for a in artifacts] == expected


def test_e2e_083_compatibility_artifacts_fixture(request, e2e_config):
    # e2e_config is session-cached, so per-test env overrides cannot reach it; pin the
    # fixture's contract instead: it is exactly artifacts_from_env over the resolved
    # config versions (env-driven mapping is covered by E2E-082).
    from quality_bundle.compatibility import artifacts_from_env
    expected = artifacts_from_env(e2e_config.compatibility.versions)
    assert request.getfixturevalue("compatibility_artifacts") == expected


def test_e2e_084_run_upgrade_command_formats(tmp_path, monkeypatch):
    # the plan's example template `echo {old}->{new}` contains a shell REDIRECTION
    # (`->2.0` writes a file), so the faithful pin of "formatting works" is the
    # side-effect file, not stdout
    monkeypatch.chdir(tmp_path)
    result = run_upgrade_command("echo {old}->{new}", "1.4.0", "2.0")
    assert result.returncode == 0
    assert result.stdout == ""
    assert (tmp_path / "2.0").read_text() == "1.4.0-\n"


def test_e2e_085_compatibility_template_journey(invoke_cli, make_project, tmp_path):
    # template only needs configured artifacts; the CLI-resolved path needs no runtime
    shim = tmp_path / "compat-cli-1.4.0"
    shim.write_text("#!/usr/bin/env bash\necho 1.4.0\n")
    shim.chmod(0o755)
    root = make_project(tmp_path, {"compatibility": [
        Path(REPO_ROOT / "templates/tests/compatibility/test_compatibility.py").read_text()]})
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "compatibility"], cwd=root,
                   env_overrides={"E2E_COMPAT_VERSIONS": "1.4.0",
                                  "E2E_COMPAT_1_4_0_CLI": str(shim),
                                  "QUALITY_ARTIFACTS_DIR": str(art)},
                   timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    data = (art / "summary.json")
    assert data.exists()
    assert '"suite": "compatibility"' in data.read_text()


def test_e2e_085_is_runtime_independent():
    # Tier pin: E2E-085 drives the template journey with fake CLIs and generated
    # artifacts only, so it must never be gated on (or marked as needing) a
    # container runtime; its fixtures stay in the demo-SUT/CLI tier.
    runtime_fixtures = {"container_runtime", "testcontainers_podman", "podman_usable",
                        "podman_service", "sut_image", "toxiproxy_pulled"}
    marks = {m.name for m in getattr(test_e2e_085_compatibility_template_journey, "pytestmark", ())}
    fixtures = set(inspect.signature(test_e2e_085_compatibility_template_journey).parameters)
    assert "container" not in marks
    assert not fixtures & runtime_fixtures
