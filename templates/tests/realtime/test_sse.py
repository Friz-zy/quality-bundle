import os, pytest
from quality_bundle.realtime import read_sse

@pytest.mark.realtime
def test_sse_template(e2e_base_url):
    path = os.getenv("E2E_SSE_PATH")
    if not path:
        pytest.skip("E2E_SSE_PATH is not configured")
    events = read_sse(f"{e2e_base_url}{path}", limit=1)
    assert events
