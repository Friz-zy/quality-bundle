"""E2E-069/070/071: bin/compose-test wrapper contract (T1, shimmed engines)."""
import os
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _shim_env(shim, tmp_path, engine):
    shim(engine, ['case "${1:-}" in',
                  "  compose) shift; echo shimmed ;;",
                  "  *) exit 0 ;;",
                  "esac"])
    return {"PATH": f"{shim.dir}:{os.environ['PATH']}", "SHIM_LOG": str(tmp_path / "shim.log"),
            "E2E_COMPOSE_ENGINE": engine}


def test_e2e_069_compose_test_unknown_engine(invoke_bin, tmp_path):
    r = invoke_bin("compose-test", cwd=tmp_path, env_overrides={"E2E_COMPOSE_ENGINE": "nerdctl"})
    assert r.returncode == 2
    assert "error: E2E_COMPOSE_ENGINE must be docker or podman" in r.stderr


def test_e2e_070_compose_test_default_file(invoke_bin, shim, tmp_path):
    assert (REPO_ROOT / "compose.quality.yml").is_file()  # post-F7 default exists
    env = _shim_env(shim, tmp_path, "docker")
    r = invoke_bin("compose-test", cwd=tmp_path, env_overrides=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    argv = (tmp_path / "shim.log").read_text().strip().splitlines()[-1].split()
    assert argv[:3] == ["compose", "-f", f"{REPO_ROOT}/compose.quality.yml"]
    assert argv[3:6] == ["run", "--rm", "e2e"]


@pytest.mark.parametrize("engine", ["docker", "podman"])
def test_e2e_071_compose_test_engine_construction(invoke_bin, shim, tmp_path, engine):
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text("services: {}\n")
    env = _shim_env(shim, tmp_path, engine)
    env["E2E_COMPOSE_FILE"] = str(compose_file)
    r = invoke_bin("compose-test", ["quality", "run", "cli"], cwd=tmp_path,
                   env_overrides=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    argv = (tmp_path / "shim.log").read_text().strip().splitlines()[-1].split()
    assert argv == ["compose", "-f", str(compose_file), "run", "--rm", "e2e",
                    "quality", "run", "cli"]
