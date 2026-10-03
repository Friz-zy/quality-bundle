from __future__ import annotations
import argparse, os, shutil, subprocess, sys, time
from pathlib import Path
from .config import load_config
from .reporting import SuiteResult, write_summary
from .suites import ALL_SUITES, PYTEST_SUITES, discover

def execute(argv, env=None):
    print("+", " ".join(map(str, argv)), flush=True)
    started = time.monotonic()
    code = subprocess.call(argv, env=env)
    return code, time.monotonic() - started

def pytest_command(cfg, cfg_path, marker, suite):
    artifact = Path(cfg.paths.artifacts)
    artifact.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "-m", "pytest", cfg.paths.tests, "-m", marker]
    if cfg_path:
        args += ["--e2e-config", cfg_path]
    if cfg.quality.junit:
        args += ["--junitxml", str(artifact / f"{suite}-junit.xml")]
    if cfg.quality.parallel:
        args += ["-n", "auto"]
    return args

def external_command(name, cfg):
    artifact = Path(cfg.paths.artifacts); artifact.mkdir(parents=True, exist_ok=True)
    kit = Path(__file__).resolve().parents[2]
    if name == "hurl":
        cases = sorted(map(str, Path(cfg.paths.hurl).glob("*.hurl")))
        if not shutil.which("hurl"):
            raise RuntimeError("Hurl is not installed")
        if not cfg.app.base_url:
            raise RuntimeError("base_url is required for Hurl")
        return ["hurl","--test","--variable",f"base_url={cfg.app.base_url.rstrip('/')}",
                "--report-junit",str(artifact/"hurl-junit.xml"),*cases]
    if name == "schema":
        if not cfg.paths.openapi:
            raise RuntimeError("OpenAPI schema is not configured")
        if not shutil.which("schemathesis"):
            raise RuntimeError("Schemathesis is not installed")
        args=[shutil.which("schemathesis"),"run",cfg.paths.openapi,
              "--report","junit","--report-junit-path",str(artifact/"schema-junit.xml")]
        if not cfg.paths.openapi.startswith(("http://","https://")):
            if not cfg.app.base_url:
                raise RuntimeError("base_url is required for a local OpenAPI schema")
            args += ["--url",cfg.app.base_url]
        return args
    if name == "performance":
        return [str(kit/"bin/performance")]
    if name == "security":
        return [str(kit/"bin/security")]
    raise RuntimeError(f"Unknown external suite: {name}")

def suites_for(cfg, explicit):
    if explicit:
        names = explicit
    elif cfg.quality.default_suites:
        names = list(cfg.quality.default_suites)
    elif cfg.quality.auto_discover:
        names = discover(cfg)
    else:
        names = ["cli","api","workflow"]
    unknown = [x for x in names if x not in ALL_SUITES]
    if unknown:
        raise RuntimeError(f"Unknown suites: {', '.join(unknown)}")
    excluded = set(cfg.quality.exclude_suites)
    return [x for x in names if x not in excluded]

def run_quality(cfg_path, explicit, dry_run=False):
    cfg=load_config(cfg_path)
    try:
        names=suites_for(cfg,explicit)
    except RuntimeError as exc:
        print(f"error: {exc}",file=sys.stderr)
        return 2
    if not names:
        print("No suites discovered.")
        if cfg.quality.json_summary:
            write_summary(Path(cfg.paths.artifacts)/"summary.json",[])
        return 0
    results=[]
    print("Suites:", ", ".join(names))
    for name in names:
        suite=ALL_SUITES[name]
        try:
            cmd=(pytest_command(cfg,cfg_path,suite.marker,name)
                 if suite.kind=="pytest" else external_command(name,cfg))
            if dry_run:
                print(f"{name:16} {' '.join(cmd)}")
                continue
            env=os.environ.copy()
            if suite.extra:
                env["QUALITY_EXTRAS"]=suite.extra
            code,duration=execute(cmd,env)
        except Exception as exc:
            print(f"{name}: {exc}",file=sys.stderr)
            code,duration=2,0.0
            cmd=[]
        results.append(SuiteResult(name,list(map(str,cmd)),code,round(duration,3),
                                   "passed" if code==0 else "failed"))
        if code and cfg.quality.fail_fast:
            break
    if dry_run:
        return 0
    if cfg.quality.json_summary:
        write_summary(Path(cfg.paths.artifacts)/"summary.json",results)
    print("\nQuality summary")
    for r in results:
        print(f"{r.suite:16} {r.status:7} {r.duration_seconds:8.3f}s")
    return 0 if all(r.exit_code==0 for r in results) else 1

