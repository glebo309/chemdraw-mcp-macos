# Development status

Current experimental release: **0.10.0rc22**.

rc22 fixes native active-document IDs being converted to scientific notation.
Large positive and negative IDs now remain exact integers. Read diagnostics
distinguish invalid IDs, changed documents and closed documents before dispatch;
these failures no longer suggest an Automation permission problem.

rc21 replaces the Start Here guide's drawn controls with a cropped macOS
screenshot and three numbered highlights. The screenshot ships beside the HTML
for offline use. Native drawing and connection code are unchanged from rc20.

rc20 adds automatic private diagnostic capture with read stages, exception types,
native/API error codes, document counts and elapsed time. The add-in handles
missing documents explicitly, does not require selection support for a full
document read, and uses a compact status panel without premature success text.
Repeated upgrade regressions check stable launchers, preserved assistant settings
and in-place add-in refresh with unchanged credentials. The illustrated DMG guide
now includes update instructions. ChemDraw 26 acceptance remains unverified.

Graphical and terminal setup use the same native bridge. The DMG includes its runtime and terminal commands; the Git route installs locked dependencies through `install.sh`. Both setup routes retain diagnostic reports.

Supported molecule tables use native measured bounds, shared caption baselines and physical pages in one document. Physical-scale exports preserve bond size. The full MCP profile additionally exposes explicit reaction, symbol and electron-arrow workflows. These tools do not infer mechanisms.

Shared drawing defaults to a lightweight native-derived white preview, with full
exports and canvas-only delivery available explicitly. Validated name lookups
can reuse process-local results, and stage timings expose native work separately
from model time. Fresh regular six-membered rings are axis-aligned without
changing the orientation of live references. [Measured performance](DRAWING_PERFORMANCE.md).

## Validation

The rc22 portable suite passed 1,219 tests with 99 optional skips, including
macOS execution of the production serializer without launching ChemDraw.
A source-runtime read-only check passed on ChemDraw 23.0.1.11, macOS 15.6,
Apple Silicon, with unchanged document metadata. ChemDraw 26 acceptance remains
unverified; this fixes a reproduced bridge bug, not every possible read failure.

The rc20 portable suite passed 1,203 tests with 99 optional skips. Fourteen
packaged checks passed, including an isolated rc19-to-rc20 executable upgrade;
three optional native checks were skipped in that run. A separate packaged
read-only setup check passed against ChemDraw 23.0.1.11. The diagnostic-screen
preview was visually inspected. No ChemDraw 26 acceptance is claimed.

The rc18 portable suite passed 1,187 tests with 98 optional skips. Five serial
native tests passed: the full glycoside reaction with circled charges, three
physical-paper round-trips and the separate crowded nitrobenzene regression.
Native evidence is limited to ChemDraw 23.0.1.11 on the development Mac.
All 13 executed packaging checks passed, including the circled-charge reaction
through the frozen MCP and plain ZIP extraction. Two add-in-specific tests were
not run. White native previews were visually inspected.
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
