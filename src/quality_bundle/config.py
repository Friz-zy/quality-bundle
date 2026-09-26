from __future__ import annotations
import os, tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class AppConfig:
    cli: str | None = None
    base_url: str | None = None
    health_path: str = "/health"
    startup_timeout: float = 30.0

@dataclass(frozen=True)
class ContainerConfig:
    image: str | None = None
    port: int = 8080

@dataclass(frozen=True)
class PathsConfig:
    tests: str = "tests/e2e"
    artifacts: str = "artifacts/quality"
    hurl: str = "tests/e2e/hurl"
    openapi: str | None = None

@dataclass(frozen=True)
class QualityConfig:
    auto_discover: bool = True
    fail_fast: bool = False
    parallel: bool = False
    default_suites: tuple[str, ...] = ()
    exclude_suites: tuple[str, ...] = ()
    junit: bool = True
    json_summary: bool = True


@dataclass(frozen=True)
class PerformanceConfig:
    backend: str = "locust"
    users: int = 50
    spawn_rate: float = 5.0
    duration: str = "1m"
    warmup: str = "10s"
    headless: bool = True
    p50_ms: float | None = None
    p95_ms: float | None = 500.0
    p99_ms: float | None = 1000.0
    failure_rate: float | None = 0.01
    min_rps: float | None = None

@dataclass(frozen=True)
class CompatibilityConfig:
    versions: tuple[str, ...] = ()
    current: str | None = None

@dataclass(frozen=True)
class ReliabilityConfig:
    toxiproxy_image: str = "ghcr.io/shopify/toxiproxy:2.12.0"

@dataclass(frozen=True)
class E2EConfig:
    app: AppConfig = field(default_factory=AppConfig)
    container: ContainerConfig = field(default_factory=ContainerConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    compatibility: CompatibilityConfig = field(default_factory=CompatibilityConfig)
    reliability: ReliabilityConfig = field(default_factory=ReliabilityConfig)

def _table(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"[{name}] must be a TOML table")
    return value

def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(x.strip() for x in value.split(",") if x.strip())
    return tuple(str(x) for x in value)

def load_config(path=None) -> E2EConfig:
    p = Path(path or os.getenv("QUALITY_CONFIG", "quality.toml"))
    data: dict[str, Any] = {}
    if p.exists():
        with p.open("rb") as f:
            data = tomllib.load(f)

    a = _table(data, "app")
    c = _table(data, "container")
    q = _table(data, "paths")
    quality = _table(data, "quality")
    perf = _table(data, "performance")
    compat = _table(data, "compatibility")
    reliability = _table(data, "reliability")

    return E2EConfig(
        app=AppConfig(
            os.getenv("E2E_CLI", a.get("cli")),
            os.getenv("E2E_BASE_URL", a.get("base_url")),
            os.getenv("E2E_HEALTH_PATH", a.get("health_path", "/health")),
            float(os.getenv("E2E_STARTUP_TIMEOUT", a.get("startup_timeout", 30))),
        ),
        container=ContainerConfig(
            os.getenv("E2E_IMAGE", c.get("image")),
            int(os.getenv("E2E_PORT", c.get("port", 8080))),
        ),
        paths=PathsConfig(
            os.getenv("E2E_TESTS_PATH", q.get("tests", "tests/e2e")),
            os.getenv("QUALITY_ARTIFACTS_DIR", q.get("artifacts", "artifacts/quality")),
            os.getenv("E2E_HURL_PATH", q.get("hurl", "tests/e2e/hurl")),
            os.getenv("E2E_OPENAPI", q.get("openapi")),
        ),
        quality=QualityConfig(
            auto_discover=str(os.getenv("QUALITY_AUTO_DISCOVER", quality.get("auto_discover", True))).lower() not in ("0","false","no"),
            fail_fast=str(os.getenv("QUALITY_FAIL_FAST", quality.get("fail_fast", False))).lower() in ("1","true","yes"),
            parallel=str(os.getenv("QUALITY_PARALLEL", quality.get("parallel", False))).lower() in ("1","true","yes"),
            default_suites=_tuple(os.getenv("QUALITY_SUITES") or quality.get("default_suites")),
            exclude_suites=_tuple(os.getenv("QUALITY_EXCLUDE_SUITES") or quality.get("exclude_suites")),
            junit=bool(quality.get("junit", True)),
            json_summary=bool(quality.get("json_summary", True)),
        ),
        performance=PerformanceConfig(
            backend=os.getenv("E2E_PERFORMANCE_BACKEND", perf.get("backend", "locust")),
            users=int(os.getenv("E2E_PERFORMANCE_USERS", perf.get("users", 50))),
            spawn_rate=float(os.getenv("E2E_PERFORMANCE_SPAWN_RATE", perf.get("spawn_rate", 5))),
            duration=os.getenv("E2E_PERFORMANCE_DURATION", perf.get("duration", "1m")),
            warmup=os.getenv("E2E_PERFORMANCE_WARMUP", perf.get("warmup", "10s")),
            headless=True,
            p50_ms=float(perf["p50_ms"]) if perf.get("p50_ms") is not None else None,
            p95_ms=float(perf["p95_ms"]) if perf.get("p95_ms") is not None else 500.0,
            p99_ms=float(perf["p99_ms"]) if perf.get("p99_ms") is not None else 1000.0,
            failure_rate=float(perf["failure_rate"]) if perf.get("failure_rate") is not None else 0.01,
            min_rps=float(perf["min_rps"]) if perf.get("min_rps") is not None else None,
        ),
        compatibility=CompatibilityConfig(
            versions=_tuple(os.getenv("E2E_COMPAT_VERSIONS") or compat.get("versions")),
            current=os.getenv("E2E_CURRENT_VERSION", compat.get("current")),
        ),
        reliability=ReliabilityConfig(
            toxiproxy_image=os.getenv("E2E_TOXIPROXY_IMAGE", reliability.get("toxiproxy_image", "ghcr.io/shopify/toxiproxy:2.12.0"))
        ),
    )
