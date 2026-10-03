import os
import pytest
from testcontainers.core.container import DockerContainer
from quality_bundle.testcontainers_runtime import (
    PodmanDockerContainer,
    configure_testcontainers_for_podman,
)

def test_configure_testcontainers_for_podman(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("TESTCONTAINERS_RYUK_DISABLED", raising=False)
    host = configure_testcontainers_for_podman()
    assert host == f"unix://{tmp_path}/podman/podman.sock"
    assert os.environ["TESTCONTAINERS_RYUK_DISABLED"] == "true"


def test_explicit_host_ports_resolve_locally_without_docker_inspect():
    container = PodmanDockerContainer("img", host_ports={"8080/tcp": 43123})
    # The podman compat `containers list` payload has no HostConfig, so the
    # stock testcontainers lookup KeyErrors; explicit ports skip it entirely.
    assert container.get_container_host_ip() == "127.0.0.1"
    assert container._get_exposed_port(8080) == 43123


def test_without_explicit_host_ports_defers_to_stock_behavior(monkeypatch):
    calls = []
    monkeypatch.setattr(
        DockerContainer, "get_container_host_ip",
        lambda self: (calls.append(1), "172.17.0.1")[1],
    )
    container = PodmanDockerContainer("img")
    assert container.get_container_host_ip() == "172.17.0.1"
    assert calls == [1]
