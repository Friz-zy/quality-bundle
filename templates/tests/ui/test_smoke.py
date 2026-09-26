import pytest
from playwright.sync_api import Page, expect

@pytest.mark.ui
def test_home_page(page: Page, e2e_config):
    if not e2e_config.app.base_url:
        pytest.skip("base_url is not configured")
    page.goto(e2e_config.app.base_url)
    expect(page.locator("body")).to_be_visible()
