"""E2E-062: bin/quality uv wrapper roundtrip (T3)."""
import shutil
import pytest


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not available")
def test_e2e_062_bin_quality_help_roundtrip(invoke_bin, tmp_path):
    r = invoke_bin("quality", ["--help"], cwd=tmp_path, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "usage:" in r.stdout
