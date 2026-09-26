#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/home/e2e}"
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


# Expose Podman's Docker-compatible API only inside the runner container.
# Testcontainers uses this socket; no host Docker socket is mounted.
export DOCKER_HOST="${DOCKER_HOST:-unix://$XDG_RUNTIME_DIR/podman/podman.sock}"
mkdir -p "$XDG_RUNTIME_DIR/podman"
podman system service --time=0 "$DOCKER_HOST" \
  >"$XDG_RUNTIME_DIR/podman-service.log" 2>&1 &
PODMAN_SERVICE_PID=$!

for _ in $(seq 1 50); do
  [[ -S "$XDG_RUNTIME_DIR/podman/podman.sock" ]] && break
  sleep 0.1
done

if [[ ! -S "$XDG_RUNTIME_DIR/podman/podman.sock" ]]; then
  cat "$XDG_RUNTIME_DIR/podman-service.log" >&2 || true
  echo "error: Podman API socket did not start" >&2
  exit 1
fi

export TESTCONTAINERS_RYUK_DISABLED="${TESTCONTAINERS_RYUK_DISABLED:-true}"

if [[ "${E2E_PODMAN_PROBE:-0}" == "1" ]]; then
  /opt/quality-bundle/bin/podman-doctor
fi

exec "$@"
