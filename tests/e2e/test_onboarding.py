"""E2E-059..061: bin/init-project onboarding contract."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "quality.example.toml"


def test_e2e_059_init_project_scaffolds_target(invoke_bin, tmp_path):
    target = tmp_path / "target"
    r = invoke_bin("init-project", [str(target)], cwd=tmp_path, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (target / "tests/e2e").is_dir()
    assert (target / "quality.toml").read_bytes() == EXAMPLE.read_bytes()
    assert "Available templates:" in r.stdout
    assert "  api" in r.stdout and "  cli" in r.stdout  # template list
    assert "cp -R" in r.stdout


def test_e2e_060_init_project_never_overwrites(invoke_bin, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "quality.toml").write_text("[app]\ncli = './mine'\n")
    r = invoke_bin("init-project", [str(target)], cwd=tmp_path, timeout=120)
    assert r.returncode == 0
    assert (target / "quality.toml").read_text() == "[app]\ncli = './mine'\n"


def test_e2e_061_init_project_default_target_is_cwd(invoke_bin, tmp_path):
    r = invoke_bin("init-project", [], cwd=tmp_path, timeout=120)
    assert r.returncode == 0
    assert (tmp_path / "tests/e2e").is_dir()
    assert (tmp_path / "quality.toml").read_bytes() == EXAMPLE.read_bytes()
