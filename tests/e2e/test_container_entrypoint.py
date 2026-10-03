"""E2E-067/068/076: nested-podman entrypoint contract (T2).

containers/entrypoint.sh creates $E2E_WORKSPACE_DIR/artifacts/quality (default
/workspace) and copies rootless config from $E2E_KIT_ROOT (default
/opt/quality-bundle), so the tests redirect the workspace to a tmp dir and use
the repository root as the kit root (E2E-SELFTEST-PLAN §11). No runtime socket
is needed: E2E-068 disables the service and E2E-076 forces its failure.
"""
import os, subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "containers" / "entrypoint.sh"


def _run_entrypoint(tmp_path, mode, extra_env):
    xdg = tmp_path / "xdg"
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"),
           "E2E_PODMAN_MODE": mode, "E2E_PODMAN_SERVICE": extra_env.pop("E2E_PODMAN_SERVICE", ""),
           "E2E_WORKSPACE_DIR": str(tmp_path / "workspace"), "E2E_KIT_ROOT": str(REPO_ROOT),
           "XDG_RUNTIME_DIR": str(xdg / "run"), "XDG_CONFIG_HOME": str(xdg / "config"),
           "XDG_DATA_HOME": str(xdg / "data"), **{k: v for k, v in extra_env.items() if v}}
    return subprocess.run(["bash", str(ENTRYPOINT), "true"], env=env,
                          capture_output=True, text=True, timeout=60)


@pytest.mark.container
def test_e2e_067_entrypoint_invalid_mode_exit_2(tmp_path):
    r = _run_entrypoint(tmp_path, "bogus", {})
    assert r.returncode == 2
    assert "error: E2E_PODMAN_MODE must be restricted or standard" in r.stderr


@pytest.mark.container
def test_e2e_068_entrypoint_service_skipped(tmp_path):
    xdg_run = tmp_path / "xdg" / "run"
    r = _run_entrypoint(tmp_path, "restricted", {"E2E_PODMAN_SERVICE": "0"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (xdg_run / "podman" / "podman.sock").exists()
    assert (tmp_path / "workspace" / "artifacts" / "quality").is_dir()


@pytest.mark.container
def test_e2e_076_entrypoint_required_service_fails_closed(tmp_path, shim):
    # a podman that cannot start a service -> required mode must fail closed (exit 1);
    # the shim dir is prepended so the entrypoint's other commands stay resolvable
    podman = shim("podman", ["exit 1"])
    r = _run_entrypoint(tmp_path, "restricted",
                        {"E2E_PODMAN_SERVICE": "1",
                         "PATH": f"{podman.parent}:{os.environ['PATH']}"})
    assert r.returncode == 1
    assert "error: Podman API socket did not start" in r.stderr
