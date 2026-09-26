import subprocess
from quality_bundle.runtime import PodmanRuntime

def test_podman_runtime_builds_expected_run_command(monkeypatch):
    seen = []
    def fake_run(argv, **kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="abc123\n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    runtime = PodmanRuntime("podman")
    container = runtime.run(
        "example/image:test",
        name="sut",
        ports={8080: None},
        env={"MODE": "test"},
    )
    assert container.id == "abc123"
    assert seen[0][:5] == ["podman", "run", "-d", "--name", "sut"]
    assert "-p" in seen[0]
    assert "0:8080" in seen[0]
