from __future__ import annotations
import csv, json
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

@dataclass
class PerformanceResult:
    requests: int
    failures: int
    failure_rate: float
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    average_ms: float

def read_locust_stats(prefix: str | Path) -> PerformanceResult:
    path = Path(f"{prefix}_stats.csv")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    total = next((r for r in rows if r.get("Name") == "Aggregated"), None)
    if total is None:
        raise RuntimeError(f"Aggregated Locust row not found in {path}")
    req = int(total["Request Count"])
    fail = int(total["Failure Count"])
    return PerformanceResult(
        requests=req,
        failures=fail,
        failure_rate=(fail / req) if req else 0.0,
        rps=float(total["Requests/s"]),
        p50_ms=float(total["50%"]),
        p95_ms=float(total["95%"]),
        p99_ms=float(total["99%"]),
        average_ms=float(total["Average Response Time"]),
    )

def evaluate(result: PerformanceResult, cfg) -> list[str]:
    failures = []
    checks = [
        ("p50_ms", cfg.p50_ms, lambda actual, limit: actual <= limit, "<="),
        ("p95_ms", cfg.p95_ms, lambda actual, limit: actual <= limit, "<="),
        ("p99_ms", cfg.p99_ms, lambda actual, limit: actual <= limit, "<="),
        ("failure_rate", cfg.failure_rate, lambda actual, limit: actual <= limit, "<="),
        ("rps", cfg.min_rps, lambda actual, limit: actual >= limit, ">="),
    ]
    for name, limit, predicate, op in checks:
        if limit is not None:
            actual = getattr(result, name)
            if not predicate(actual, limit):
                failures.append(f"{name}: {actual} must be {op} {limit}")
    return failures

def write_reports(result: PerformanceResult, threshold_failures: list[str], artifacts: Path) -> None:
    artifacts.mkdir(parents=True, exist_ok=True)
    payload = {"status": "passed" if not threshold_failures else "failed",
               "metrics": asdict(result), "threshold_failures": threshold_failures}
    (artifacts / "performance.json").write_text(json.dumps(payload, indent=2) + "\n")

    suite = Element("testsuite", name="performance", tests="1",
                    failures="1" if threshold_failures else "0")
    case = SubElement(suite, "testcase", classname="performance", name="thresholds")
    if threshold_failures:
        failure = SubElement(case, "failure", message="Performance thresholds failed")
        failure.text = "\n".join(threshold_failures)
    ElementTree(suite).write(artifacts / "performance-junit.xml",
                             encoding="utf-8", xml_declaration=True)
