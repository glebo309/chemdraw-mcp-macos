# Private development snapshot

Updated 2026-09-15. This snapshot preserves work in progress, not a release candidate. Package metadata remains 0.9.0; see PROJECT_PROGRESS.md for the earlier version's native validation evidence.

## Current checks

- Full portable command: `.venv/bin/pytest -q`.
- Result: 683 passed, 32 skipped, 11 failed in 6.05 seconds.
- All 11 failures are in `tests/test_native_lock.py`. These are new red-phase tests for coordination between independent CLI/MCP clients. The implementation is not present yet; current locks serialize only within each bridge instance.
- The seven focused tests in `tests/test_draw_charges.py` pass. The new `charge_style` option is experimental, not native-accepted.
- The first native four-molecule circled-charge demo stopped with `Unsupported or partially parsed chemistry; refusing to proceed`, after a nitrogen valence sanitization diagnostic. The precise cause remains under investigation. No successful charge-style production claim follows from portable tests.
- No native operation was automatically retried after this failure. Diagnostic artifacts remain local and are not repository assets.

## Next work

1. Diagnose the charged-molecule native roundtrip without weakening chemistry or stereochemistry validation.
2. Complete and verify cross-process coordination, retaining bounded waits and uncertain-write handling.
3. Verify both CLI and MCP paths with native artifacts and visual inspection before promoting either addition.
4. Continue molecule-first usability and consistent styling. Reactions combine explicit molecules; charts and general figure composition are not the current priority.
5. Investigate explicit coordination bonds and spatial depictions for metal complexes. General metal-complex construction and 3D geometry are not implemented or certified.

The private repository includes source, tests, documentation and synthetic examples. It excludes local-validation bundles, virtual environments, built distributions, proprietary templates, application binaries and reference PDFs. No public release or original-code licence grant is implied.
