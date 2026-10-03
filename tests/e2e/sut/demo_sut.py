"""Demo system-under-test for the quality-bundle self-test suite. Stdlib only.

Endpoints (plan §3):
  GET  /health          200 {"status": "ok"} - unless flapping or pinned (see /_ctl/health)
  GET  /ready           200 {"status": "ready"}
  GET  /api/data        200 {"items": [1, 2, 3]}
  POST /api/echo        echoes the JSON request body back
  GET  /events          SSE: ": ping" comments, then 3 events, then holds the connection open
  GET  /boom            500
  GET  /a11y            minimal valid HTML with one button
  GET  /_ctl/health     control plane: ?mode=flap (next two /health calls 503),
                        ?code=418 (pin /health to 418), ?code=0 (reset pin)
"""
from __future__ import annotations
import json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class ControlState:
    """Thread-safe /health behavior control (handler instances are per-connection)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._flap_remaining = 0
        self._pinned_code: int | None = None

    def flap(self, times: int = 2):
        with self._lock:
            self._flap_remaining = times

    def pin(self, code: int | None):
        with self._lock:
            self._pinned_code = code

    def health_code(self) -> int:
        with self._lock:
            if self._pinned_code is not None:
                return self._pinned_code
            if self._flap_remaining > 0:
                self._flap_remaining -= 1
                return 503
        return 200


class DemoSUTHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "DemoSUT/1.0"
    timeout = 30

    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if path == "/_ctl/health":
            self._control(query)
        elif path == "/health":
            code = self.server.control.health_code()
            self._json(code, {"status": "ok"} if code == 200 else {"status": "unhealthy"})
        elif path == "/ready":
            self._json(200, {"status": "ready"})
        elif path == "/api/data":
            self._json(200, {"items": [1, 2, 3]})
        elif path == "/events":
            self._events()
        elif path == "/boom":
            self._json(500, {"error": "boom"})
        elif path == "/a11y":
            self._html(200, "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
                            "<title>Demo SUT</title></head><body><h1>Demo</h1>"
                            "<button id=\"go\" type=\"button\">Go</button></body></html>\n")
        else:
            self._json(404, {"error": "not found", "path": path})

    def _method_not_allowed(self):
        body = b'{"error": "method not allowed"}\n'
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/echo":
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path in ("/health", "/ready", "/api/data", "/events", "/boom", "/a11y"):
            # declared read-only endpoints: method-level 405, not 404 (schema tooling
            # such as schemathesis coverage expects 405/501 for undeclared methods)
            self._method_not_allowed()
        else:
            self._json(404, {"error": "not found", "path": path})

    def __getattr__(self, name):
        # catch-all for arbitrary/unlisted HTTP methods (PUT, TRACE, QUERY, ...):
        # schema tooling such as schemathesis coverage expects 405/501, never 404,
        # for methods not listed in the spec on declared paths
        if name.startswith("do_"):
            return self._unlisted_method
        raise AttributeError(name)

    def _unlisted_method(self):
        path = urlparse(self.path).path
        if path in ("/health", "/ready", "/api/data", "/events", "/boom", "/a11y"):
            self._method_not_allowed()
        else:
            self._json(404, {"error": "not found", "path": path})

    def _control(self, query):
        mode = (query.get("mode") or [""])[0]
        raw_code = (query.get("code") or [None])[0]
        if mode == "flap":
            self.server.control.flap(2)
            self._json(200, {"flap": 2})
        elif raw_code is not None:
            code = int(raw_code)
            self.server.control.pin(None if code == 0 else code)
            self._json(200, {"pinned": None if code == 0 else code})
        else:
            self._json(400, {"error": "use ?mode=flap or ?code=<n> (0 resets)"})

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(b": ping\n\n")
            self.wfile.write(b": ping\n\n")
            for n in (1, 2, 3):
                self.wfile.write(f"event: message\nid: {n}\ndata: {json.dumps({'n': n})}\n\n".encode())
            while True:  # hold open; keepalive writes surface client disconnects
                time.sleep(0.25)
                self.wfile.write(b": keepalive\n\n")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code, payload):
        body = (json.dumps(payload) + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, code, text):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        return  # silence request logging


class DemoSUTServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):  # keep disconnect noise out of stderr
        return


def serve() -> tuple[DemoSUTServer, int]:
    """Start the demo SUT on 127.0.0.1:0 and return (server, port)."""
    server = DemoSUTServer(("127.0.0.1", 0), DemoSUTHandler)
    server.control = ControlState()
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True, name="demo-sut").start()
    return server, port


if __name__ == "__main__":
    srv, port = serve()
    print(f"demo SUT on http://127.0.0.1:{port}", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
