"""E2E-001..004: quality doctor contract (T1).

E2E-001 pins doctor always exits 0 (intentional behavior, see CHARACTERIZATION.md).
"""
import shutil

import pytest

DOCTOR_KEYS = ["python", "hurl", "k6", "docker", "podman", "tests",
               "cli", "base_url", "image", "openapi", "discovered"]


def doctor_map(result):
    pairs = (line.split(None, 1) for line in result.stdout.splitlines() if line.strip())
    return {key: value for key, value in pairs}


def test_e2e_001_doctor_pins_11_keys_and_exit_0(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": [], "api": []}, toml='[paths]\ntests = "tests/e2e"\n')
    r = invoke_cli(["doctor"], cwd=root)
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert [line.split(None, 1)[0] for line in lines] == DOCTOR_KEYS
    d = doctor_map(r)
    # doctor must reflect actual Hurl availability. invoke_cli inherits this
    # process's PATH (only E2E_*/QUALITY_* are scrubbed), so the expected value
    # is derived from that same PATH; CI installs Hurl 8.0.1 and reports its path.
    assert d["hurl"] == (shutil.which("hurl") or "not installed")
    assert d["k6"] == "not installed"
    assert d["tests"] == "tests/e2e"
    assert d["cli"] == "not configured"
    assert d["base_url"] == "not configured"
    assert d["image"] == "not configured"
    assert d["openapi"] == "not configured"
    assert d["discovered"] == "cli,api"


@pytest.mark.parametrize("case", ["present", "missing"])
def test_e2e_002_doctor_config(invoke_cli, make_project, tmp_path, case):
    if case == "present":
        root = make_project(tmp_path, {"cli": []}, toml=(
            '[app]\nbase_url = "http://127.0.0.1:1"\ncli = "mycli"\n\n'
            '[paths]\ntests = "tests/e2e"\nopenapi = "openapi/mini.yaml"\n'))
        (root / "openapi").mkdir()
        (root / "openapi/mini.yaml").write_text(
            "openapi: 3.0.3\ninfo: {title: t, version: '1'}\npaths: {}\n")
        r = invoke_cli(["--config", str(root / "quality.toml"), "doctor"], cwd=root)
        assert r.returncode == 0
        d = doctor_map(r)
        assert d["base_url"] == "http://127.0.0.1:1"
        assert d["cli"] == "mycli"
        assert d["openapi"] == "openapi/mini.yaml"
        assert "cli" in d["discovered"] and "schema" in d["discovered"]
    else:
        root = make_project(tmp_path, {"cli": []})
        r = invoke_cli(["--config", str(tmp_path / "missing.toml"), "doctor"], cwd=root)
        assert r.returncode == 0
        d = doctor_map(r)
        assert d["tests"] == "tests/e2e"
        assert d["cli"] == "not configured"
        assert d["base_url"] == "not configured"


@pytest.mark.parametrize("env_key,field,value", [
    ("E2E_BASE_URL", "base_url", "http://127.0.0.1:9"),
    ("E2E_IMAGE", "image", "registry/sut:1"),
    ("E2E_TESTS_PATH", "tests", "tests/custom"),
    ("E2E_OPENAPI", "openapi", "openapi/custom.yaml"),
])
def test_e2e_003_doctor_env_overrides(invoke_cli, make_project, tmp_path, env_key, field, value):
    root = make_project(tmp_path, {"cli": []})
    r = invoke_cli(["doctor"], cwd=root, env_overrides={env_key: value})
    assert r.returncode == 0
    assert doctor_map(r)[field] == value


def test_e2e_004_quality_config_selects_file(invoke_cli, make_project, tmp_path):
    root = make_project(tmp_path, {"cli": []}, toml='[app]\nbase_url = "http://a"\n')
    (root / "other.toml").write_text('[app]\nbase_url = "http://b"\n')
    r = invoke_cli(["doctor"], cwd=root, env_overrides={"QUALITY_CONFIG": "other.toml"})
    assert r.returncode == 0
    assert doctor_map(r)["base_url"] == "http://b"
    r2 = invoke_cli(["doctor"], cwd=root)
    assert doctor_map(r2)["base_url"] == "http://a"
