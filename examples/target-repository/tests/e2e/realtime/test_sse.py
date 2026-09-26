import pytest
from quality_bundle.realtime import read_sse

@pytest.mark.realtime
def test_sse_stream(base_url):
    events = read_sse(f"{base_url}/events", limit=1)
    assert len(events) == 1
