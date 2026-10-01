# Rootless Podman runner

The primary runner image is Podman-first and does not require a host Docker socket.

## Default restricted mode

```text
outer CI/container runtime
  -> quality-bundle container (UID 1000)
     -> rootless Podman
        -> SUT
        -> databases
        -> brokers
        -> Toxiproxy
```

The restricted profile uses:
- `vfs`
- `ignore_chown_errors="true"`
- `cgroups="disabled"`
- `crun`
- `pasta`
- no `/dev/fuse`
- no `/dev/net/tun`
- no host container socket
- no requested privileged mode

VFS is deliberately chosen for compatibility, not performance.

## Why the probe is mandatory

Whether nested rootless Podman can create the required user namespaces is ultimately controlled
by the outer kernel/runtime/CI executor. Configuration inside this image cannot override a blocked
`clone`/`unshare`, seccomp restriction, or disabled user namespaces.

Always run:

```bash
/opt/quality-bundle/bin/podman-doctor
```

on a new executor.

## API socket lifecycle

`podman system service` is started only when the invoked command needs the
Docker-compatible API socket: `quality test`, `quality run`, and suite commands,
because their tests may use Testcontainers. If the socket cannot start there,
the container fails before executing them.

Diagnostics such as `quality doctor`, `quality list`, and `quality plan` skip
the service entirely, so they run on executors that forbid nested user
namespaces. Any other entrypoint (a debug shell, the `podman-doctor` probe)
attempts the service and continues with a warning if it cannot start.

Set `E2E_PODMAN_SERVICE=1` to require the socket for any entrypoint, or
`E2E_PODMAN_SERVICE=0` to never start it (for example for a `quality run` that
selects only non-container suites on a restricted executor). This does not
change the namespace limitation above; runtime suites on such executors still
need the `E2E_BASE_URL` fallback.

## Standard mode

Set:

```bash
E2E_PODMAN_MODE=standard
```

when subordinate UID/GID mappings work correctly. This preserves image ownership instead of
squashing all image users to one UID. VFS is still used, so FUSE remains unnecessary.

## Restricted single-UID trade-off

`ignore_chown_errors` lets Podman use images in environments where multiple subordinate IDs are
unavailable. All image file ownership is effectively squashed. Images that rely on distinct Unix
owners/groups can fail or behave differently. Use standard mode for those images.

## Persistent storage

Mount a named volume at:

```text
/home/podman/.local/share/containers
```

to cache pulled images between runs.

## CI smoke coverage

The Toolkit workflow (`.github/workflows/toolkit.yml`) builds the image once
and then runs two independent smoke jobs; neither substitutes for the other:

- `smoke-dood` — Testcontainers through a mounted host Docker socket with
  `E2E_PODMAN_SERVICE=0`, so the internal Podman service stays off
  (Docker-out-of-Docker; see `TESTCONTAINERS-PODMAN.md`).
- `smoke-nested-podman` — no Docker socket mounted, `E2E_PODMAN_SERVICE=1`
  fails closed if the internal API socket cannot start, and the smoke files
  (`smoke/test_nested_podman.py`) really create and remove containers through
  both in-container paths: Testcontainers over the internal socket and the
  `PodmanRuntime` CLI adapter.

`quality doctor` alone is not a substitute: it proves only that Podman starts,
not that containers can actually run.

## Executor requirements for nested rootless Podman

Nested rootless Podman needs the executor to allow creating user namespaces
(`clone(CLONE_NEWUSER)`) and needs seccomp not to block it. Under stock
Docker the default seccomp profile blocks it, so the nested CI job runs with
`--security-opt seccomp=unconfined --security-opt apparmor=unconfined` and no
privileged mode; the restricted profile keeps VFS, disabled cgroups, and pasta,
so `/dev/fuse` and `/dev/net/tun` are not required.

If a runner still forbids user namespaces (symptom: `EPERM` from
`clone`/`unshare` in the podman-doctor output), point the
`smoke-nested-podman` job at a capable self-hosted runner by changing its
`runs-on` label; the DooD job has no such requirement.

## Fallback

When the executor forbids nested user namespaces, run the SUT outside the harness and provide
`E2E_BASE_URL`. Functional tests remain black-box and do not otherwise change.
