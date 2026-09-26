import os, pytest

@pytest.mark.grpc
def test_grpc_template():
    endpoint = os.getenv("E2E_GRPC_ENDPOINT")
    if not endpoint:
        pytest.skip("E2E_GRPC_ENDPOINT is not configured")
    # Use generated public protobuf stubs or reflection against the public endpoint.
