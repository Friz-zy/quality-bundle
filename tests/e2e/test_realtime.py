"""E2E-036..039: realtime helpers and realtime suite journey (T1, E2E-038 is T3 slow)."""
import asyncio, threading
import httpx, pytest
from quality_bundle.realtime import read_sse


def test_e2e_036_read_sse_parses_events_ignores_comments(demo_sut):
    events = read_sse(demo_sut + "/events", limit=2)
    assert [e["id"] for e in events] == ["1", "2"]
    assert all(e["event"] == "message" for e in events)
    assert all("ping" not in str(e) for e in events)  # ": ping" comments excluded


def test_e2e_037_read_sse_raises_on_non_200(demo_sut):
    with pytest.raises(httpx.HTTPStatusError):
        read_sse(demo_sut + "/boom", limit=1)


@pytest.mark.slow
def test_e2e_038_websocket_json_echo_roundtrip():
    websockets = pytest.importorskip("websockets")
    from quality_bundle.realtime import websocket_json

    async def handler(ws):
        async for message in ws:
            await ws.send(message)

    async def start():
        return await websockets.serve(handler, "127.0.0.1", 0)

    async def shutdown(server):
        server.close()
        await server.wait_closed()

    loop = asyncio.new_event_loop()
    server = loop.run_until_complete(start())
    server_thread = threading.Thread(target=loop.run_forever, daemon=True)
    server_thread.start()
    port = server.sockets[0].getsockname()[1]
    try:
        replies = asyncio.run(websocket_json(f"ws://127.0.0.1:{port}",
                                             [{"ping": 1}, {"n": 2}], timeout=10))
        assert replies == [{"ping": 1}, {"n": 2}]
    finally:
        # Drain the server on its own loop before stopping it, or the
        # handler/keepalive tasks are destroyed while still pending.
        asyncio.run_coroutine_threadsafe(shutdown(server), loop).result(timeout=10)
        loop.call_soon_threadsafe(loop.stop)
        server_thread.join(timeout=10)
        loop.close()


def test_e2e_039_realtime_suite_journey(invoke_cli, make_project, tmp_path):
    body = ("from quality_bundle.realtime import read_sse\n\n\n"
            "def test_sse_stream(base_url):\n"
            "    events = read_sse(base_url + '/events', limit=1)\n"
            "    assert events and events[0]['event'] == 'message'\n")
    root = make_project(tmp_path, {"realtime": [body]})
    art = tmp_path / "artifacts"
    r = invoke_cli(["run", "realtime"], cwd=root,
                   env_overrides={"QUALITY_ARTIFACTS_DIR": str(art)}, timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (art / "realtime-junit.xml").exists()
