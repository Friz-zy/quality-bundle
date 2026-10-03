"""E2E-026: recursion guard - the repo's own tests/e2e must never self-discover.

The repo tree stays FLAT (no suite-named directories) so that running the harness
against its own repository discovers nothing. This guards future contributors from
accidentally creating tests/e2e/<suite>/ directories that would turn the harness
into its own SUT.
"""
from pathlib import Path
from quality_bundle.suites import ALL_SUITES

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_e2e_026_repo_root_discovery_empty(invoke_cli):
    r = invoke_cli(["list"], cwd=REPO_ROOT)
    assert r.returncode == 0
    assert r.stdout.rstrip("\n") == ""  # pinned: print("") emits exactly one newline


def test_e2e_026_flat_layout_no_suite_dirs():
    e2e_dir = REPO_ROOT / "tests" / "e2e"
    dirs = {p.name for p in e2e_dir.iterdir() if p.is_dir()}
    forbidden = set(ALL_SUITES) | {"hurl", "performance", "security"}
    clash = dirs & forbidden
    assert not clash, f"suite-named directories under tests/e2e would self-discover: {sorted(clash)}"
