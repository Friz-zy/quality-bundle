import pytest

@pytest.mark.api
def test_health(api):
    response = api.get("/health")
    assert response.status_code == 200

@pytest.mark.api
def test_not_found(api):
    response = api.get("/__e2e_missing_resource__")
    assert response.status_code == 404
