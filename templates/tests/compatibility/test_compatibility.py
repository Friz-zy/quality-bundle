import pytest

@pytest.mark.compatibility
def test_configured_versions_have_public_artifacts(compatibility_artifacts):
    if not compatibility_artifacts:
        pytest.skip("No compatibility matrix configured")
    for artifact in compatibility_artifacts:
        assert artifact.cli or artifact.image, f"No artifact configured for {artifact.version}"
