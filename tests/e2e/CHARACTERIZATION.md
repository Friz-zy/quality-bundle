# Characterization registry

Behaviors pinned by the e2e suite (plan §8): intentional behaviors and actual-behavior pins.
A characterization test documents current behavior on purpose; flipping one requires an
explicit product decision, not a fix.

| Test id | Behavior pinned | Rationale | Flip condition |
|---|---|---|---|
| E2E-001 | `quality doctor` always exits 0, even when tools are missing | doctor is a report for humans/agents, not a gate | none required / N/A |
| E2E-010 | `quality plan` creates the artifacts dir without executing anything | plan is a dry-run but pre-creates the artifact path so wrappers can rely on it | none required / N/A |
| E2E-007 | `quality list` with empty discovery exits 0 and stdout is exactly one newline | `print("\n".join([]))` emits one blank line; pinned as-is rather than special-casing empty output | product decision to print nothing (or a message) on empty discovery |
| E2E-052 | `bin/zap` without `E2E_BASE_URL` exits 1 before creating the artifacts dir | the base-url guard fires before mkdir, so the error path leaves no directory behind | product decision to mkdir before the guard (plan §11 handoff table) |
| E2E-083 | `compatibility_artifacts` fixture always equals `artifacts_from_env(config versions)` | session-cached `e2e_config` makes per-test env overrides unreachable inside the fixture, so the fixture's consistency with the config-derived mapping is the contract; the env mapping itself is covered by E2E-082 | the fixture stops being session-cached or changes its mapping source; re-pin against the new contract |
| E2E-084 | `run_upgrade_command` builds `echo {old}->{new}`, whose `>` is a shell redirection: a file named `2.0` containing `1.4.0-` is created and stdout is empty | pins actual behavior including the redirection side effect, so any later quoting fix is a deliberate decision, not an accident | the argument is quoted/escaped so stdout carries `old->new` and no stray file is created |
