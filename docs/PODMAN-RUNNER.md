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
/home/e2e/.local/share/containers
```

to cache pulled images between runs.

## Fallback

When the executor forbids nested user namespaces, run the SUT outside the harness and provide
`E2E_BASE_URL`. Functional tests remain black-box and do not otherwise change.