def doctor(cp):
    c=load_config(cp)
    discovered=discover(c)
    for k,v in {
        "python":sys.executable,
        "hurl":shutil.which("hurl") or "not installed",
        "k6":shutil.which("k6") or "not installed",
        "docker":shutil.which("docker") or "not installed",
        "podman":shutil.which("podman") or "not installed",
        "tests":c.paths.tests,
        "cli":c.app.cli or "not configured",
        "base_url":c.app.base_url or "not configured",
        "image":c.container.image or "not configured",
        "openapi":c.paths.openapi or "not configured",
        "discovered":",".join(discovered) or "none",
    }.items():
        print(f"{k:12} {v}")
    return 0

def split_argv(argv):
    """Split raw argv before argparse: return (start, cmd) where argv[start] is the
    subcommand token if it is a suite name or `test`, else None.

    Suite/test subcommands pass everything after them straight to pytest. argparse
    REMAINDER cannot capture a leading option-like token (`quality cli -k health`
    used to die with 'unrecognized arguments: -k'), so the token position is found
    manually and only the head is parsed. Only the leading global --config form is
    consumed here; flags behind the subcommand stay pytest passthrough.
    """
    start = 0
    if argv and argv[0] == "--config":
        start = 2 if len(argv) > 1 else 1
    elif argv and argv[0].startswith("--config="):
        start = 1
    cmd = argv[start] if start < len(argv) else None
    if cmd is not None and not cmd.startswith("-") and (cmd in ALL_SUITES or cmd == "test"):
        return start, cmd
    return start, None


def main():
    argv = sys.argv[1:]
    start, cmd = split_argv(argv)
    if (cmd is None and start < len(argv) and not argv[start].startswith("-")
            and argv[start] not in ("run", "plan", "list", "doctor", "test")):
        print(f"error: Unknown suites: {argv[start]}", file=sys.stderr)
        raise SystemExit(2)
    p = argparse.ArgumentParser(prog="quality")
    p.add_argument("--config")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("run", help="Discover and run configured quality suites")
    q.add_argument("suites", nargs="*")
    plan = sub.add_parser("plan", help="Show commands without executing them")
    plan.add_argument("suites", nargs="*")
    sub.add_parser("list", help="List discovered suites")
    sub.add_parser("doctor")
    for name in ALL_SUITES:
        sub.add_parser(name)  # registered for --help/choices; dispatched manually above
    sub.add_parser("test")

    extra = []
    if cmd is not None:
        a, _ = p.parse_known_args(argv[:start + 1])
        extra = argv[start + 1:]
    else:
        a = p.parse_args(argv)
    cfg = load_config(a.config)
    if cmd == "test":
        built = [sys.executable, "-m", "pytest", cfg.paths.tests]
        if a.config:
            built += ["--e2e-config", a.config]
        code, _ = execute(built + extra)
    elif cmd in ALL_SUITES:
        suite = ALL_SUITES[cmd]
        try:
            built = (pytest_command(cfg, a.config, suite.marker, cmd)
                     if suite.kind == "pytest" else external_command(cmd, cfg))
            code, _ = execute(built + extra)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            code = 2
    elif a.cmd == "doctor":
        code = doctor(a.config)
    elif a.cmd == "list":
        print("\n".join(discover(cfg)))
        code = 0
    elif a.cmd == "run":
        code = run_quality(a.config, a.suites)
    else:
        code = run_quality(a.config, a.suites, True)
    raise SystemExit(code)

if __name__=="__main__":
    main()
