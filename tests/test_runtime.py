import re
import subprocess
import pytest
from quality_bundle.runtime import (
    BUILD_TIMEOUT,
    DEFAULT_TIMEOUT,
    MAX_PORT_ATTEMPTS,
    PULL_TIMEOUT,
    RUN_TIMEOUT,
    PodmanRuntime,
    free_host_port,
)


class FakePodman:
    """Records subprocess.run calls; can selectively hang or fail."""

    def __init__(self, hang_subcommand=None, fail=False):
        self.calls = []
        self.hang_subcommand = hang_subcommand
        self.fail = fail

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        if self.hang_subcommand is not None and argv[1] == self.hang_subcommand:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", DEFAULT_TIMEOUT))
        code = 1 if self.fail else 0
        return subprocess.CompletedProcess(argv, code, stdout="abc123\n", stderr="")


def _publish_values(fake):
    values = []
    for argv, _ in fake.calls:
        values.extend(argv[i + 1] for i, token in enumerate(argv) if token == "-p")
    return values


def test_free_host_port_returns_ephemeral_range():
    for _ in range(5):
        port = free_host_port()
        assert 1 <= port <= 65535


def test_podman_runtime_builds_expected_run_command(monkeypatch):
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    runtime = PodmanRuntime("podman")
    container = runtime.run(
        "example/image:test",
        name="sut",
        ports={8080: None},
        env={"MODE": "test"},
    )
    assert container.id == "abc123"
    argv, kwargs = fake.calls[0]
    assert argv[:5] == ["podman", "run", "-d", "--name", "sut"]
    assert kwargs["timeout"] == RUN_TIMEOUT
    # publishing containers ride the stock bridge network so `-p` is honored
    assert argv[argv.index("--network") + 1] == "podman"
    publish = _publish_values(fake)[0]
    # dynamic host port (None) -> explicitly allocated ephemeral port, never 0
    assert re.fullmatch(r"[1-9][0-9]{0,4}:8080", publish), publish


def test_run_explicit_network_wins_over_bridge_default(monkeypatch):
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    runtime = PodmanRuntime("podman")
    runtime.run("img", name="sut", ports={8080: None}, network="custom")
    argv = fake.calls[0][0]
    assert argv[argv.index("--network") + 1] == "custom"


def test_run_allocates_distinct_explicit_ports(monkeypatch):
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    runtime = PodmanRuntime("podman")
    runtime.run("img", name="sut", ports={8080: None, 8081: None})
    publishes = _publish_values(fake)
    assert len(publishes) == 2
    host_ports = {p.split(":")[0] for p in publishes}
    assert len(host_ports) == 2  # two mappings, two different allocated ports
    assert all(int(p.split(":")[0]) > 0 for p in publishes)


def test_run_preserves_explicit_host_ports(monkeypatch):
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    runtime = PodmanRuntime("podman")
    runtime.run("img", name="sut", ports={8080: 43123, 8081: 0})
    publishes = sorted(_publish_values(fake), key=lambda p: int(p.split(":")[1]))
    assert publishes[0] == "43123:8080"  # explicit host port kept verbatim
    assert re.fullmatch(r"[1-9][0-9]{0,4}:8081", publishes[1])  # 0 -> allocated


def test_run_port_allocation_retries_until_distinct(monkeypatch):
    # the kernel may hand back the same just-released port; a few retries are normal
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    recycled = iter([5000, 5000, 5001])
    monkeypatch.setattr("quality_bundle.runtime.free_host_port", lambda: next(recycled))
    PodmanRuntime("podman").run("img", name="sut", ports={8080: None, 8081: None})
    publishes = sorted(_publish_values(fake), key=lambda p: int(p.split(":")[1]))
    assert publishes == ["5000:8080", "5001:8081"]


