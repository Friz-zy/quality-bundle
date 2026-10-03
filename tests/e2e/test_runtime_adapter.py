"""E2E-065/066: native runtime adapter contract (T1, shimmed)."""
import re
import pytest
from quality_bundle.runtime import PodmanRuntime, runtime_from_environment


def test_e2e_065_unsupported_runtime_rejected(monkeypatch):
    monkeypatch.setenv("E2E_CONTAINER_RUNTIME", "nginx")
    with pytest.raises(RuntimeError, match="Unsupported native runtime 'nginx'"):
        runtime_from_environment()


def test_e2e_066_podman_runtime_command_shapes(shim, tmp_path, monkeypatch):
    podman_shim = shim("podman", [
        'case "${1:-}" in',
        "  run) echo 'abc123' ;;",
        "  port) echo '0.0.0.0:43123' ;;",
        "  logs) echo 'container log line' ;;",
        "  stop) exit 0 ;;",
        "  *) exit 0 ;;",
        "esac",
    ])
    log = tmp_path / "shim.log"
    monkeypatch.setenv("E2E_PODMAN", str(podman_shim))
    monkeypatch.setenv("SHIM_LOG", str(log))
    runtime = runtime_from_environment()
    assert isinstance(runtime, PodmanRuntime)
    assert runtime.executable == str(podman_shim)

    container = runtime.run("registry/sut:1", name="e2e-test",
                            ports={8080: None}, env={"APP_ENV": "test"})
    assert (container.id, container.name) == ("abc123", "e2e-test")

    host, port = runtime.port(container, 8080)
    assert (host, port) == ("0.0.0.0", 43123)

    assert runtime.logs(container) == "container log line\n"

    runtime.stop(container)  # check=False path, exit 0

    lines = log.read_text().strip().splitlines()
    run_argv = lines[0].split()
    # None/0 host ports are published as an explicitly allocated ephemeral port
    # (this podman-compatible shim path must never emit `-p 0:PORT`), on the
    # stock bridge network so publishing is honored in nested setups.
    publish = run_argv[run_argv.index("-p") + 1]
    assert re.fullmatch(r"[1-9][0-9]{0,4}:8080", publish), publish
    assert run_argv == ["run", "-d", "--name", "e2e-test", "--rm",
                        "--network", "podman",
                        "-p", publish, "-e", "APP_ENV=test", "registry/sut:1"]
    assert lines[1].split() == ["port", "abc123", "8080"]
    assert lines[2].split() == ["logs", "abc123"]
    assert lines[3].split() == ["stop", "--time", "10", "abc123"]
