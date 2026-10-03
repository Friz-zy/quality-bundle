from pathlib import Path
from quality_bundle.config import E2EConfig, PathsConfig
from quality_bundle.suites import discover

def cfg_for(base):
    return E2EConfig(paths=PathsConfig(tests=str(base)))

def suite_dir(base,name):
    d=base/name;d.mkdir(parents=True)
    (d/f"test_{name}.py").write_text("def test_x(): pass")
    return d

def test_discovery(tmp_path):
    base=tmp_path/"tests/e2e"
    (base/"cli").mkdir(parents=True)
    (base/"cli/test_one.py").write_text("def test_one(): pass")
    (base/"hurl").mkdir()
    (base/"hurl/health.hurl").write_text("GET http://localhost")
    cfg=E2EConfig(paths=PathsConfig(tests=str(base),hurl=str(base/"hurl")))
    assert discover(cfg)==["cli","hurl"]

def test_discovery_performance_locustfile(tmp_path):
    base=tmp_path/"tests/e2e"
    (base/"performance").mkdir(parents=True)
    (base/"performance/locustfile.py").write_text("")
    assert discover(cfg_for(base))==["performance"]

def test_discovery_performance_k6_js(tmp_path):
    base=tmp_path/"tests/e2e"
    (base/"performance").mkdir(parents=True)
    (base/"performance/smoke.js").write_text("")
    assert discover(cfg_for(base))==["performance"]

def test_discovery_performance_absent(tmp_path):
    base=tmp_path/"tests/e2e"
    (base/"performance").mkdir(parents=True)
    (base/"performance/readme.md").write_text("")
    assert discover(cfg_for(base))==[]

def test_discovery_contract_container(tmp_path):
    base=tmp_path/"tests/e2e"
    suite_dir(base,"contract")
    suite_dir(base,"containers")
    assert discover(cfg_for(base))==["contract","container"]

def test_discovery_contract_container_empty_dirs_ignored(tmp_path):
    base=tmp_path/"tests/e2e"
    (base/"contract").mkdir(parents=True)
    (base/"containers").mkdir()
    assert discover(cfg_for(base))==[]
