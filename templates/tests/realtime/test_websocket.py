import asyncio, os, pytest
from quality_bundle.realtime import websocket_json

@pytest.mark.realtime
def test_websocket_template(base_url):
    path = os.getenv("E2E_WEBSOCKET_PATH")
    if not path:
        pytest.skip("E2E_WEBSOCKET_PATH is not configured")
    url = base_url.replace("http://","ws://").replace("https://","wss://") + path
    replies = asyncio.run(websocket_json(url, [{"type":"ping"}]))
    assert replies
