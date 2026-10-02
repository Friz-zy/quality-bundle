"""Nested rootless Podman smoke: no host Docker socket mounted.

CI runs this file inside the quality-bundle container with
``E2E_PODMAN_SERVICE=1``, so the entrypoint fails closed when the internal
Podman API socket cannot start (for example when the outer executor forbids
nested user namespaces). A passing ``quality doctor`` is not enough: the tests
really create and remove containers through both in-container paths used by
the harness:

- Testcontainers over the internal Docker-compatible socket
  (``$XDG_RUNTIME_DIR/podman/podman.sock``), as used by ``quality test``;
- the ``PodmanRuntime`` CLI adapter, as used for SUT lifecycle operations.

Run without mounting ``/var/run/docker.sock`` and without setting
``DOCKER_HOST``; this file is independent of the DooD mode exercised by
test_dood_testcontainers.py.
"""
import os
import time

import pytest
from docker.errors import NotFound
from testcontainers.core.container import DockerContainer
from testcontainers.core.docker_client import DockerClient

from quality_bundle.runtime import PodmanRuntime
from quality_bundle.testcontainers_runtime import generic_container

IMAGE = "docker.io/library/busybox:1.37.0"
MARKER = "nested-podman-smoke-ok"


def test_nested_mode_targets_internal_podman_socket():
    docker_host = os.environ.get("DOCKER_HOST", "")
    assert docker_host.endswith("/podman/podman.sock")
    assert "docker.sock" not in docker_host


def test_testcontainers_creates_and_removes_container_via_internal_socket():
    client = DockerClient()
    with generic_container(IMAGE, port=8080, command="sleep 30") as container:
        container_id = container.get_wrapped_container().id
        published = int(container.get_exposed_port(8080))
        assert published > 0
        result = container.exec(["echo", MARKER])
        assert result.exit_code == 0
        assert MARKER in result.output.decode()
    # DockerContainer.stop() force-removes the container on context exit.
    with pytest.raises(NotFound):
        client.client.containers.get(container_id)


def test_podman_runtime_creates_and_removes_container():
    runtime = PodmanRuntime()
    container = runtime.run(IMAGE, name="smoke-nested-runtime", command=["sleep", "30"])
    try:
        assert runtime.inspect(container)["State"]["Running"] is True
    finally:
        runtime.stop(container)
    # run() uses --rm, so the container must disappear after stop.
    for _ in range(50):
        try:
            runtime.inspect(container)
        except RuntimeError:
            return
        time.sleep(0.1)
    pytest.fail("container was not removed after PodmanRuntime.stop()")
