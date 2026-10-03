"""E2E-017: suite selection precedence matrix (8 params, exercised via the cheap plan mode)."""
import pytest

# (case, toml quality/app section, env overrides, args, expected first stdout line)
CASES = [
    ("explicit-beats-default", '[quality]\ndefault_suites = ["api"]\n',
     {}, ["plan", "cli"], "Suites: cli"),
    ("env-beats-toml-default", '[quality]\ndefault_suites = ["workflow"]\n',
     {"QUALITY_SUITES": "cli"}, ["plan"], "Suites: cli"),
    ("default-beats-discovery", '[quality]\ndefault_suites = ["cli"]\n',
     {}, ["plan"], "Suites: cli"),
    ("plain-discovery", None,
     {}, ["plan"], "Suites: cli, api"),
    ("fallback-replaces-discovery", '[quality]\nauto_discover = false\n',
     {}, ["plan"], "Suites: cli, api, workflow"),
    ("explicit-plus-exclude", '[quality]\nexclude_suites = ["cli"]\n',
     {}, ["plan", "cli", "api"], "Suites: api"),
    ("default-plus-exclude", '[quality]\ndefault_suites = ["cli", "api"]\nexclude_suites = ["api"]\n',
     {}, ["plan"], "Suites: cli"),
    ("env-comma-string", None,
     {"QUALITY_SUITES": "cli, api"}, ["plan"], "Suites: cli, api"),
]


@pytest.mark.parametrize("name,toml,env,args,expected", CASES, ids=[c[0] for c in CASES])
def test_e2e_017_selection_precedence(invoke_cli, make_project, tmp_path,
                                      name, toml, env, args, expected):
    root = make_project(tmp_path, {"cli": [], "api": []}, toml=toml)
    r = invoke_cli(args, cwd=root, env_overrides=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines()[0] == expected
