# Rootless nested Podman runner

The default `restricted` mode is designed for the most constrained nested-container case:

- no host Docker/Podman socket
- no `--privileged`
- no `/dev/fuse`
- no `/dev/net/tun`
- VFS storage
- `ignore_chown_errors="true"`
- rootless networking through `pasta`

Run a capability probe before relying on a new CI runtime:

```bash
podman run --rm quality-bundle /opt/quality-bundle/bin/podman-doctor
```

## Modes

### restricted

Uses VFS and single-UID-compatible ownership squashing. This maximizes portability but is slower,
uses more disk, and can break images whose behavior depends on distinct Unix file ownership.

### standard

Still uses VFS and remains rootless, but does not squash ownership. It expects working subordinate
UID/GID mappings and the outer runtime/kernel to permit the necessary user namespaces.

## Important limitation

Nested rootless Podman cannot manufacture kernel capabilities that the outer container runtime has
removed. The image therefore includes a real runtime probe. A CI executor that blocks creation of
the required user namespaces may still reject nested Podman even though no privileged mode, FUSE,
TUN, or host socket is requested.

Use an external deployment (`E2E_BASE_URL`) as the fallback when the executor forbids nested user
namespaces.
