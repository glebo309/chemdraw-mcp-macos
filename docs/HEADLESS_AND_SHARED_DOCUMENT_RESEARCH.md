# Headless rendering and one shared document

Update, 2026-09-16: bounded shared molecule insertion is now implemented and
native-tested. Approved keyboard movement with position readback places native
CDX in the same document, including untitled documents. Auto selects this route
when one document is visible. Two native tests passed, including repeated actual
MCP calls and Undo preservation. A further actual CLI default-auto call appended
to the already populated untitled document. See USAGE.md for its deliberately
limited object support and focus/Accessibility requirements. Historical failed
probes below remain evidence, not currently enabled alternatives.

Capability investigation, 2026-09-15. This is evidence and a proposed direction,
not an implemented headless backend or general collaborative editor.

## Installed desktop application

Inspected ChemDraw 23.0.1's installed scripting dictionary, application bundle
and current native bridge. No documented display-free renderer or command-line
render entry point was found in that inspection or the vendor sources searched.
This is not proof that no unpublished SDK or other product can provide one.
The current bridge sends Apple events to the desktop application and requires
that application process. Hiding document windows does not remove that dependency.

### Cold-start experiment

The application was running with zero documents before the experiment. Quit was
guarded by a second native check that no document existed. An initial immediate
launch raced asynchronous termination and returned -600. The subsequent document
listing started the app and created an empty untitled ACS document.

The test-created startup document was later confirmed unmodified with zero objects
and closed by exact ID. No pre-existing user document was closed. After a second
guarded quit, a bounded running-process poll confirmed termination before sending
the explicit AppleScript `launch` event. The subsequent native query returned:

```text
frontmost = false
document count = 0
window count = 0
```

This supports a launch-only startup path that avoids the default new document in
this clean-session case. It does not establish behavior with restored documents,
licensing dialogs or without a logged-in desktop. It does not prove that imports
never flash: the existing implementation opens a document then hides its window.
No production startup code was changed in this investigation.

## Separate vendor server product

Revvity's own ChemDraw JS examples document ChemDraw Web Service as a server-side
component supplied as a Docker image with the JS subscription. Its advertised
tasks include generating SVG from chemistry data, format conversion and reactions.
The repository warns that the CDWS API is private and subject to change.

- https://github.com/Revvity/ChemDraw-JS-Public-Examples
- https://support.revvitysignals.com/hc/en-us/articles/36661289382164-ChemDraw-JS-Webpack-React-Github-demo-implementation-ChemDraw-JS-version-23

This is a documented candidate for actual server-side rendering, not a capability
demonstrated with the installed desktop license. No service image, subscription,
remote endpoint or alternate renderer was installed or used.

## One shared document: native probe

The disposable script is local-validation/probe_headless_shared.py. Native CDXML
snapshots and a hidden-window SVG export are in local-validation/headless-shared-probe.
All molecular probes addressed a single owned scratch document by its exact ID.

| Operation | Observed result |
| --- | --- |
| Hidden native CDXML/CDX/SVG export | Worked |
| Document-addressed cleanup | Worked |
| Atom properties getter | Native -10000 |
| Make caption with text | Native -10000 |
| Make atom | Native -10000 |
| Make molecule with SMILES text | Native -10000 |
| Make molecule with exported binary ST2D data | Native -10000 |
| Same binary input at end of document molecules | Native -10000 |
| Selection contents getter | Native -10000 |

Counts after each attempted creation remained unchanged. A select-all probe was
refused by the explicit front-document guard because the hidden scratch document
was not frontmost. Its empty-selection SMILES response proves no selected-graph
capability. No clipboard or GUI fallback was attempted.

The existing shared-document integration tests were independently rerun:
2 passed in 11.58 seconds, local-validation/shared-document-recheck.xml. These
verify same-ID cleanup over MCP, detection of an edit from a separate native
client, stale-token rejection, hidden export and ownership isolation. The separate
client is a stand-in for manual edits, not a live human collaboration experiment.
Reads remain on request, not continuous synchronization. The final inventory is
checked against its baseline by both tests.

## Decision boundary

Do not advertise the installed Mac backend as truly headless. Investigate the
explicit launch path for less intrusive desktop startup, with regression tests
before changing production behavior.

For interactive use, prefer a persistent document/session contract rather than
the batch renderer's document lifecycle. Existing read/cleanup/alignment tools
cover part of it; arbitrary insertion and atom editing are still missing. A
controlled native clipboard/paste experiment is a possible next route, but needs
explicit approval under the project's no-clipboard/no-GUI-fallback boundary.
It must preserve/restore clipboard data, verify the target document and chemistry,
respect concurrent edits, and establish undo/recovery before being called safe.

## 2026-09-16: authorized clipboard experiment

Native CDX data using the observed com.revvity.chemdraw.cdx-clipboard pasteboard
type inserted editable chemistry into the same existing document without opening
a helper document. The native readback added methanol to a chlorobenzoic-acid
fixture and retained both expected graphs. Document ID and file binding stayed
the same. With ChemDraw explicitly active, native Undo returned the molecule count
from two to one. The earlier non-active application case did not reliably undo.
Thus front-document identity alone is not enough for this route; application focus
also matters and must be checked, including immediately before dispatch.

All original clipboard items/types/data were held in memory and restored with
byte equality checks in the completed probes. Concurrent clipboard changes are
detected by changeCount and not overwritten. This is prototype evidence, not a
production recovery guarantee under crashes, timeouts or clipboard managers.

Copy As CDXML Text can read the selected drawing without saving a file or opening
a window. The experiment selected all to obtain the whole drawing. Preserving a
human's previous arbitrary selection has not been solved, so this is not yet a
drop-in read-only replacement for live-read.

The final MOL trial completed its undo and clipboard restoration. Readback confirmed
the original graph and all atom positions were restored, with page dimensions
unchanged at 523 by 770 points and one page wide/tall. Only the owned test document
remains open, containing the original single molecule. No further paste was sent.

Probe artifacts are in local-validation/clipboard-probe-cdx. The generic
mol-pasted.cdxml was overwritten by the later failed MOL trial and must not be
used as evidence of successful CDX chemistry. The successful CDX graph comparison
was observed before that overwrite. This capability spike
does not yet implement collision-aware append placement, arbitrary in-place atom
edits, selection restoration, untitled-document support or continuous collaboration.

## 2026-09-16 implementation acceptance blocker

The experimental shared route now has MCP/CLI argument plumbing and portable
placement/preservation tests, but remains gated before native execution. A native
paste preserves the tested graph, while the requested selection-bounds movement
fails with -10000. Changing the CDX document framing rectangle did not change the
observed page-centered paste placement. This is not a supported positioning method.

The acceptance test in tests/test_shared_native.py explicitly checks position and
Undo and remains failing; portable tests do not substitute for that test. Approval
was requested for narrowly scoped keyboard placement, and no keyboard events have
been sent. Manual page 106 describes one-point arrow-key object movement.

Implementation detail: uninitialized Objective-C error references caused one
osascript crash. shared.js now catches errors inside AppleScript and passes a null
error pointer, avoiding the unreliable reference dereference. Clipboard restoration
still cannot be guaranteed after process termination and must not be advertised so.
