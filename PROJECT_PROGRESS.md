# Release history and validation

Experimental macOS builds are available on [GitHub Releases](https://github.com/glebo309/chemdraw-mcp-macos/releases). Native results below are from ChemDraw 23.0.1.11 on the development Mac. Skipped tests are not passes, and local results do not establish compatibility with other machines.

## Development: complete scope batches and recovery

Explicit plain-charge grouped drawings now measure the whole table in one
native document and deliver the grid, heading, frame and exports in one final
document. The planner uses real physical paper and retains bond scale. Native
object matching uses graph and geometry instead of document order, so native
renumbering or reordering cannot silently swap compound labels. Both the
advanced MCP operation and CLI draw manifest reach this path. The ordinary
background harness routes eligible grouped requests before the legacy untitled
document guard.

Preservation reads can select an explicit inactive untitled document under the
native lock and restore the original tab without activating the application.
The comparison excludes native page-handle churn but retains drawing content.
Named drawings with unsaved edits also use the API read, avoiding native save
side effects during preservation checks.
Shared additions preserve narrowly supported linked name-caption metadata
without using stale names as molecular identity. Unknown properties still fail
closed. Native uncertainty returns available artifacts, audit checks and the
last known retained document ID through MCP and CLI, without retrying a write.

The serial development-Mac component test rendered the 15-member framed table
in 6.735 seconds, including native layout/style/frame checks and all image
exports. It left one final document and retained the original document inventory.
The white preview was visually inspected; the 3900 by 5117 RGBA PNG has a
600-DPI physical scale and transparent margins on all sides. The full new
desktop-API preservation workflow remains pending exclusive native acceptance:
an installed runtime owned that connection during the component test. This
result does not certify the complete integration or a new packaged release.
`tests/test_scope_table_live.py` exercises the full workflow serially when both
native-test opt-ins are enabled.

The locked-environment suite passed 1,236 tests with 100 optional skips. The
macOS Swift checks used the existing local SDK module-map overlay. Regression
coverage includes complete batch routing, label ownership after native object
reordering, immutable linked caption metadata, guarded untitled preservation
reads, and retained-result reporting through the harness, advanced MCP and CLI.
The counts include portable/mock checks, not the skipped exclusive live run.

## 0.10.0rc22: exact native document IDs

Active-document IDs use Foundation JSON serialization rather than AppleScript
text coercion. Large positive and negative values previously became scientific
notation, parsed as floats and failed the bridge's strict integer validation.
The strict input guard remains in place; no rounding or permissive float-to-ID
conversion was added.

Read preflight reports invalid_document_id, document_changed or no_open_document
with the specific stage. Reports exclude the ID value, drawing and credentials.
Known read failures no longer recommend changing Automation permissions.

Validation: 1,219 portable tests passed with 99 optional skips. The regression
executes the production AppleScript serializer on macOS without ChemDraw,
including signed 32-bit limits and the no-document case. A source-runtime
read-only check passed against ChemDraw 23.0.1.11 on macOS 15.6, Apple Silicon,
with unchanged open-document metadata. ChemDraw 26 and independent-Mac acceptance
remain unverified. Installer and terminal use the same corrected bridge.

## 0.10.0rc21: screenshot-based opening guide

The offline Start Here guide uses a cropped macOS screenshot instead of drawn
controls. Three numbered pink outlines identify Privacy & Security, the blocked
app's Open Anyway button and the final confirmation. The screenshot is bundled
in Start Here assets beside the HTML, with no remote image dependency. Only the
relevant settings and confirmation region is distributed.

The packaging regression verifies the screenshot is present and byte-identical
in the staged disk image. The portable suite passed 1,204 tests with 99 optional
skips. The guide and all three highlights were rendered and visually inspected.
Native drawing and connection implementation are unchanged from rc20.

## 0.10.0rc20: diagnostic capture and upgrade regressions

Graphical setup automatically retains a private text report after each event,
including before native calls. A visible Show saved report action locates it;
Save and Copy remain available if automatic saving fails. Failed probes retain
their stage, exception type, bounded error code, document count and elapsed time
without drawings, credentials or raw native exception text.

Read probes handle a disappearing document before dispatch and a missing document
inside the add-in. API-version failures return a result instead of losing a claimed
job. Selection retrieval is optional for full-document reads. A read requests
document CDXML once, retains identity checks and never retries uncertain writes.
The add-in requests a 240 by 64 pixel window and reports document delivery rather
than claiming verified connectivity. Optional window APIs cannot break polling.

Portable validation: 1,203 passed, 99 optional skips. Packaged checks: 14 passed,
3 optional skips, including a real rc19-to-rc20 runtime upgrade in an isolated
home directory. A separate packaged read-only native setup test passed against
ChemDraw 23.0.1.11 on macOS 15.6. The actual diagnostic-screen preview was visually
inspected. Repeated upgrade tests preserve client configuration, terminal paths,
private connection credentials and suffixed add-in folders. Existing app versions
remain available; automatic update discovery and one-click rollback are not implemented.
These results do not establish ChemDraw 26 or independent-Mac acceptance.

## 0.10.0rc19: illustrated first-launch guide

The DMG includes an offline **Start Here.html** beside the application. Three
numbered illustrations identify Privacy & Security, the blocked-app Open Anyway
entry and the confirmation dialog. The guide separately explains ChemDraw
Automation permission and links to Apple's instructions. It does not run scripts,
fetch remote assets or change security settings. The app remains not notarized.

The packaging regression verifies that the guide is staged beside the app and
contains the offline instructions. The portable suite passed 1,188 tests with
98 optional skips; the rendered guide was visually inspected. Native drawing
and connection implementation are unchanged from rc18; this packaging update
does not claim new native or independent-Mac acceptance.

## 0.10.0rc18: circled reaction charges

Ordinary batched reactions display existing unit formal charges as native
circled symbols. Placement prefers the owning atom's measured label as well
as its coordinate. Native saving must retain charge ownership and a 2 pt
clearance from measured labels, conservative bond envelopes and other symbols.
One additional whole-document measurement includes the circles in row layout.

Validation: 1,187 portable tests passed, 98 optional tests skipped. The complete
glycoside reaction passed native validation with four circled charges, unchanged
graphs and pre-existing documents, and physical-scale exports. Its white native
preview was visually inspected. Four batch-reaction/paper native tests and the
separate nitrobenzene circled-charge regression passed serially. All 13 executed
packaging checks passed, including the full circled-charge reaction through the
frozen MCP and plain ZIP extraction. Two add-in-specific tests were not run.
Independent-Mac acceptance remains open.

## 0.10.0rc17: complete reaction batching

- Ordinary explicit reactions use local whole-document assembly, one native
  measuring copy and one final export copy. No per-participant native imports
  or cleanup calls; no mouse-control fallback or content-shortening retries.
- Native measured layout selects supported A4/A3 paper at unchanged bond scale.
  Saved physical paper records are checked independently of drawing bounds.
- Full glycoside hydrolysis retains water, both products, all labels and the
  complete conditions line. A bounded nitro orientation avoids charge crowding.
- Reaction exports include physical-scale SVG, 600-DPI transparent PNG and a
  white review preview. Input-resolution provenance and timings are retained.

Validation: 1,184 portable tests passed, 98 optional tests skipped. Four serial
native tests passed: complete glycoside hydrolysis and round-trips for A4 portrait,
A4 landscape and A3 landscape. All 13 executed packaging checks passed, including
the complete reaction through the frozen executable's actual MCP interface;
two add-in-specific checks were skipped because another client retained that
connection. The frozen reaction completed in 5.758 seconds with four participants
on A4 landscape. Its white native preview was visually inspected; the pre-existing
document inventory and content remained unchanged. This candidate's native runs
used a named original, not an untitled original. Separate-Mac acceptance remains
open. [Workflow, physical paper and limitations](docs/REACTION_BATCH.md).

## 0.10.0rc16: faster shared drawing and upright ring orientation

- Shared drawing defaults to native SVG plus a white 1200-pixel review preview;
  full transparent exports and explicit canvas-only delivery remain available.
- Repeated validated name/CAS results use a bounded five-minute in-memory cache,
  with fresh-lookup control and unchanged permission/ambiguity requirements.
- Native reads combine post-read identity and metadata into one invocation;
  stage timings distinguish server work from model/client overhead.
- Fresh regular six-membered rings use a measured rigid rotation to eliminate
  arbitrary tilt. Live references retain their supplied orientation. The caffeine
  native preview was inspected on white with an upright fused edge and carbonyl.

Validation: 1,168 portable tests passed, 93 optional tests skipped. Seven serial
native tests passed, covering all delivery modes, live-target/stale-token checks,
shared analogue alignment, mixed chemistry, paged tables and physical exports.
Pre-existing documents remained unchanged in the timing comparison. Caffeine
warm medians were 2.952 seconds for the previous full-export/read sequence,
2.067 seconds for preview and 1.401 seconds for canvas-only (three runs each).
[Environment, scope and reproduction](docs/DRAWING_PERFORMANCE.md).

All 14 packaged checks passed, including isolated installation/client startup,
plain ZIP extraction, live document read and a native caffeine drawing from the
frozen candidate with the preview and upright-ring policy. Package execution was
bound to the candidate rather than delegated to an older selected installation.

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
