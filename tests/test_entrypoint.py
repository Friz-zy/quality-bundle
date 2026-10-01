import os
import shlex
import subprocess
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parents[1] / "containers" / "entrypoint.sh"

def service_mode(*argv, podman_service=None, environ=None):
    """Evaluate the entrypoint decision function by sourcing it in bash.

    The child environment never inherits E2E_PODMAN_SERVICE from the ambient
    environment, so expectations hold regardless of how the suite is invoked;
    only the explicit podman_service override is applied.
    """
    args = " ".join(shlex.quote(a) for a in argv)
    script = (
        f"source {shlex.quote(str(ENTRYPOINT))}\n"
        f"podman_service_mode {args}\n"
    )
    env = dict(environ) if environ is not None else os.environ.copy()
    env.pop("E2E_PODMAN_SERVICE", None)
    if podman_service is not None:
        env["E2E_PODMAN_SERVICE"] = podman_service
    r = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True, env=env
    )
    return r.stdout.strip()

def test_entrypoint_syntax():
    subprocess.run(["bash", "-n", str(ENTRYPOINT)], check=True)

def test_diagnostics_skip_service():
    assert service_mode("quality", "doctor") == "skip"
    assert service_mode("quality", "list") == "skip"
    assert service_mode("quality", "plan") == "skip"

def test_runtime_commands_require_service():
    assert service_mode("quality", "test") == "required"
    assert service_mode("quality", "run") == "required"
    for suite in ("api", "workflow", "hurl", "reliability"):
        assert service_mode("quality", suite) == "required"

def test_unknown_quality_subcommand_fails_closed():
    assert service_mode("quality", "mystery") == "required"

def test_empty_command_skips_service():
    assert service_mode() == "skip"

def test_non_cli_entrypoints_attempt_service_optionally():
    assert service_mode("bash") == "optional"
    assert service_mode("/opt/quality-bundle/bin/podman-doctor") == "optional"

def test_quality_resolved_by_path_is_still_detected():
    assert service_mode("/opt/quality-bundle/.venv/bin/quality", "doctor") == "skip"
    assert service_mode("/opt/quality-bundle/.venv/bin/quality", "test") == "required"

def test_service_override_env():
    assert service_mode("bash", podman_service="1") == "required"
    assert service_mode("quality", "run", podman_service="0") == "skip"

def test_global_config_forms_route_diagnostics_to_skip():
    assert service_mode("quality", "--config", "quality.toml", "doctor") == "skip"
    assert service_mode("quality", "--config=quality.toml", "doctor") == "skip"
    assert service_mode("quality", "--config", "quality.toml", "list") == "skip"
    assert service_mode("quality", "--config=quality.toml", "plan") == "skip"

def test_global_config_forms_preserve_runtime_routing():
    assert service_mode("quality", "--config", "quality.toml", "run") == "required"
    assert service_mode("quality", "--config=quality.toml", "test") == "required"
    assert service_mode("quality", "--config", "quality.toml", "api") == "required"

def test_global_config_repeats_and_missing_value_are_handled():
    # argparse lets the last --config win; the subcommand still follows.
    assert service_mode("quality", "--config", "a", "--config=quality.toml", "doctor") == "skip"
    # argparse rejects a missing value; the error path needs no service.
    assert service_mode("quality", "--config") == "skip"

def test_ambient_service_env_does_not_change_expectations():
    polluted = dict(os.environ, E2E_PODMAN_SERVICE="1")
    assert service_mode("quality", "doctor", environ=polluted) == "skip"
    assert service_mode("quality", "run", environ=polluted) == "required"
    assert service_mode("bash", environ=polluted) == "optional"
