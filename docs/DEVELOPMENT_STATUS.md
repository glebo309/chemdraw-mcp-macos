# Development status

Current experimental release: **0.10.0rc15**.

Graphical and terminal setup use the same native bridge. The DMG includes its runtime and terminal commands; the Git route installs locked dependencies through `install.sh`. Both setup routes retain diagnostic reports.

Supported molecule tables use native measured bounds, shared caption baselines and physical pages in one document. Physical-scale exports preserve bond size. The full MCP profile additionally exposes explicit reaction, symbol and electron-arrow workflows. These tools do not infer mechanisms.

## Validation

The rc15 portable suite passed 1,141 tests with 91 optional skips. Packaged acceptance passed 11 tests with one live-read skip. Native evidence is limited to ChemDraw 23.0.1.11 on the development Mac. Earlier focused results are listed separately in [release history](../PROJECT_PROGRESS.md).

## Open work

- Independent-Mac installation and native acceptance.
- Developer ID signing and notarization.
- Transactional graphical updates and rollback.
- Measured generation-speed improvements and better default molecular orientation.
- Connected mechanism layouts and a sourced biocatalysis reference library.
- Remaining crowded-charge cases and broader native-object coverage.

See the [roadmap](ROADMAP.md) and [compatibility](COMPATIBILITY.md). Experimental builds are distributed through [GitHub Releases](https://github.com/glebo309/chemdraw-mcp-macos/releases), not a package index. Original project code is AGPL-3.0-only.
