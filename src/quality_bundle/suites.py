from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .config import E2EConfig

@dataclass(frozen=True)
class Suite:
    name: str
    kind: str
    marker: str | None = None
    path: str | None = None
    extra: str | None = None
    external: str | None = None

PYTEST_SUITES = {
    "cli": Suite("cli", "pytest", "cli"),
    "api": Suite("api", "pytest", "api"),
    "workflow": Suite("workflow", "pytest", "workflow"),
    "bdd": Suite("bdd", "pytest", "bdd", extra="bdd"),
    "ui": Suite("ui", "pytest", "ui", extra="ui"),
    "accessibility": Suite("accessibility", "pytest", "accessibility", extra="accessibility"),
    "mobile": Suite("mobile", "pytest", "mobile", extra="mobile"),
    "grpc": Suite("grpc", "pytest", "grpc", extra="grpc"),
    "realtime": Suite("realtime", "pytest", "realtime", extra="realtime"),
    "compatibility": Suite("compatibility", "pytest", "compatibility"),
    "reliability": Suite("reliability", "pytest", "reliability", extra="reliability"),
}
EXTERNAL_SUITES = {
    "hurl": Suite("hurl", "external", external="hurl"),
    "schema": Suite("schema", "external", extra="api", external="schema"),
    "performance": Suite("performance", "external", external="performance"),
    "security": Suite("security", "external", external="security"),
}
ALL_SUITES = {**PYTEST_SUITES, **EXTERNAL_SUITES}

def discover(config: E2EConfig) -> list[str]:
    base = Path(config.paths.tests)
    found: list[str] = []
    aliases = {"workflow": "workflows", "schema": None}
    for name in PYTEST_SUITES:
        directory = base / aliases.get(name, name)
        if directory.exists() and any(directory.rglob("test_*.py")):
            found.append(name)
    if Path(config.paths.hurl).exists() and any(Path(config.paths.hurl).glob("*.hurl")):
        found.append("hurl")
    if config.paths.openapi:
        found.append("schema")
    if (base / "performance").exists() and any((base / "performance").glob("*.js")):
        found.append("performance")
    if (base / "security").exists():
        found.append("security")
    excluded = set(config.quality.exclude_suites)
    return [x for x in found if x not in excluded]