def test_run_port_allocation_is_bounded_before_launch(monkeypatch):
    # QA gate: pathological kernel reuse must fail fast with a clear error,
    # never loop indefinitely, and never reach podman
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    attempts = []

    def stuck():
        attempts.append(1)
        return 55555

    monkeypatch.setattr("quality_bundle.runtime.free_host_port", stuck)
    # explicit port pre-seeds `allocated`, so the single allocation must exhaust
    with pytest.raises(RuntimeError, match=r"distinct ephemeral host port in 16 attempts"):
        PodmanRuntime("podman").run("img", name="sut", ports={8080: 55555, 8081: None})
    assert len(attempts) == MAX_PORT_ATTEMPTS == 16  # bounded, not unbounded
    assert fake.calls == []  # raised before any podman command


def test_run_allocation_avoids_explicit_host_ports(monkeypatch):
    # explicit binds are simultaneous too, so allocations must skip them
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    recycled = iter([43123, 43124])
    monkeypatch.setattr("quality_bundle.runtime.free_host_port", lambda: next(recycled))
    PodmanRuntime("podman").run("img", name="sut", ports={8080: 43123, 8081: None})
    publishes = sorted(_publish_values(fake), key=lambda p: int(p.split(":")[1]))
    assert publishes[0] == "43123:8080"  # explicit host port kept verbatim
    assert publishes[1] == "43124:8081"  # allocation skipped the explicit port


def test_run_without_ports_has_no_publish_or_network_flags(monkeypatch):
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    PodmanRuntime("podman").run("img", name="sut")
    assert _publish_values(fake) == []
    argv = fake.calls[0][0]
    assert "--network" not in argv


def test_run_bounded_timeout_raises_runtime_error(monkeypatch):
    fake = FakePodman(hang_subcommand="run")
    monkeypatch.setattr(subprocess, "run", fake)
    with pytest.raises(RuntimeError, match=r"Podman command timed out after \d+s: podman run"):
        PodmanRuntime("podman").run("img", name="sut")


def test_run_default_timeout_is_bounded(monkeypatch):
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    runtime = PodmanRuntime("podman")
    runtime._run("info")
    _, kwargs = fake.calls[0]
    assert kwargs["timeout"] == DEFAULT_TIMEOUT == 120


def test_logs_include_stderr(monkeypatch):
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="out-line\n", stderr="err-line\n")
    monkeypatch.setattr(subprocess, "run", fake_run)
    from quality_bundle.runtime import RuntimeContainer
    runtime = PodmanRuntime("podman")
    logs = runtime.logs(RuntimeContainer("abc123", "sut"))
    assert "out-line" in logs and "err-line" in logs


def test_pull_and_build_use_higher_explicit_bounds(monkeypatch):
    fake = FakePodman()
    monkeypatch.setattr(subprocess, "run", fake)
    runtime = PodmanRuntime("podman")
    runtime.pull("example/image:test")
    runtime.build(".", tag="sut:test")
    assert fake.calls[0][1]["timeout"] == PULL_TIMEOUT == 900
    assert fake.calls[1][1]["timeout"] == BUILD_TIMEOUT == 900


def test_probe_reports_timeout_as_failed_entry(monkeypatch):
    fake = FakePodman(hang_subcommand="run")  # only the `run` probes hang
    monkeypatch.setattr(subprocess, "run", fake)
    report = PodmanRuntime("podman").probe()
    assert set(report) == {"info", "run", "network", "volume"}
    for name in ("run", "network", "volume"):
        assert report[name]["ok"] is False, name
        assert report[name]["timeout"] is True, name
        assert report[name]["exit_code"] is None, name
    assert report["info"]["ok"] is True  # other probes still complete
    # cleanup still attempted after timeouts
    assert fake.calls[-1][0] == ["podman", "volume", "rm", "-f", "e2e-probe"]


def test_probe_cleanup_timeout_does_not_abort_report(monkeypatch):
    fake = FakePodman(hang_subcommand="volume")
    monkeypatch.setattr(subprocess, "run", fake)
    report = PodmanRuntime("podman").probe()
    assert all(entry["ok"] is True for entry in report.values())


def test_probe_failure_recorded_without_timeout_flag(monkeypatch):
    fake = FakePodman(fail=True)
    monkeypatch.setattr(subprocess, "run", fake)
    report = PodmanRuntime("podman").probe()
    for entry in report.values():
        assert entry["ok"] is False
        assert entry["exit_code"] == 1
        assert "timeout" not in entry
