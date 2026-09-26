import pytest

@pytest.mark.compatibility
def test_compatibility_artifacts_are_resolvable(compatibility_artifacts):
    if not compatibility_artifacts:
        pytest.skip("No compatibility versions configured")
    for artifact in compatibility_artifacts:
        assert artifact.cli or artifact.image, (
            f"No public artifact configured for compatibility version {artifact.version}"
        )
