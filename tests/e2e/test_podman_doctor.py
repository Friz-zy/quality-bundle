"""E2E-072: bin/podman-doctor full pass (T2) plus bounded-wrapper shim coverage.

Shim rows need no image pulls and no real podman: they cover the bounded
E2E_PODMAN_TIMEOUT wrapper, the fail-closed behavior without `timeout`, and the
port publishing probe's bridge-network argv (`--network podman`, matching
PodmanRuntime's publishing path) plus its host:port mapping validation.
"""
import os, shutil, subprocess
from pathlib import Path
import pytest

from conftest import _require_podman

DOCTOR = Path(__file__).resolve().parents[2] / "bin" / "podman-doctor"


@pytest.mark.container
def test_e2e_072_podman_doctor_full_pass(request, tmp_path):
    _require_podman(request)  # the doctor's port probe publishes an allocated port
    r = subprocess.run(["bash", str(DOCTOR)], cwd=tmp_path,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS: container run" in r.stdout
    assert "PASS: port publishing" in r.stdout
    assert "PASS: volume" in r.stdout


# --- shim rows: fast, no image pulls, no real podman -----------------------------

def _install_podman_shim(shim, port_file, port_case):
    """Doctor-aware podman shim with canned output per subcommand.

    A `run -d` invocation parses the published host port from its `-p
    <hostport>:<containerport>` argv and records it, so `port` can echo a
    mapping consistent with what the doctor actually asked to publish.
    """
    shim("podman", [
        'case "${1:-}" in',
        '  version|info) exit 0 ;;',
        '  run)',
        '    case " $* " in',
        '      *" -d "*)',
        '        prev=""',
        '        for a in "$@"; do',
        '          if [[ "$prev" == "-p" ]]; then printf \'%s\\n\' "${a%%:*}" >' + str(port_file) + '; fi',
        '          prev="$a"',
        '        done',
        '        echo doctor-shim-cid ;;',
        '      *"e2e-doctor"*) echo ok ;;',
        '      *) echo nested-podman-ok ;;',
        '    esac ;;',
        '  port) ' + port_case + ' ;;',
        '  inspect) echo true ;;',
        '  *) exit 0 ;;',
        'esac',
    ])


def test_e2e_072_shim_full_pass_publishes_on_bridge_network(invoke_bin, shim, tmp_path):
    """Happy path via shims: the port probe's `run -d` argv carries `--network
    podman` (the same bridge network PodmanRuntime uses when publishing) with the
    explicitly allocated host port, and the doctor reports a real host:port pair."""
    port_file = tmp_path / "doctor_shim_port"
    _install_podman_shim(shim, port_file, port_case=f'echo "0.0.0.0:$(cat {port_file})"')
    log = tmp_path / "shim.log"
    r = invoke_bin("podman-doctor", cwd=tmp_path, env_overrides={
        "PATH": f"{shim.dir}:{os.environ['PATH']}",
        "SHIM_LOG": str(log)})
    assert r.returncode == 0, r.stdout + r.stderr
    # The shim logs `$*`, so the publishing run's line starts with "run -d".
    run_line = next(l for l in log.read_text().splitlines() if l.startswith("run -d "))
    assert "--network podman" in run_line
    published = port_file.read_text().strip()
    assert published.isdigit() and int(published) > 0  # explicit allocated host port
    assert f"-p {published}:8080" in run_line
    assert f"0.0.0.0:{published}" in r.stdout  # echoed mapping matches the -p argv
    for line in ("PASS: container run", "PASS: port publishing", "PASS: volume"):
        assert line in r.stdout


def test_e2e_072_shim_empty_port_mapping_fails(invoke_bin, shim, tmp_path):
    """An empty `podman port` mapping must FAIL, never PASS (QA finding)."""
    port_file = tmp_path / "doctor_shim_port"
    _install_podman_shim(shim, port_file, port_case=":")  # `podman port` prints nothing
    r = invoke_bin("podman-doctor", cwd=tmp_path, env_overrides={
        "PATH": f"{shim.dir}:{os.environ['PATH']}"})
    assert r.returncode != 0
    assert "FAIL: port publishing" in r.stdout
    assert "PASS: port publishing" not in r.stdout


def test_e2e_072_shim_hanging_podman_call_is_bounded(invoke_bin, shim, tmp_path):
    """A hanging podman call is killed after E2E_PODMAN_TIMEOUT instead of running
    unbounded; the doctor reports the timeout diagnosis and exits nonzero."""
    shim("podman", ["sleep 30"])
    r = invoke_bin("podman-doctor", cwd=tmp_path, env_overrides={
        "PATH": f"{shim.dir}:{os.environ['PATH']}",
        "E2E_PODMAN_TIMEOUT": "1"}, timeout=60)
    assert r.returncode != 0
    assert "exceeded E2E_PODMAN_TIMEOUT=1s" in r.stderr


@pytest.mark.parametrize("bad", ["0", "-5", "abc", "", "1.5"])
def test_e2e_072_shim_rejects_invalid_timeout(invoke_bin, shim, tmp_path, bad):
    """E2E_PODMAN_TIMEOUT must be a positive integer; anything else fails closed."""
    shim("podman", ["exit 0"])
    r = invoke_bin("podman-doctor", cwd=tmp_path, env_overrides={
        "PATH": f"{shim.dir}:{os.environ['PATH']}",
        "E2E_PODMAN_TIMEOUT": bad})
    assert r.returncode != 0
    assert "E2E_PODMAN_TIMEOUT must be a positive integer" in r.stderr
    assert "FAIL:" not in r.stdout  # rejected before any podman probe ran


def test_e2e_072_shim_fails_closed_without_timeout_utility(invoke_bin, shim, tmp_path):
    """Without the `timeout` utility the doctor refuses to run podman unbounded."""
    shim("podman", ["exit 0"])
    # PATH must still resolve `bash` for the subprocess but nothing else: a bare
    # bin dir holding only a bash symlink leaves `timeout` unavailable.
    nobin = tmp_path / "nobin"
    nobin.mkdir()
    os.symlink(shutil.which("bash"), nobin / "bash")
    r = invoke_bin("podman-doctor", cwd=tmp_path,
                   env_overrides={"PATH": f"{shim.dir}:{nobin}"})
    assert r.returncode != 0
    assert "'timeout' utility is not available" in r.stderr
