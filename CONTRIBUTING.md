# Contributing

Contributions are welcome. This is an open-source experimental project under [AGPL-3.0-only](LICENSE), not yet a stable release. These instructions do not authorize publishing private files or proprietary ChemDraw assets.

Useful first contributions include another-Mac compatibility reports, minimal reproducible drawing bugs, redistributable native fixtures and focused CLI/MCP improvements. Open an issue to discuss larger changes before building them. You do not need to be a programmer to help check chemical correctness or visual quality.

Unless explicitly agreed otherwise, contributions of original code are submitted under AGPL-3.0-only. You retain your copyright; no copyright assignment is requested. Only submit work you have the right to contribute, and retain applicable upstream notices when adapting existing code.

## Build a bounded, visible result

Read [usage](docs/USAGE.md), [compatibility](docs/COMPATIBILITY.md) and [roadmap](docs/ROADMAP.md). A feature needs a usable CLI/MCP entry point, tests, and an inspectable artifact for visual output. Unreachable internal helpers do not complete a user feature.

Keep responsibilities separated:

- `core.py`, `native.applescript`: bounded native operations and working-copy safety.
- `polish.py`, `geometry.py`: measured, conservative transformations.
- `workflow.py`: native save-cycle checks, artifacts and audit.
- `cli.py`, `server.py`: interfaces to the same implementation.
- `diagnostics.py`: read-only capability checks.

Do not add raw script/shell/menu execution or unscoped close operations to bypass missing native coverage. Do not describe mouse simulation as native scripting.

## Tests first

For a feature or bug fix, write a focused failing test, run it, implement the change, then rerun the relevant suite. Inspect a working native export before inventing CDXML properties.

```sh
uv sync --locked --extra chemistry
uv run --extra chemistry pytest
```

Native tests are skipped by default. Changes to native behavior require a licensed, activated application with no modal dialog or competing automation:

```sh
CHEMDRAW_LIVE_TEST=1 uv run --extra chemistry pytest tests/test_live.py tests/test_scope_live.py tests/test_batch_live.py tests/test_annotations_live.py tests/test_draw_live.py tests/test_batch_annotations_live.py -vs
```

Live tests create scratch documents and must preserve unrelated open documents. Never use someone else's unsaved drawing as a disposable fixture. A scripting dictionary declaration is not proof an operation works.

Inspect native visual output after any layout change. Record which checks were automated and which were visually reviewed; never equate `visual_review: required` with publication approval.

Regression priorities:

- Source unchanged; existing outputs refused; unrelated documents cannot be managed-closed.
- Native ID renumbering and ambiguous matching handled safely.
- Unsupported objects and partial chemistry parsing rejected.
- Supported stereo, formal charge, isotope and explicit-H preservation.
- Shared bond scale independent of whole-molecule dimensions.
- Explicit annotation ownership; no guessed label movement.
- Width overflow reported rather than silently shrinking molecules.
- Recoverable timeout/failure results without repeating uncertain writes.

A graph match proves supported input preservation, not independent correctness of a name, image interpretation or reaction. Keep that distinction in tests and audit text.

## Reuse and credit

Read [third-party notices](THIRD_PARTY_NOTICES.md) and [upstream research](docs/UPSTREAM_RESEARCH.md). Record repository, immutable commit, copied source/symbols, local destination and license in `upstream-sources.json`. Retain full applicable copyright/license text and mark adaptations accurately.

Do not call copied code mere inspiration; do not claim an entire project is copied when only an idea was used. Preserve original authorship through forks. Added code and dependencies must be compatible with the project's AGPL-3.0-only distribution and retain their own applicable notices.

Use redistributable synthetic fixtures with expected identities. Do not commit confidential chemistry, licensed application binaries, proprietary templates/fonts or paper artwork without appropriate rights.

## Bug reports

Useful information: command/MCP call, application/Python versions, diagnostic output, expected result, actual error/audit status, and a minimal nonconfidential CDXML fixture. Native before/after images help with layout bugs. Redact paths and unpublished chemistry before sharing.

Do not require confidential uploads as the first troubleshooting step. Reproduce on a minimal fixture, inspect our output, and distinguish a verified environment issue from our own bug.
