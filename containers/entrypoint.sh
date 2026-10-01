#!/usr/bin/env bash
set -euo pipefail

# Decide how the nested Podman API service is handled for the invoked command.
# Testcontainers consumes its socket; no host Docker socket is mounted.
#   required  - quality runtime commands (run/test/suites may use
#               Testcontainers): fail closed if the socket cannot start
#   optional  - any other entrypoint (debug shells, the podman-doctor probe):
#               attempt to start it, warn and continue on failure
#   skip      - diagnostics (doctor/list/plan) run without it, so they work on
#               executors that forbid nested user namespaces
podman_service_mode() {
  case "${E2E_PODMAN_SERVICE:-auto}" in
    0|false|off|no) echo skip; return ;;
    1|true|on|yes) echo required; return ;;
  esac
  local argv0="${1:-}"
  case "$argv0" in
    "") echo skip; return ;;
  esac
  case "${argv0##*/}" in
    quality|quality-bundle) ;;
    *) echo optional; return ;;
  esac
  # Locate the subcommand: argparse accepts global options such as --config
  # only before it, so skip both --config VALUE and --config=VALUE forms.
  local i sub="" arg
  for ((i = 2; i <= $#; i++)); do
    arg="${!i}"
    case "$arg" in
      --config) i=$((i + 1)) ;;
      --config=*) ;;
      *) sub="$arg"; break ;;
    esac
  done
  case "$sub" in
    doctor|list|plan|"") echo skip ;;
    *) echo required ;;
  esac
}

# Sourcing this file (entrypoint tests) must expose only the function above.
[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0

export HOME="${HOME:-/home/podman}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/podman-run-$(id -u)}"

mkdir -p \
  "$XDG_CONFIG_HOME/containers" \
  "$XDG_DATA_HOME/containers/storage" \
  "$XDG_RUNTIME_DIR" \
  /workspace/artifacts/quality
chmod 0700 "$XDG_RUNTIME_DIR"

MODE="${E2E_PODMAN_MODE:-restricted}"
case "$MODE" in
  restricted)
    cp /opt/quality-bundle/containers/rootless-vfs/storage.conf "$XDG_CONFIG_HOME/containers/storage.conf"
    cp /opt/quality-bundle/containers/rootless-vfs/containers.conf "$XDG_CONFIG_HOME/containers/containers.conf"
    ;;
  standard)
    cp /opt/quality-bundle/containers/rootless-standard/storage.conf "$XDG_CONFIG_HOME/containers/storage.conf"
    cp /opt/quality-bundle/containers/rootless-standard/containers.conf "$XDG_CONFIG_HOME/containers/containers.conf"
    ;;
  *)
    echo "error: E2E_PODMAN_MODE must be restricted or standard" >&2
    exit 2
    ;;
esac
cp /opt/quality-bundle/containers/rootless-vfs/registries.conf "$XDG_CONFIG_HOME/containers/registries.conf"


# Expose Podman's Docker-compatible API only when the invoked command needs it.
SERVICE_MODE="$(podman_service_mode "$@")"

if [[ "$SERVICE_MODE" != "skip" ]]; then
  export DOCKER_HOST="${DOCKER_HOST:-unix://$XDG_RUNTIME_DIR/podman/podman.sock}"
  mkdir -p "$XDG_RUNTIME_DIR/podman"
  podman system service --time=0 "$DOCKER_HOST" \
    >"$XDG_RUNTIME_DIR/podman-service.log" 2>&1 &
  PODMAN_SERVICE_PID=$!

  for _ in $(seq 1 50); do
    [[ -S "$XDG_RUNTIME_DIR/podman/podman.sock" ]] && break
    sleep 0.1
  done

  if [[ -S "$XDG_RUNTIME_DIR/podman/podman.sock" ]]; then
    export TESTCONTAINERS_RYUK_DISABLED="${TESTCONTAINERS_RYUK_DISABLED:-true}"
  elif [[ "$SERVICE_MODE" == "optional" ]]; then
    echo "warning: Podman API socket unavailable, continuing without it (see $XDG_RUNTIME_DIR/podman-service.log, or set E2E_PODMAN_SERVICE=1 to require it)" >&2
  else
    cat "$XDG_RUNTIME_DIR/podman-service.log" >&2 || true
    echo "error: Podman API socket did not start" >&2
    exit 1
  fi
fi

if [[ "${E2E_PODMAN_PROBE:-0}" == "1" ]]; then
  /opt/quality-bundle/bin/podman-doctor
fi

exec "$@"
