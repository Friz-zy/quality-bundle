from quality_bundle.config import load_config
def test_defaults(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg=load_config()
    assert cfg.paths.tests=="tests/e2e"
    assert cfg.container.port==8080
