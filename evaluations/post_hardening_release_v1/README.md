# Post-hardening release integrity v1

This layer identifies the current application without changing the Auditor Scenario Evaluation v1 or v1.1 freezes.

The original baseline validators remain deliberately strict. They validate the application snapshot that existed when each evaluation was frozen. Running them against the post-hardening application therefore reports source drift. They stop at the first mismatch (`app.py`), while the version-aware relationship check enumerates the full authorised five-file runtime drift.

`release_manifest_v1.json` separately binds the current application source, the current focused regression files, the unchanged 88-artifact preservation ledger, both original manifests, all three observation layers, and the original 50-question benchmark identity. It is a release manifest, not a rewrite of historical evidence.

`run_release_verification.py` discovers the complete test tree, executes the four unchanged historical snapshot tests in a named baseline category, and executes every other test as the current-version regression category. No test is deleted, skipped, weakened, or silently filtered. The runner accepts the historical category only when all four retain the exact known `Integrity mismatch: app.py` result and the complete drift is confined to the five authorised post-hardening runtime files.

All verification is offline. The runner clears live-provider credentials and blocks sockets and URL opening.
