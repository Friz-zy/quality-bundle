import asyncio, pytest
from quality_bundle.realtime import websocket_json

@pytest.mark.realtime
def test_websocket_echo(base_url):
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    replies = asyncio.run(websocket_json(ws_url, [{"type": "ping"}]))
    assert replies[0]["type"] == "pong"
