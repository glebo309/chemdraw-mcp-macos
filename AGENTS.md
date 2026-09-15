# ChemDraw MCP for macOS

Read README.md, docs/USAGE.md, docs/COMPATIBILITY.md and PROJECT_PROGRESS.md before changing this project.

## Contracts

- Desktop ChemDraw renders native outputs. RDKit validates chemistry and supplies explicit-input MOL coordinate seeds; it is not a fallback renderer hidden behind a native label.
- Both CLI and MCP call the same workflow implementation. A feature is incomplete until the user can invoke it and inspect its actual native output.
- Write a failing regression test before implementation. Run the portable suite and opt-in native tests after relevant changes.
- Use explicit document IDs, working copies and new output directories. Do not edit or close pre-existing documents during tests.
- Do not retry uncertain writes. An import whose result is delayed may be reconciled by read-only document listing, never by opening a second time.
- Positive uniform scaling and translation preserve existing orientation. Do not strip explicit H, reflect coordinates, infer unspecified stereo, or replace chemical attributes just to obtain a successful parse.
- Unsupported document objects and chemistry must fail closed. A parser returning a molecule does not establish support for every source property.
- Verify native saved chemistry and layout separately. Keep human visual review distinct from machine checks. Never set a check true when it was unavailable or not run.
- Treat captions and arrow conditions as owned objects. Reject ambiguous ownership rather than guessing.
- Keep changes bounded. No GUI fallback, raw AppleScript execution tool, external provider, publication or licence change without corresponding user scope.
- Update upstream-sources.json and THIRD_PARTY_NOTICES.md for borrowed source. Retain the full applicable notices in distributed artifacts.

## Verification

Install with `uv sync --extra chemistry` and run `.venv/bin/pytest -q`.
Native tests require a licensed, running supported ChemDraw: `CHEMDRAW_LIVE_TEST=1 .venv/bin/pytest tests/test_live.py tests/test_scope_live.py tests/test_batch_live.py tests/test_annotations_live.py tests/test_draw_live.py tests/test_batch_annotations_live.py tests/test_v08_live.py tests/test_symbols_live.py tests/test_scope_decoration_live.py -v -s`.
Do not run separate native editing clients concurrently. Generated local reports remain in ignored local-validation/ directories.

Private GitHub hosting was approved on 2026-09-15 for glebo309/chemdraw-mcp-macos. Keep the repository private. This does not authorize public distribution, package publication, contacting maintainers, adding collaborators or granting a project licence. Subsequent pushes require corresponding user scope.
