import pytest
from axe_playwright_python.sync_playwright import Axe

pytestmark = [pytest.mark.ui, pytest.mark.accessibility]

def test_home_has_no_automatically_detected_violations(page, e2e_config):
    if not e2e_config.app.base_url:
        pytest.skip("base_url is not configured")
    page.goto(e2e_config.app.base_url)
    results = Axe().run(page)
    assert results.response["violations"] == []
