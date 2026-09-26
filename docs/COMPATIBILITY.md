# Compatibility testing

Compatibility tests must operate on released/public artifacts, not imported implementation code.

Configure version identifiers:

```toml
[compatibility]
versions = ["1.4.0", "1.5.0", "current"]
```

Map each version to a CLI or image in CI:

```bash
export E2E_COMPAT_1_4_0_CLI=/artifacts/app-1.4.0
export E2E_COMPAT_1_5_0_IMAGE=registry/app:1.5.0
export E2E_COMPAT_CURRENT_CLI=./bin/app
```

Useful project-owned scenarios:
- old CLI -> current API
- current CLI -> previous supported API
- old persisted state -> current release
- upgrade N-1 -> N
- downgrade only when explicitly supported
- schema/data migration
- rolling mixed-version behavior when the product supports it

The toolkit intentionally does not decide which version combinations are supported.
That policy belongs to the target product.
