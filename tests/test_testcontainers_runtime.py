import os
from quality_bundle.testcontainers_runtime import configure_testcontainers_for_podman

def test_configure_testcontainers_for_podman(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("TESTCONTAINERS_RYUK_DISABLED", raising=False)
    host = configure_testcontainers_for_podman()
    assert host == f"unix://{tmp_path}/podman/podman.sock"
    assert os.environ["TESTCONTAINERS_RYUK_DISABLED"] == "true"
