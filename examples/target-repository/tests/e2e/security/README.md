# Security E2E

The shared toolkit can run OWASP ZAP baseline scanning against `E2E_BASE_URL`.

Project-specific authentication setup, contexts, exclusions and accepted-risk rules
must remain in the target repository. Never disable findings globally to make CI pass.
