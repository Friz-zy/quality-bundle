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

def generic_container(image: str, port: int | None = None, command: str | None = None) -> DockerContainer:
    configure_testcontainers_for_podman()
    container = DockerContainer(image, command=command)
    if port is not None:
        # Podman's compat API does not reliably report auto-assigned (empty-HostPort)
        # port mappings in nested rootless setups; binding an explicit free host port
        # is the supported publish form (equivalent to -p HOST:port).
        container.with_bind_ports(port, _free_host_port())
    return container
