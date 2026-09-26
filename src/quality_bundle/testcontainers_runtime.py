from __future__ import annotations
import os
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

def generic_container(image: str, port: int | None = None) -> DockerContainer:
    configure_testcontainers_for_podman()
    container = DockerContainer(image)
    if port is not None:
        container.with_exposed_ports(port)
    return container
