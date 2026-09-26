from __future__ import annotations
import os
from pathlib import Path
import httpx
from .polling import poll_until
from .runtime import RuntimeContainer, runtime_from_environment

class ApplicationEnvironment:
    """Connect to an external SUT or start its production image with rootless Podman."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.base_url = cfg.app.base_url
        self.runtime = None
        self.container: RuntimeContainer | None = None

    def __enter__(self):
        if not self.base_url:
            if not self.cfg.container.image:
                raise RuntimeError("Configure app.base_url/E2E_BASE_URL or container.image/E2E_IMAGE")
            self.runtime = runtime_from_environment()
            env = {
                key.removeprefix("E2E_APP_ENV_"): value
                for key, value in os.environ.items()
                if key.startswith("E2E_APP_ENV_")
            }
            name = f"e2e-sut-{os.getpid()}"
            self.container = self.runtime.run(
                self.cfg.container.image,
                name=name,
                ports={self.cfg.container.port: None},
                env=env,
            )
            host, port = self.runtime.port(self.container, self.cfg.container.port)
            if host in ("0.0.0.0", "::"):
                host = "127.0.0.1"
            self.base_url = f"http://{host}:{port}"

        url = f"{self.base_url.rstrip('/')}{self.cfg.app.health_path}"
        poll_until(
            lambda: httpx.get(url, timeout=2),
            lambda response: response.status_code < 500,
            timeout=self.cfg.app.startup_timeout,
            description=f"readiness at {url}",
        )
        return self

    def __exit__(self, *_):
        if not self.container or not self.runtime:
            return
        artifacts = Path(self.cfg.paths.artifacts)
        artifacts.mkdir(parents=True, exist_ok=True)
        try:
            (artifacts / "sut.log").write_text(
                self.runtime.logs(self.container), encoding="utf-8"
            )
        finally:
            self.runtime.stop(self.container)
