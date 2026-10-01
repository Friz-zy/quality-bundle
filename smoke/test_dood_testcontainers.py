"""DooD smoke: Testcontainers over the host Docker socket.

CI runs this file inside the quality-bundle container with:

    -v /var/run/docker.sock:/var/run/docker.sock
    -e DOCKER_HOST=unix:///var/run/docker.sock
    -e E2E_PODMAN_SERVICE=0

so the nested Podman API service stays off and Testcontainers must operate on
the host engine through the mounted socket (Docker-out-of-Docker). This mode is
independent of the nested rootless Podman mode exercised by
test_nested_podman.py: it covers Testcontainers clients only, not the
PodmanRuntime CLI adapter, which knows nothing about DOCKER_HOST.
"""
import os

import pytest
from docker.errors import NotFound
from testcontainers.core.container import DockerContainer
from testcontainers.core.docker_client import DockerClient

IMAGE = "docker.io/library/busybox:1.37.0"
MARKER = "dood-smoke-ok"


def test_dood_mode_targets_docker_socket():
    docker_host = os.environ.get("DOCKER_HOST", "")
    assert docker_host, "DOCKER_HOST must point at the mounted host Docker socket"
    assert "podman.sock" not in docker_host


def test_testcontainers_creates_and_removes_container():
    client = DockerClient()
    with DockerContainer(IMAGE).with_command("sleep 30") as container:
        container_id = container.get_wrapped_container().id
        result = container.exec(["echo", MARKER])
        assert result.exit_code == 0
        assert MARKER in result.output.decode()
    # DockerContainer.stop() force-removes the container on context exit.
    with pytest.raises(NotFound):
        client.client.containers.get(container_id)
