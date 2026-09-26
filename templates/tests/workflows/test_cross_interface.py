import os, pytest

@pytest.mark.workflow
def test_cross_interface_template(cli, api):
    if os.getenv("E2E_ENABLE_CROSS_INTERFACE_TEMPLATE") != "1":
        pytest.skip("Replace this template with a real CLI -> API -> CLI workflow")
    # 1. Create a resource through the CLI.
    # 2. Read or modify it through the public API.
    # 3. Read it again through the CLI.
    # 4. Assert only externally observable state.
