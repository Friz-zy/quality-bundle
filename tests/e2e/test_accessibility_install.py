"""E2E-063/064: accessibility journey and install-ui smoke (T3 slow / T3)."""
import shutil
from pathlib import Path
import pytest


def _chromium_installed():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


ACCESSIBILITY_BODY = (
    "import os\n"
    "import pytest\n"
    "pytestmark = pytest.mark.accessibility\n\n\n"
    "def test_a11y_clean_page():\n"
    "    from playwright.sync_api import sync_playwright\n"
    "    from axe_playwright_python.sync_playwright import Axe\n"
    "    with sync_playwright() as p:\n"
    "        browser = p.chromium.launch()\n"
    "        page = browser.new_page()\n"
    "        page.goto(os.environ['E2E_BASE_URL'] + '/a11y')\n"
    "        results = Axe().run(page)\n"
    "        browser.close()\n"
    "    assert results.violations_count == 0, results.generate_report()\n")


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not available")
def test_e2e_063_accessibility_axe_scan(invoke_bin, make_project, demo_sut, tmp_path):
    pytest.importorskip("playwright")
    pytest.importorskip("axe_playwright_python")
    if not _chromium_installed():
        pytest.skip("chromium browser binary is not installed")
    root = make_project(tmp_path, {"accessibility": [ACCESSIBILITY_BODY]})
    r = invoke_bin("accessibility", cwd=root,
                   env_overrides={"E2E_BASE_URL": demo_sut}, timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not available")
def test_e2e_064_install_ui_help_side_effect_free(invoke_bin, tmp_path):
    r = invoke_bin("install-ui", ["--help"], cwd=tmp_path, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "playwright install" in r.stdout
