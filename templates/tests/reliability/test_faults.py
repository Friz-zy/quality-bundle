import pytest

@pytest.mark.reliability
def test_network_fault_template(toxiproxy):
    # Create a proxy through toxiproxy.api_url and route a real public dependency through it.
    # Suggested cases: latency, timeout, reset, temporary outage, and recovery.
    assert toxiproxy.api_url.startswith("http://")
