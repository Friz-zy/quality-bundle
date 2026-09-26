import pytest
@pytest.mark.cli
def test_version(cli):
    result=cli.run("--version").assert_ok()
    assert result.stdout.strip()
