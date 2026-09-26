import os, pytest

@pytest.mark.mobile
def test_mobile_template():
    if not os.getenv("E2E_APPIUM_URL"):
        pytest.skip("Configure Appium and project-specific capabilities")
    # Create the Appium driver here.
    # Keep selectors, capabilities, and product flows in the target repository.
