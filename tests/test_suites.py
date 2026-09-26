from pathlib import Path
from quality_bundle.config import E2EConfig, PathsConfig
from quality_bundle.suites import discover

def test_discovery(tmp_path):
    base=tmp_path/"tests/e2e"
    (base/"cli").mkdir(parents=True)
    (base/"cli/test_one.py").write_text("def test_one(): pass")
    (base/"hurl").mkdir()
    (base/"hurl/health.hurl").write_text("GET http://localhost")
    cfg=E2EConfig(paths=PathsConfig(tests=str(base),hurl=str(base/"hurl")))
    assert discover(cfg)==["cli","hurl"]
