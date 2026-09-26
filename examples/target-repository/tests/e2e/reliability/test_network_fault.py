import pytest

@pytest.mark.reliability
def test_toxiproxy_is_available(toxiproxy):
    # Project tests create a proxy through toxiproxy.api_url, point the SUT/client at
    # its mapped port, inject latency/reset/timeout toxics, and assert public recovery behavior.
    assert toxiproxy.api_url.startswith("http://")
