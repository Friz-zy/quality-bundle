import sys
from quality_bundle.cli_runner import CLI
def test_cli_runner():
    r=CLI(sys.executable).run("-c","print('ok')")
    assert r.returncode==0
    assert r.stdout.strip()=="ok"
