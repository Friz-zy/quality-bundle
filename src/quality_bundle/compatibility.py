from __future__ import annotations
import os, subprocess
from dataclasses import dataclass

@dataclass(frozen=True)
class VersionArtifact:
    version: str
    cli: str | None = None
    image: str | None = None

def artifacts_from_env(versions: tuple[str, ...]) -> list[VersionArtifact]:
    result = []
    for version in versions:
        key = version.upper().replace(".", "_").replace("-", "_")
        result.append(VersionArtifact(
            version,
            os.getenv(f"E2E_COMPAT_{key}_CLI"),
            os.getenv(f"E2E_COMPAT_{key}_IMAGE"),
        ))
    return result

def run_upgrade_command(template: str, old: str, new: str) -> subprocess.CompletedProcess[str]:
    command = template.format(old=old, new=new)
    return subprocess.run(command, shell=True, text=True, capture_output=True, check=False)
