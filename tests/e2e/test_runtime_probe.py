"""E2E-073: PodmanRuntime.probe report contract (T2, no port publishing needed)."""
import subprocess
import pytest
from conftest import _require_podman
from quality_bundle.runtime import PodmanRuntime


@pytest.mark.container
def test_e2e_073_podman_probe_report(request):
    _require_podman(request)
    report = PodmanRuntime().probe()
    assert set(report) == {"info", "run", "network", "volume"}
    for name, entry in report.items():
        assert set(entry) == {"ok", "exit_code", "duration", "stderr"}, name
        assert entry["ok"] is True, f"{name}: {entry}"
        assert entry["exit_code"] == 0
        assert isinstance(entry["duration"], float) and entry["duration"] >= 0
    volumes = subprocess.run(["podman", "volume", "ls", "--format", "{{.Name}}"],
                             capture_output=True, text=True, timeout=30).stdout.split()
    assert "e2e-probe" not in volumes  # probe cleans up its volume
