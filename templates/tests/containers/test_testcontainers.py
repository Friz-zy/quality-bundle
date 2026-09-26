import pytest
from testcontainers.core.container import DockerContainer

@pytest.mark.container
def test_testcontainers_uses_configured_podman(testcontainers_podman):
    with DockerContainer("docker.io/library/busybox:latest").with_command(
        "sh -c 'echo testcontainers-podman-ok; sleep 1'"
    ) as container:
        logs = container.get_logs()
        stdout = logs[0] if isinstance(logs, tuple) else logs
        if isinstance(stdout, bytes):
            stdout = stdout.decode()
        assert "testcontainers-podman-ok" in stdout
