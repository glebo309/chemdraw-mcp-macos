# Development status

Current experimental release: **0.10.0rc16**.

Graphical and terminal setup use the same native bridge. The DMG includes its runtime and terminal commands; the Git route installs locked dependencies through `install.sh`. Both setup routes retain diagnostic reports.

Supported molecule tables use native measured bounds, shared caption baselines and physical pages in one document. Physical-scale exports preserve bond size. The full MCP profile additionally exposes explicit reaction, symbol and electron-arrow workflows. These tools do not infer mechanisms.

Shared drawing defaults to a lightweight native-derived white preview, with full
exports and canvas-only delivery available explicitly. Validated name lookups
can reuse process-local results, and stage timings expose native work separately
from model time. Fresh regular six-membered rings are axis-aligned without
changing the orientation of live references. [Measured performance](DRAWING_PERFORMANCE.md).

## Validation

The rc16 portable suite passed 1,168 tests with 93 optional skips. Seven serial
native tests passed, including delivery modes, unchanged originals, mixed
chemistry, shared alignment, pagination and physical exports. Native evidence is
limited to ChemDraw 23.0.1.11 on the development Mac. All 14 packaged checks
passed, including a live read and native drawing from the frozen candidate.
Earlier focused results are
listed separately in [release history](../PROJECT_PROGRESS.md).

## Open work

- Independent-Mac installation and native acceptance.
- Developer ID signing and notarization.
- Transactional graphical updates and rollback.
- Broader reaction/table speed benchmarks and additional molecular orientation conventions.
- Connected mechanism layouts and a sourced biocatalysis reference library.
- Remaining crowded-charge cases and broader native-object coverage.

See the [roadmap](ROADMAP.md) and [compatibility](COMPATIBILITY.md). Experimental builds are distributed through [GitHub Releases](https://github.com/glebo309/chemdraw-mcp-macos/releases), not a package index. Original project code is AGPL-3.0-only.
