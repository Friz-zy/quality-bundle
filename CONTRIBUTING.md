# Contributing

Keep the framework generic and product-agnostic.
Do not add target-application selectors, credentials, schemas, endpoints or business assertions here.
New optional frameworks should be isolated behind an optional dependency profile and marker.
Preserve backward compatibility for fixtures and `quality.toml` where practical.
Run the toolkit self-tests before tagging a release.
