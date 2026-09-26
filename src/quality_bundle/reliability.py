from __future__ import annotations
from .runtime import runtime_from_environment

class ToxiproxyEnvironment:
    API_PORT = 8474
    PROXY_PORT = 8666

    def __init__(self, image: str):
        self.image = image
        self.runtime = runtime_from_environment()
        self.container = None

    def __enter__(self):
        self.container = self.runtime.run(
            self.image,
            name="e2e-toxiproxy",
            ports={self.API_PORT: None, self.PROXY_PORT: None},
        )
        return self

    @property
    def api_url(self):
        host, port = self.runtime.port(self.container, self.API_PORT)
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        return f"http://{host}:{port}"

    def mapped_proxy_port(self):
        return self.runtime.port(self.container, self.PROXY_PORT)[1]

    def __exit__(self, *_):
        if self.container:
            self.runtime.stop(self.container)
