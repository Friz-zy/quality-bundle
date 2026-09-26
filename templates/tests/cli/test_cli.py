import json
import pytest

@pytest.mark.cli
def test_cli_help(cli):
    result = cli.run("--help")
    assert result.returncode == 0
    assert result.stdout or result.stderr

@pytest.mark.cli
def test_cli_invalid_argument(cli):
    result = cli.run("--definitely-invalid")
    assert result.returncode != 0
