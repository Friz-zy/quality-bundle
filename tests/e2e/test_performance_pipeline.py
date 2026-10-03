"""E2E-040..050: performance pipeline - CSV parsing, thresholds, reports, discovery,
bin/performance guards and the full locust pipeline (T3 rows marked slow)."""
import importlib.util, json, shutil
from pathlib import Path
import pytest
from quality_bundle.config import PerformanceConfig
from quality_bundle.performance import read_locust_stats, evaluate, write_reports

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "tests/e2e/fixtures/data"


def require_locust():
    # locust pulls in gevent, which monkey-patches threading/sockets at import time
    # and deadlocks against the live demo SUT server thread - so it must never be
    # imported in this process; the pipeline under test runs it in a subprocess.
    if importlib.util.find_spec("locust") is None:
        pytest.skip("locust is not installed")

LOCUSTFILE = ("from locust import HttpUser, task, between\n\n\n"
              "class DemoUser(HttpUser):\n"
              "    wait_time = between(0.1, 0.2)\n\n"
              "    @task\n"
              "    def data(self):\n"
              "        self.client.get('/api/data')\n")


def stats_csv(tmp_path, name):
    shutil.copy(DATA / f"locust_stats_{name}.csv", tmp_path / f"{name}_stats.csv")
    return read_locust_stats(tmp_path / name)


def test_e2e_040_read_locust_stats_parses_aggregated_row(tmp_path):
    result = stats_csv(tmp_path, "good")
    assert result.requests == 1000
    assert result.failures == 5
    assert result.failure_rate == 0.005
    assert result.rps == 120.5
    assert result.p50_ms == 40.0
    assert result.p95_ms == 180.0
    assert result.p99_ms == 350.0
    assert result.average_ms == 85.2


def test_e2e_041_missing_aggregated_row_raises(tmp_path):
    shutil.copy(DATA / "locust_stats_noagg.csv", tmp_path / "noagg_stats.csv")
    with pytest.raises(RuntimeError, match="Aggregated Locust row not found"):
        read_locust_stats(tmp_path / "noagg")


@pytest.mark.parametrize("case,csv_name,cfg,expected", [
    ("pass", "good", PerformanceConfig(), []),
    ("fail", "bad", PerformanceConfig(), ["p95_ms: 600.0 must be <= 500.0"]),
    ("disabled", "bad", PerformanceConfig(p50_ms=None, p95_ms=None, p99_ms=None,
                                          failure_rate=None, min_rps=None), []),
])
def test_e2e_042_evaluate_verdicts(tmp_path, case, csv_name, cfg, expected):
    result = stats_csv(tmp_path, csv_name)
    assert evaluate(result, cfg) == expected


@pytest.mark.parametrize("failing", [False, True])
def test_e2e_043_write_reports(tmp_path, failing):
    result = stats_csv(tmp_path, "good")
    failures = ["p95_ms: 600.0 must be <= 500"] if failing else []
    art = tmp_path / "artifacts"
    write_reports(result, failures, art)
    payload = json.loads((art / "performance.json").read_text())
    assert payload["status"] == ("failed" if failing else "passed")
    assert payload["threshold_failures"] == failures
    assert payload["metrics"]["p95_ms"] == 180.0
    junit = (art / "performance-junit.xml").read_text()
    if failing:
        assert 'failures="1"' in junit and "Performance thresholds failed" in junit
    else:
        assert 'failures="0"' in junit and "Performance thresholds failed" not in junit


@pytest.mark.parametrize("filename,expected", [
    ("locustfile.py", ["performance"]),
    ("smoke.js", ["performance"]),
    ("readme.md", []),
])
def test_e2e_044_performance_discovery(invoke_cli, make_project, tmp_path, filename, expected):
    root = make_project(tmp_path, {})
    perf = root / "tests/e2e/performance"
    perf.mkdir()
    (perf / filename).write_text("")
    r = invoke_cli(["list"], cwd=root)
    assert r.returncode == 0
    assert r.stdout.strip().splitlines() == expected


def test_e2e_045_performance_requires_base_url(invoke_bin, tmp_path):
    r = invoke_bin("performance", cwd=tmp_path)  # scrubbed: no E2E_BASE_URL
    assert r.returncode == 1
    assert "E2E_BASE_URL is required" in r.stderr
    assert not (tmp_path / "artifacts").exists()


