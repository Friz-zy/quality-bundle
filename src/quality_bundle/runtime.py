from __future__ import annotations
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

@dataclass(frozen=True)
class RuntimeContainer:
    id: str
    name: str

class PodmanRuntime:
    """Minimal Podman CLI adapter for black-box E2E infrastructure."""

    def __init__(self, executable: str = "podman"):
        self.executable = executable

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [self.executable, *args],
            text=True,
            capture_output=True,
            check=False,
        )
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
        if network:
            args += ["--network", network]
        for container_port, host_port in (ports or {}).items():
            publish = f"{host_port or 0}:{container_port}"
            args += ["-p", publish]
        for key, value in (env or {}).items():
            args += ["-e", f"{key}={value}"]
        for volume in volumes or ():
            args += ["-v", volume]
        args.append(image)
        args.extend(command or ())
        result = self._run(*args)
        return RuntimeContainer(result.stdout.strip(), name)

    def stop(self, container: RuntimeContainer, timeout: int = 10) -> None:
        self._run("stop", "--time", str(timeout), container.id, check=False)

    def kill(self, container: RuntimeContainer, signal: str = "KILL") -> None:
        self._run("kill", "--signal", signal, container.id)

    def restart(self, container: RuntimeContainer, timeout: int = 10) -> None:
        self._run("restart", "--time", str(timeout), container.id)

    def logs(self, container: RuntimeContainer) -> str:
        return self._run("logs", container.id, check=False).stdout

    def inspect(self, container: RuntimeContainer) -> dict:
        output = self._run("inspect", container.id).stdout
        return json.loads(output)[0]

    def port(self, container: RuntimeContainer, container_port: int) -> tuple[str, int]:
        output = self._run("port", container.id, str(container_port)).stdout.strip().splitlines()[0]
        host, port = output.rsplit(":", 1)
        return host.strip("[]"), int(port)

    def pull(self, image: str) -> None:
        self._run("pull", image)

    def build(self, context: str | Path, *, tag: str, dockerfile: str | Path | None = None) -> None:
        args = ["build", "-t", tag]
        if dockerfile:
            args += ["-f", str(dockerfile)]
        args.append(str(context))
        self._run(*args)

    def create_network(self, name: str) -> None:
        self._run("network", "create", name)

    def remove_network(self, name: str) -> None:
        self._run("network", "rm", "-f", name, check=False)

    def probe(self, image: str = "docker.io/library/busybox:latest") -> dict[str, object]:
        """Exercise the capabilities required by the harness."""
        report: dict[str, object] = {}
        commands = {
            "info": [self.executable, "info", "--format", "json"],
            "run": [self.executable, "run", "--rm", image, "true"],
            "network": [self.executable, "run", "--rm", image, "sh", "-c", "ip addr >/dev/null 2>&1 || true"],
            "volume": [self.executable, "run", "--rm", "-v", "e2e-probe:/data", image, "sh", "-c", "touch /data/probe"],
        }
        for name, argv in commands.items():
            started = time.monotonic()
            result = subprocess.run(argv, text=True, capture_output=True, check=False)
            report[name] = {
                "ok": result.returncode == 0,
                "exit_code": result.returncode,
                "duration": round(time.monotonic() - started, 3),
                "stderr": result.stderr[-2000:],
            }
        subprocess.run([self.executable, "volume", "rm", "-f", "e2e-probe"],
                       text=True, capture_output=True, check=False)
        return report

def runtime_from_environment() -> PodmanRuntime:
    runtime = os.getenv("E2E_CONTAINER_RUNTIME", "podman")
    if runtime != "podman":
        raise RuntimeError(
            f"Unsupported native runtime {runtime!r}; the built-in runtime is Podman-first"
        )
    return PodmanRuntime(os.getenv("E2E_PODMAN", "podman"))
