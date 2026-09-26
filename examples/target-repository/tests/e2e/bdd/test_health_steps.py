import pytest
from pytest_bdd import scenarios,when,then,parsers
pytestmark=pytest.mark.bdd
scenarios("features/health.feature")
@when("the client requests the health endpoint",target_fixture="response")
def request_health(api):return api.get("/health")
@then(parsers.parse("the response status is {status:d}"))
def response_status(response,status):assert response.status_code==status
