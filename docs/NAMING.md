# Naming conventions

The repository/project is `quality-bundle`.

Public orchestration interface:
- CLI: `quality`
- configuration: `quality.toml`
- framework environment: `QUALITY_*`
- reports: `artifacts/quality/`
- conventional submodule path: `tools/quality/`

Product/E2E environment variables intentionally keep the `E2E_*` prefix:
- `E2E_BASE_URL`
- `E2E_CLI`
- `E2E_IMAGE`
- `E2E_PORT`
- `E2E_HEALTH_PATH`
- `E2E_OPENAPI`
- `E2E_APP_ENV_*`
- protocol/runtime-specific E2E variables

Product-owned functional tests intentionally remain under `tests/e2e/`.
The name describes the test layer, while `quality-bundle` describes the shared toolkit.
