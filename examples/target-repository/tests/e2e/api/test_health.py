import pytest
@pytest.mark.api
def test_health(api):
    assert api.get("/health").status_code==200
