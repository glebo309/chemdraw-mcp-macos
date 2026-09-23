# Release history and validation

Experimental macOS builds are available on [GitHub Releases](https://github.com/glebo309/chemdraw-mcp-macos/releases). Native results below are from ChemDraw 23.0.1.11 on the development Mac. Skipped tests are not passes, and local results do not establish compatibility with other machines.

## 0.10.0rc15: setup diagnostics

- Graphical setup saves plain-text reports, confirms the destination and offers Show in Finder. Failed saves offer a clipboard fallback; Copy diagnostics is available directly.
- Terminal setup saves failure reports under `~/Library/Logs/ChemDraw MCP/` with owner-only permissions. If saving fails, it prints a copyable report.
- Reports retain setup stages and classified errors without drawings, credentials, personal paths or raw exception text. Nothing is uploaded.
- Only native error -1743 is classified as Automation denial. An add-in timeout is not proof of a permission problem.

Validation: 1,141 portable tests passed, 91 optional tests skipped. Packaged acceptance: 11 passed, one live document-read test skipped. The frozen terminal executable was tested with an isolated home, including saved location, 0600 permissions and path exclusion. The graphical error preview was visually inspected. Signature, archive CRC and DMG verification passed.

This release does not change molecular orientation or generation speed. A reported second-Mac disconnection remains undiagnosed. Independent-Mac acceptance and interactive save-dialog testing on that machine remain open.

## 0.10.0rc13: bundled terminal access

- Graphical setup installs terminal commands against the same bundled runtime, with a backed-up, idempotent zsh PATH entry.
- Reaction preservation checks read the active untitled document without assigning it a filename.
- Full-profile guidance exposes existing electron-arrow, symbol and routing workflows; it does not infer complete mechanisms.

Validation: 1,130 portable tests passed, 91 skipped. Four focused native tests passed: a reaction with an untitled original and full/left/right arrowheads. All 12 packaged checks passed, including a live read. An older custom-style test assumed background routing; its shared request was rejected before writing and is not counted as a passing native test.

## 0.10.0rc12: graphical and Git installation

- `install.sh` installs locked dependencies and starts animated terminal setup.
- The Apple Silicon DMG includes Python, dependencies and graphical setup.
- Setup prints commands appropriate to a checkout or installed runtime.
- Guides cover architecture, customization, physical-scale exports and updates.

Validation: 1,123 portable tests passed, 90 skipped. All 11 packaged checks passed, including a native read and ordinary ZIP extraction.

## Earlier development milestones

| Milestone | Behavior | Recorded validation |
| --- | --- | --- |
| rc10 | Native-measured tables across physical pages; physical-scale SVG, PNG and PDF exports | 1,098 portable passes, 89 skips; paged-table/export test and five add-in tests passed |
| rc8 | Shared runtime, selectable local clients and neutral Mac installer | 1,077 portable passes, 88 skips; 10 packaged passes, one live-read skip |
| rc5 | Materialized runtime libraries for ZIP extraction; compact setup | 1,059 portable passes, 85 skips; seven packaged checks passed |
| rc3 | Shared-document reads/appends and scaffold/caption regressions | 1,043 portable passes, 79 skips; six native shared-API/first-run tests passed |
| 0.9.2 | One-command first drawing through CLI and MCP | 733 portable passes, 35 skips; five focused native tests passed |
| 0.9.1 | Cross-process coordination and charge-owner checks | 713 portable passes, 34 skips; 34 serial native tests passed |
| 0.7 | Identifiers, explicit-SMILES drawing and scaffold alignment | 298 portable passes, 17 skips; 17 native tests passed |
| 0.5 | Sequential batch export with source-preservation checks | 123 portable passes, 10 skips; 10 native tests passed |
| 0.4 | Measured scope grids and caption ownership | 104 portable passes, nine skips; nine native tests passed |

These are separate historical runs, not combined acceptance for the current version. The rc10 layout fixture retained a reference and added 17 structures across four A4 pages in one document. Native chemistry, geometry, centring and caption-baseline checks passed; PDF pages and a PNG table page were visually inspected. This verifies the supplied drawing fixture, not compound names or literature claims.

## Current limits

- Apple Silicon and ChemDraw 23.0.1.11 are the locally tested combination.
- The app is ad-hoc signed, not Developer ID signed or notarized.
- Independent-Mac installation and native acceptance remain incomplete.
- One process owns the add-in connection at a time.
- Automatic graphical updates, complete mechanism inference and general collision-free layout are not implemented.
- Automated preservation checks and human visual review remain separate requirements.

See [compatibility](docs/COMPATIBILITY.md), [known issues](docs/KNOWN_ISSUES.md), [roadmap](docs/ROADMAP.md) and the [release checklist](docs/RELEASE_CHECKLIST.md).
