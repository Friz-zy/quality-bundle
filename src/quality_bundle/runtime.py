from __future__ import annotations
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

# Per-operation subprocess bounds so a stuck runtime cannot hang the suite.
DEFAULT_TIMEOUT = 120.0
# `run` may implicitly pull a missing image before starting the container.
RUN_TIMEOUT = 600.0
# Pulls and builds are network/CPU bound and legitimately slow.
PULL_TIMEOUT = 900.0
BUILD_TIMEOUT = 900.0


def free_host_port() -> int:
    """Return a currently-free ephemeral host port (bound on 127.0.0.1, then released).

    Some Podman builds reject `-p 0:PORT` dynamic host ports, so callers publish an
    explicitly allocated port instead. The release-then-rebind window is the standard
    tradeoff of this pattern (same as testcontainers).
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# Bounded ephemeral-port allocation: the kernel may immediately reuse a
# just-released port, so a few retries are normal, but pathological reuse must
# fail fast with a clear error instead of looping indefinitely (QA gate).
MAX_PORT_ATTEMPTS = 16


def allocate_distinct_port(allocated: set[int]) -> int:
    """Return an ephemeral port not in `allocated`, bounded by MAX_PORT_ATTEMPTS tries.

    Raises RuntimeError when uniqueness cannot be achieved so the failure
    surfaces before any podman command is launched.
    """
    for _ in range(MAX_PORT_ATTEMPTS):
        port = free_host_port()
        if port not in allocated:
            return port
    raise RuntimeError(
        f"could not allocate a distinct ephemeral host port in {MAX_PORT_ATTEMPTS} attempts; "
        f"ports already in use: {sorted(allocated)}"
    )


@dataclass(frozen=True)
class RuntimeContainer:
    id: str
    name: str

class PodmanRuntime:
    """Minimal Podman CLI adapter for black-box E2E infrastructure."""

    def __init__(self, executable: str = "podman"):
        self.executable = executable

    def _run(
        self,
        *args: str,
        check: bool = True,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                [self.executable, *args],
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Podman command timed out after {timeout:g}s: "
                f"{self.executable} {' '.join(args)}"
            ) from exc
        if check and result.returncode != 0:
            raise RuntimeError(
                f"Podman command failed: {self.executable} {' '.join(args)}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def run(
        self,
        image: str,
        *,
        name: str,
        ports: Mapping[int, int | None] | None = None,
        env: Mapping[str, str] | None = None,
        command: Sequence[str] | None = None,
        volumes: Sequence[str] | None = None,
        network: str | None = None,
    ) -> RuntimeContainer:
        args = ["run", "-d", "--name", name, "--rm"]
        # In nested/rootless setups the engine default can be a host-style
        # network where `-p` publishing is silently ignored; the stock bridge
        # network ("podman") publishes reliably. Only publishing containers
        # need this; explicit network= always wins.
        if network:
            args += ["--network", network]
        elif ports:
            args += ["--network", "podman"]
        # Explicit host binds count as taken so allocations cannot collide with
        # them (a container's binds are simultaneous); explicit ports pass
        # through verbatim.
        allocated: set[int] = {host for host in (ports or {}).values() if host}
        for container_port, host_port in (ports or {}).items():
            if not host_port:
                # Dynamic `-p 0:PORT` is rejected by several Podman builds
                # ("port numbers must be between 1 and 65535"); publish an
                # explicitly allocated ephemeral port instead.
                host_port = allocate_distinct_port(allocated)
                allocated.add(host_port)
            args += ["-p", f"{host_port}:{container_port}"]
        for key, value in (env or {}).items():
            args += ["-e", f"{key}={value}"]
        for volume in volumes or ():
            args += ["-v", volume]
        args.append(image)
        args.extend(command or ())
        result = self._run(*args, timeout=RUN_TIMEOUT)
        return RuntimeContainer(result.stdout.strip(), name)

    def stop(self, container: RuntimeContainer, timeout: int = 10) -> None:
        self._run("stop", "--time", str(timeout), container.id, check=False)

    def kill(self, container: RuntimeContainer, signal: str = "KILL") -> None:
        self._run("kill", "--signal", signal, container.id)

    def restart(self, container: RuntimeContainer, timeout: int = 10) -> None:
        self._run("restart", "--time", str(timeout), container.id)

    def logs(self, container: RuntimeContainer) -> str:
        result = self._run("logs", container.id, check=False)
        # `podman logs` emits the container's stdout on stdout and its stderr on
        # stderr; many services log to stderr, so sut.log must keep both.
        return result.stdout + result.stderr

    def inspect(self, container: RuntimeContainer) -> dict:
        output = self._run("inspect", container.id).stdout
        return json.loads(output)[0]

    def port(self, container: RuntimeContainer, container_port: int) -> tuple[str, int]:
        output = self._run("port", container.id, str(container_port)).stdout.strip().splitlines()[0]
        host, port = output.rsplit(":", 1)
        return host.strip("[]"), int(port)

    def pull(self, image: str) -> None:
        self._run("pull", image, timeout=PULL_TIMEOUT)

    def build(self, context: str | Path, *, tag: str, dockerfile: str | Path | None = None) -> None:
        args = ["build", "-t", tag]
        if dockerfile:
            args += ["-f", str(dockerfile)]
        args.append(str(context))
        self._run(*args, timeout=BUILD_TIMEOUT)

    def create_network(self, name: str) -> None:
        self._run("network", "create", name)

    def remove_network(self, name: str) -> None:
        self._run("network", "rm", "-f", name, check=False)

    def probe(self, image: str = "docker.io/library/busybox:latest",
              timeout: float = DEFAULT_TIMEOUT) -> dict[str, object]:
        """Exercise the capabilities required by the harness.

        Every probe is bounded by `timeout`; a probe that exceeds it is reported as a
        failed entry (`ok: False`, `timeout: True`) instead of aborting the report.
        """
        report: dict[str, object] = {}
        commands = {
            "info": [self.executable, "info", "--format", "json"],
            "run": [self.executable, "run", "--rm", image, "true"],
            "network": [self.executable, "run", "--rm", image, "sh", "-c", "ip addr >/dev/null 2>&1 || true"],
            "volume": [self.executable, "run", "--rm", "-v", "e2e-probe:/data", image, "sh", "-c", "touch /data/probe"],
        }
        for name, argv in commands.items():
            started = time.monotonic()
            try:
                result = subprocess.run(argv, text=True, capture_output=True, check=False,
                                        timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                report[name] = {
                    "ok": False,
                    "exit_code": None,
                    "duration": round(time.monotonic() - started, 3),
                    "stderr": str(exc)[-2000:],
                    "timeout": True,
                }
                continue
            report[name] = {
                "ok": result.returncode == 0,
                "exit_code": result.returncode,
                "duration": round(time.monotonic() - started, 3),
                "stderr": result.stderr[-2000:],
            }
        try:
            subprocess.run([self.executable, "volume", "rm", "-f", "e2e-probe"],
                           text=True, capture_output=True, check=False, timeout=timeout)
        except subprocess.TimeoutExpired:
            pass  # cleanup is best-effort; never abort the report
        return report

def runtime_from_environment() -> PodmanRuntime:
    runtime = os.getenv("E2E_CONTAINER_RUNTIME", "podman")
    if runtime != "podman":
        raise RuntimeError(
            f"Unsupported native runtime {runtime!r}; the built-in runtime is Podman-first"
        )
    return PodmanRuntime(os.getenv("E2E_PODMAN", "podman"))
