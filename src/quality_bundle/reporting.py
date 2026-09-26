from __future__ import annotations
import json, time
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass
class SuiteResult:
    suite: str
    command: list[str]
    exit_code: int
    duration_seconds: float
    status: str

def write_summary(path: str | Path, results: list[SuiteResult]) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "passed" if all(r.exit_code == 0 for r in results) else "failed",
        "suites": [asdict(r) for r in results],
        "totals": {
            "suites": len(results),
            "passed": sum(r.exit_code == 0 for r in results),
            "failed": sum(r.exit_code != 0 for r in results),
            "duration_seconds": round(sum(r.duration_seconds for r in results), 3),
        },
    }
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
