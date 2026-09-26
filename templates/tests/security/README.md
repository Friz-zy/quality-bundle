# Security template

The default security backend is OWASP ZAP baseline scanning.
Keep authentication contexts, exclusions, accepted-risk policy, and any active-scan
configuration in the target repository.

Do not enable destructive active scanning against production by default.
