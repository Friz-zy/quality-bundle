"""E2E-027 canary: the framework's own plugin fixtures dogfood against the demo SUT.

The plugin fixtures (e2e_config, artifacts_dir, app_env, e2e_base_url, api; legacy
base_url alias) are session-scoped and cache on first request, so artifacts redirection
and env stamping happen in the conftest e2e_config/demo_sut fixtures (dependency-based,
ordering-proof) instead of function-scoped monkeypatch, which would run too late and
ScopeMismatch against session fixtures.
"""
from pathlib import Path


def test_plugin_fixtures_dogfood_demo_sut(demo_sut, e2e_config, e2e_base_url, base_url, api,
                                          artifacts_dir, tmp_path_factory):
    assert e2e_base_url == demo_sut
    assert base_url == e2e_base_url  # legacy alias resolves to the same URL
    assert e2e_config.app.base_url == demo_sut
    # artifacts live in the session tmp dir, never in the repo (plan §8)
    assert artifacts_dir == Path(e2e_config.paths.artifacts)
    assert artifacts_dir.is_dir()
    assert artifacts_dir.is_relative_to(tmp_path_factory.getbasetemp())
    response = api.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
