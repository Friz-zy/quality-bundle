from __future__ import annotations
import os
import socket
from pathlib import Path
from testcontainers.core.container import DockerContainer

def configure_testcontainers_for_podman() -> str:
    """
    Point Docker-API clients, including Testcontainers, at the rootless Podman socket.

    Podman remains the container engine; Testcontainers talks to its Docker-compatible API.
    """
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    socket = runtime_dir / "podman" / "podman.sock"
    docker_host = os.environ.setdefault("DOCKER_HOST", f"unix://{socket}")
    # Rootless/nested environments can make a resource-reaper sidecar problematic.
    # Python Testcontainers also explicitly stops containers in fixture finalizers.
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
    return docker_host

def _free_host_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])

class PodmanDockerContainer(DockerContainer):
    """DockerContainer whose published host ports are known locally: podman's
    compat API does not reliably report port mappings in nested rootless setups."""
    def __init__(self, image: str, command: str | None = None, host_ports: dict[str, int] | None = None):
        super().__init__(image, command=command)
        self._host_ports = host_ports if host_ports is not None else {}

    def _get_exposed_port(self, port: int) -> int:
        return self._host_ports[f"{port}/tcp"]

def generic_container(image: str, port: int | None = None, command: str | None = None) -> DockerContainer:
    configure_testcontainers_for_podman()
    host_ports: dict[str, int] = {}
    container = PodmanDockerContainer(image, command=command, host_ports=host_ports)
    # Force the engine's default bridge network ("podman"): testcontainers' DinD
    # network detection can attach the container to the host network, where port
    # publishing is silently ignored (NetworkSettings.Ports stays empty). Passing
    # the plain name via _kwargs keeps the create payload minimal, which the
    # podman compat API handles reliably.
    container._kwargs["network"] = "podman"
    if port is not None:
        free = _free_host_port()
        host_ports[f"{port}/tcp"] = free
        # Keep the real bind so the port is actually published (pasta forwards it);
        # only the compat-API introspection of the mapping is skipped above.
        container.with_bind_ports(port, free)
    return container
