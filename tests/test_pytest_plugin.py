"""Fixture-wiring regression tests for the quality-bundle pytest plugin.

The behavioral regression (a competing ``base_url`` fixture must not break the
framework's ``api`` fixture) lives in tests/e2e/test_plugin_fixtures.py; these
unit checks pin the wiring itself.
"""
import inspect

from quality_bundle import pytest_plugin as plugin


def _params(fixture) -> tuple[str, ...]:
    func = getattr(fixture, "_fixture_function", fixture)
    return tuple(inspect.signature(func).parameters)


def test_api_fixture_depends_on_unique_base_url_name():
    assert _params(plugin.api) == ("e2e_base_url",)


def test_legacy_base_url_is_deprecated_alias_of_e2e_base_url():
    assert _params(plugin.base_url) == ("e2e_base_url",)
    assert _params(plugin.e2e_base_url) == ("app_env",)


def test_deprecation_documented_on_legacy_fixture():
    assert "DEPRECATED" in (plugin.base_url._fixture_function.__doc__ or "")