def test_e2e_046_performance_rejects_non_locust_backend(invoke_bin, tmp_path):
    r = invoke_bin("performance", cwd=tmp_path,
                   env_overrides={"E2E_BASE_URL": "http://127.0.0.1:1",
                                  "E2E_PERFORMANCE_BACKEND": "k6"})
    assert r.returncode == 2
    assert "error: default harness supports locust" in r.stderr


def test_e2e_047_quality_performance_delegates(invoke_cli, tmp_path):
    r = invoke_cli(["performance"], cwd=tmp_path)  # scrubbed: no E2E_BASE_URL
    assert r.returncode == 1
    assert "E2E_BASE_URL is required" in r.stderr


def test_e2e_047_run_records_performance_exit_code(invoke_cli, tmp_path):
    r = invoke_cli(["run", "performance"], cwd=tmp_path,
                   env_overrides={"QUALITY_ARTIFACTS_DIR": str(tmp_path / "artifacts")},
                   timeout=120)
    assert r.returncode == 1
    data = json.loads((tmp_path / "artifacts/summary.json").read_text())
    assert data["suites"][0]["suite"] == "performance"
    assert data["suites"][0]["exit_code"] == 1
    assert data["totals"]["failed"] == 1


@pytest.mark.slow
def test_e2e_048_locust_pipeline_green(invoke_bin, make_project, demo_sut, tmp_path):
    require_locust()
    root = make_project(tmp_path, {"performance": []})
    perf = root / "tests/e2e/performance"
    (perf / "locustfile.py").write_text(LOCUSTFILE)
    art = tmp_path / "artifacts"
    r = invoke_bin("performance", cwd=root,
                   env_overrides={"E2E_BASE_URL": demo_sut,
                                  "E2E_PERFORMANCE_FILE": str(perf / "locustfile.py"),
                                  "E2E_PERFORMANCE_USERS": "2",
                                  "E2E_PERFORMANCE_SPAWN_RATE": "2",
                                  "E2E_PERFORMANCE_DURATION": "10s",
                                  "QUALITY_ARTIFACTS_DIR": str(art)},
                   timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (art / "locust_stats.csv").exists()
    payload = json.loads((art / "performance.json").read_text())
    assert payload["status"] == "passed"
    assert (art / "performance-junit.xml").exists()


@pytest.mark.slow
def test_e2e_049_locust_threshold_failure(invoke_bin, make_project, demo_sut, tmp_path):
    require_locust()
    root = make_project(tmp_path, {"performance": []}, toml=(
        f'[app]\nbase_url = "{demo_sut}"\n\n[performance]\nmin_rps = 1e9\n'))
    perf = root / "tests/e2e/performance"
    (perf / "locustfile.py").write_text(LOCUSTFILE)
    art = tmp_path / "artifacts"
    r = invoke_bin("performance", cwd=root,
                   env_overrides={"E2E_BASE_URL": demo_sut,
                                  "E2E_PERFORMANCE_FILE": str(perf / "locustfile.py"),
                                  "E2E_PERFORMANCE_USERS": "2",
                                  "E2E_PERFORMANCE_SPAWN_RATE": "2",
                                  "E2E_PERFORMANCE_DURATION": "10s",
                                  "QUALITY_ARTIFACTS_DIR": str(art)},
                   timeout=240)
    assert r.returncode == 1
    assert "Threshold failures:" in r.stdout
    payload = json.loads((art / "performance.json").read_text())
    assert payload["status"] == "failed"


@pytest.mark.slow
def test_e2e_050_performance_reads_quality_toml_by_default(invoke_bin, demo_sut, tmp_path):
    require_locust()
    (tmp_path / "quality.toml").write_text(  # post-F6: no e2e.toml anywhere
        f'[app]\nbase_url = "{demo_sut}"\n\n[performance]\nusers = 2\n')
    art = tmp_path / "artifacts"
    locustfile = tmp_path / "locustfile.py"
    locustfile.write_text(LOCUSTFILE)
    r = invoke_bin("performance", cwd=tmp_path,
                   env_overrides={"E2E_BASE_URL": demo_sut,
                                  "E2E_PERFORMANCE_FILE": str(locustfile),
                                  "E2E_PERFORMANCE_SPAWN_RATE": "2",
                                  "E2E_PERFORMANCE_DURATION": "5s",
                                  "QUALITY_ARTIFACTS_DIR": str(art)},
                   timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    import csv
    with (art / "locust_stats_history.csv").open(newline="") as fh:
        user_counts = [int(row["User Count"]) for row in csv.DictReader(fh)]
    assert max(user_counts) == 2  # users came from [performance] in quality.toml
