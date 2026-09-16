# Project progress

## 2026-09-16: rc12 Git installer and public distribution candidate

Glenn approved updating GitHub and distributing the graphical and terminal routes.
The new executable install.sh installs the locked checkout environment, then
launches terminal setup automatically. It forwards explicit client selections and
stops if dependency installation fails. Setup now prints a first-run command that
works for its actual source or installed environment instead of assuming PATH.

README distinguishes the Git/uv route from the self-contained Apple Silicon DMG,
shows the native setup design, and links architecture, customization, exports and
update guides. The source package and Mac app are versioned 0.10.0rc12/build 12.
Portable suite: 1123 passed, 90 opt-in skips. The local DMG build passed ad-hoc
signature verification, bundled dependency self-check, ZIP CRC and DMG checksum.
Archive inventory excludes private connection files and local validation data.
The project remains experimental, not notarized or independently Mac-certified.
All 11 frozen-runtime and packaging acceptance tests passed, including extraction
without symlinks and a live native document read. The actual install.sh wrapper
was also exercised from dependency synchronization through terminal setup.

## 2026-09-16: detect the actual installed add-in folder

The fresh terminal test exposed a real installation bug: ChemDraw used our
randomized archive filename as its installed folder/menu identity, while the
bridge looked only for the unsuffixed folder. The enabled f9aa03bb entry was
therefore missed and setup misreported licence/Automation trouble.

Discovery now recognizes an old eight-hex suffix only when metadata, loopback
endpoint and private key match the canonical local connection. It handles imports
made while setup is already running and retains the original credential path.
Future terminal exports retain the stable archive basename inside a unique
Downloads subfolder. Unregistered prepared backends now report needs_setup rather
than falling through to a generic native-connection error.

Four failing regressions preceded implementation. The live doctor then reported
status ready, shared_drawing_ready true and read_verified true against Glenn's
existing enabled suffix-named add-in. The same blank document remained unmodified;
no drawing writes or reinstall were needed. Focused tests: 51 passed.

## 2026-09-16: terminal background compatibility correction

Glenn's actual Terminal screenshot exposed an unreadable light background that
the separate raster preview did not catch. Setup used a 24-bit RGB background
escape while its foregrounds used indexed colours. The background now uses
indexed dark grey 235, and each frame resets inherited text attributes before
painting. Pink/lavender/gold accents and continuous animation are unchanged.
A failing regression preceded the fix and covers both frame and screen entry.
The previous generated preview was not evidence of Apple Terminal compatibility.

## 2026-09-16: continuous terminal setup and reversible local reset

Replaced per-operation animation flashes with one themed alternate-screen setup
session. The screen starts before setup-session initialization, animates throughout
manual instructions and checks, and holds the successful completion until Return.
Actual braille ink bounds determine molecular centering. Smaller windows paginate
instructions. Input echo, colours, cursor and the prior screen are restored on exit
or interruption. Plain output remains available. Credential wording now distinguishes
the generated add-in archive from the installed bridge and shareable main download.

Regression tests were written and failed before implementation. The exact locked
uv setup command was exercised in a pseudo-terminal through the manual-input stage,
then interrupted without drawing. The native UI inspection service was unavailable;
the actual frame was rasterized separately and visually inspected instead.
Final portable regression run: 1115 passed, 90 opt-in tests skipped, using the
existing local Swift SDK overlay for native presentation compilation.

At Glenn's request, the installed shared helper, native add-in and credential,
helper preferences, and generated Downloads archives were moved to a private
recovery directory. The native development and shared graphical client entries
were removed with backups and semantic preservation checks on unrelated settings.
Only this project's native MCP server processes were stopped. The source checkout,
environment, ChemDraw application, drawings, and the unrelated legacy MCP remain.
ChemDraw was still running; save and quit it before the fresh installation test
to discard its in-memory add-in. No automatic close of user documents was attempted.

## 2026-09-16: rc11 terminal setup and sharing documentation

New `chemdraw-mac setup` reuses the graphical setup protocol from an interactive
terminal. It exports a uniquely named private add-in to Downloads, always shows
the import/enable instructions, and verifies a live document read without drawing.
Optional explicit client selections register the installed stdio executable only
after that read passes, with existing conflict checks and private config backups.
No client selection means no client-config writes. The molecular animation uses
pink/lavender/gold accents. First-run accepts an explicitly verified page expansion
without misreporting its expected page_unchanged=false as a failed drawing check.

A fresh isolated uv tool install succeeded from the source, outside the checkout
environment. Its real interactive setup reached Document read: PASS against the
existing local add-in. An installed-CLI pseudo-terminal acceptance test then drew
the two-molecule example in an owned blank document, captured the animation,
checked artifacts, closed only its test document and preserved the original
document inventory. This is not fresh-Mac Add-in Manager acceptance. No actual
assistant configuration was modified during these tests.

README now shows the actual native setup screen and separates graphical, terminal
and MCPB routes. New terminal, worked-example/customization and update guides are
linked beside the expanded MCP/harness architecture explanation. Automatic
graphical updates and cross-version rollback remain explicitly unimplemented.
Publication status and final package gates are recorded after completion below.

Final local gates: 1108 portable tests passed, 90 opt-in tests skipped. The new
installed-terminal native acceptance passed in 10.10 seconds. Frozen rc11 runtime
and packaging acceptance passed 10 tests with one live-read skip. The builder's
ad-hoc signature, dependency self-check, archive checks and DMG checksum passed.
Wheel and source archive include terminal setup and exclude environments,
private add-in packages, credentials and local validation bundles. The rc11 DMG
is on the Desktop. The current branch is main; confirmation to push the
accumulated tested changes there and publish a prerelease was requested.
No commit, push or release has been performed for rc11 yet.

## 2026-09-16: rc10 installer, same-document tables and physical-scale exports

Step 2 now always offers a visible add-in installer export, followed by the
Add from file instructions. Existing files no longer hide the import route.
The normal page fits the existing window without scrolling. Downloads contains
the disposable installation archive; the page explains that it may be removed
after successful setup. Native bundled SwiftUI preview was visually checked,
including the molecule animation resource and pink controls.

Native addCDXML was experimentally verified to expand the current document's
vertical sheet count while retaining physical sheet size. Complete molecule
batches now add defined sheets to the same document when necessary. Existing
content is retained. One hidden native measuring copy supplies actual visible
molecule/caption bounds before the final append. Complete-table cells have
common column centres, row centres, caption baselines and chemical scale.
Related structures use a fully shared supplied ring/linker framework for
orientation; no guessed maximum-common-substructure chemistry is introduced.

The retained 17-structure LSD-family regression was drawn as one batch beneath
an unchanged reference page: 18 structures, four A4 pages, one editable document.
Native graph, geometry, source preservation, table-centre and baseline checks
passed. All four exported PDF pages and a rendered PNG table page were visually
checked. This tests drawing/layout, not the historical compound-name research.
Artifacts: /Users/glenn/Desktop/ChemDraw-rc10-LSD-Export-Pages.

New chemdraw_export_figure and export-figure entry points preserve physical
chemical scale, use point-sized SVGs, and produce DPI-tagged transparent PNGs
without fitting each molecule to equal pixel dimensions. Multipage drawings
produce one PNG/SVG per drawing page; optional native PDF retains physical paper
pages. PDF uses an owned hidden copy so an untitled source is not renamed.
No HTML review is needed. Physical export does not normalize inconsistent input
bond lengths; it preserves the source scale. Limits are in docs/PHYSICAL_EXPORT.md.

Verification: final portable suite 1098 passed and 89 skipped; the dedicated
paged-table/export native test passed;
all five existing native add-in tests passed. Frozen bundle/packaging acceptance:
10 passed, one opt-in live-read test skipped. Disk-image checksum verified.
The local rc10 DMG is on the Desktop. No real client configuration was changed,
and no GitHub release was published. Independent-Mac acceptance remains open.

Glenn's next requested work is tracked in docs/ROADMAP.md: terminal installation
walkthrough, graphical updates, refreshed GitHub presentation, architecture and
customization documentation with worked examples.

## 2026-09-16: rc9 installer corrections; table and export gaps remain explicit

Fixed preparation's uncaught EADDRINUSE with an actionable busy response and
readiness reset. Other OS errors are not misdiagnosed. The helper does not kill
another client, rotate credentials or pretend simultaneous access is supported.
Client checkboxes now use the pink theme, Codex / ChatGPT is the visible label,
and normal selection no longer scrolls. App name and selector share a row; the
full path is available on hover. The existing 800 by 400 point size is retained.
Selected, prepared and connected native SwiftUI previews were visually checked.

Found and fixed an actual planner translation error: free-space placement is
the destination of the batch envelope, not a displacement from zero. A narrow
first cell previously added 30.284644 pt of unintended horizontal offset in the
regression case. Complete-table overflow now returns table_needs_space with zero
insertions and explicit instructions against independent smaller batches,
omitted structures or a second-document workaround. This is a guard and one
placement correction, NOT completion of the requested publication-quality table.
Native ink centering and consistent layout across previously inserted batches
still need implementation and native acceptance.

Glenn clarified the desired direction: defined pages inside ONE document, not an
endless canvas. The vendor JavaScript API reference and installed ChemDraw 23.0.1
scripting dictionary expose no canvas-size setter. Existing shared insertion
still supports one physical page. Asked permission for a bounded page-settings
UI step; no such fallback has been implemented. No user drawing was changed.

Export investigation: house drawing verifies 18 pt bond length, but raster.py
fits every cropped SVG to a fixed longest side. Consequently separate exports
do NOT guarantee equal bond lengths in pixels. Next task after layout: retain
physical chemical scale, crop whitespace without fitting each molecule, use a
fixed DPI for PNG and explicit physical dimensions for vector output. Different
structures should have different image dimensions at the same chemical scale.
This export change is recorded, not implemented in rc9.

Red/green regression failures reproduced the raw occupied-port exception,
envelope offset and unstructured advanced-tool overflow. Portable suite:
1082 passed, 88 skipped. Frozen runtime/extraction tests: 10 passed, one live-read
test skipped. Package self-check, ad-hoc signature and disk-image checks passed.
The active endpoint was occupied; fresh native drawing acceptance was not run.
No user installation reset or client configuration change; nothing published.

## 2026-09-16: rc8 neutral Mac installer and brighter personal accents

The main local deliverable is ChemDraw-MCP-Apple-Silicon-rc8.dmg, with the same
native animated helper and a neutral ChemDraw MCP name. The first page offers
Claude Desktop and Codex local-client checkboxes. Finish copies one versioned
application outside any client's extension directory and creates a stable stdio
launcher. Selected client configurations are merged with private backups; other
servers/settings and Codex comments survive. Conflicting same-name entries fail
before changes. A recognized Claude MCPB installation is not duplicated in JSON.
No real user client configuration was modified while developing/testing this.

The alternative neutral MCPB detects its already-registered host and can add a
Codex connection. After setup, bundle launches hand off to the shared installed
runtime. A standalone DMG does not require Claude to open the helper. The source
checkout/animated terminal first-run remains an optional independent route, not
a second installation required by graphical users. Public GitHub release is not
performed by this work.

Glenn requested more of the pink/lavender/yellow artwork and understated
brutalist/fine-line accents. Surfaces are now lighter plum-charcoal, buttons use
clear pink fills, and a thin tricolor rule and corner strokes frame the unchanged
native molecule animation. The native Finder icon and MCPB icon share the palette.
Actual welcome and connected SwiftUI views were rendered and visually checked.

Red/green tests cover client selection, preservation/backups, idempotency,
conflicts, symbolic-link refusal, versioned copying, bundle handoff, generic
MCPB hosts and neutral branding. Portable suite: 1077 passed, 88 skipped.
Packaged/extraction checks: 10 passed, one live-read test skipped. Tests exercised
the real frozen runtime through the shared launcher and the MCPB handoff, actual
MCP initialization/ethanol identification, and Codex CLI parsing of its generated
configuration in an isolated home. DMG integrity, native ad-hoc signature, logo
and MCPB manifest checks passed. No drawing writes were needed.

This is not fresh Claude/Codex desktop click-through or drawing acceptance.
Native connection ownership still requires one active client at a time; multiple
configured assistants are not simultaneous editing support. Developer ID signing,
notarization and another-Mac acceptance remain pending. No user installation reset.

## 2026-09-16: rc7 minimal setup, molecular centering and personal palette

The wizard now has three pages. Software checking automatically proceeds to
preparation, with a small check mark on the installation page. The connected
page shows the successful document read and Finish setup only. Completion saves
state, releases the backend and closes the app, without an Open Claude page.
Diagnostics are available only when something fails; Change app is removed from
normal later stages. Selection can still be changed on the first page.

Sprite layout now uses actual occupied braille-dot bounds, preserving aspect
ratio and centering every molecule in the same viewport. Tests cover padding
invariance, empty sprites and all nine shipped molecules. Charcoal, cream,
muted pink and gold reflect Glenn's supplied profile images without redesigning
the window. A matching vector molecular logo is rasterized to the declared
512-pixel Claude extension icon during the build.

Regressions were observed failing before implementation. Portable suite:
1066 passed, 86 skipped. Seven frozen/extraction checks passed; the opt-in live
read was not rerun because this change is presentation-only and the installed
client retains the live connection. MCPB manifest/icon validation passed. Native
SwiftUI preview rendering covers the welcome, instructions and connected states.
Glenn's rc6 screenshots independently establish successful fresh installation
through the live-read page; rc7 client click-through remains a user test.

No client reset, drawing edit, Git publication or security-setting change.

## 2026-09-16: rc6 visible installer export and duplicate-install prevention

Glenn correctly shared rc5.mcpb. The friend reached the subsequent ChemDraw import
and reported an invalid-ZIP error for the locally generated .chemdrawaddin, plus
a possible duplicate-name warning. That remote package is unavailable; the local
one passed ZIP validation. Inspection found two setup hazards: the archive lived
inside its own installation destination, and GUI preparation populated installed
assets before asking for import. Regressions fail for both old behaviors.

Installer ZIP creation is now atomic and CRC-checked outside the destination.
Fresh GUI setup creates only private connection state and a staged installer;
it does not prepopulate the target add-in folder. Existing installations retain
their identity. A Save installer to Downloads button exports a validated private
copy through a standard Save dialog. The GUI distinguishes fresh import from
enabling existing files and explains duplicate-name recovery without deleting
other add-ins. Both actual SwiftUI screen states were rendered and inspected.

Frozen package acceptance passed eight checks, including a fresh isolated-home
prepare/export without preinstallation, ordinary ZIP extraction, MCP handshake,
chemistry, rasterization and a real live read. ChemDraw Add-in Manager import on
the friend's Mac remains unverified. No other MCP was removed. The linked
jurimaxam-dotcom project documents RDKit rendering without ChemDraw; there is no
evidence that it owns our native add-in identity or caused this error.

Final portable suite: 1064 passed, 86 skipped in 16.22 seconds. Delivered
Desktop/ChemDraw-for-Claude-Apple-Silicon-rc6.mcpb with corresponding source and
notices; manifest and deep ad-hoc signature validated. Final archive extraction
acceptance passed. Previous test installers were retained. No Git publication.

## 2026-09-16: rc5 compact wizard and Claude extraction fix

Glenn installed rc4 in Claude and the setup window opened, but the chemistry
check failed. Inspection of Claude's installed bundle reproduced the exact
failure: library aliases were tiny text files containing link targets, and
RDKit reported libRDKitRDBoost.1.dylib was not valid Mach-O. The previous ditto
extraction acceptance preserved symlinks and therefore missed this client behavior.
The builder now materializes runtime links and refuses links in its final stage.
A regression test fails on rc4 and passes on rc5 using plain ZIP extraction.
The misleading incompatible-Mac/re-download message was also replaced.

The SwiftUI window is now 800 by 400 points instead of 800 by 720. Setup starts
with a prominent Select ChemDraw button, shows the validated application, and
disables Next until selection succeeds. Numbered Next stages lead through checks,
add-in preparation and enabling, then live connection verification and Finish.
Changing apps clears old readiness. Animation and small author credit remain.
Welcome, selected and add-in screens were rendered from the real view and checked.

Portable suite: 1059 passed, 85 skipped in 14.44 s. Frozen-runtime/native-read and
packaging acceptance: seven checks passed. Computer control still cannot connect;
rc5 installation through Claude itself needs Glenn's retest. No user drawings or
installed client files were modified. Desktop rc5 MCPB includes corresponding
source and notices. Apple Developer ID/notarization and another Mac remain pending.

## 2026-09-16: graphical Claude Desktop test bundle, 0.10.0rc4

Built an Apple Silicon MCPB with a self-contained Python/RDKit/resvg runtime and
native SwiftUI setup window. It reuses the existing nine molecular silhouettes
and adds a small Created by Glenn Bojanov credit. Buttons guide dependency checks,
ChemDraw selection, local private add-in preparation, activation instructions,
live connection testing and plain-text diagnostic export. No Terminal or Markdown
reader is part of the intended user setup. Completion requires a real API read;
the helper releases its endpoint before native MCP tools become available.

TDD covered setup state, app validation, JSON protocol, endpoint release, manifest
and native-tool setup gating. Portable suite: 1056 passed, 84 skipped in 14.79 s.
The actual frozen runtime passed five acceptance checks, including MCP discovery,
offline chemistry, raster-worker dispatch and live read. The delivered archive was
extracted to a new location and those checks repeated successfully. Real native
SwiftUI welcome and preparation screens were rendered and visually inspected.
MCPB CLI 2.1.2 validated the manifest; ad-hoc signatures passed deep verification.
The archive includes corresponding project source and dependency license notices.

Delivered Desktop/ChemDraw-for-Claude-Apple-Silicon-rc4.mcpb. This is a local test
candidate. Computer-control service startup failed, so Claude's installation UI
has not been exercised. Developer ID signing/notarization, another Mac and the
first native drawing from Claude remain release gates. No Developer ID identity
is available on this Mac. No client configuration, Git commit, push or publication
was performed. Build and acceptance details are in docs/DESKTOP_INSTALLER.md.

## 2026-09-16: 0.10.0rc3 another-Mac handoff

First-run no longer depends on an HTML review or browser launch. It validates
native shared artifacts and returns CDXML/SVG/PNG plus JSON checks. Doctor now
checks a real CDXML writer roundtrip, records environment/package versions and
reads the desktop API through the current MCP backend. Missing setup, no document,
another endpoint owner and offline-only readiness are separate outcomes. No
drawing is inserted by diagnostics. Standalone checks may open the installed
connection panel, which is closed when that process exits.

The endpoint became free and the pending caption/replacement-scope tests ran.
Native targeted first-run/caption/replacement tests: 3 passed in 22.63 seconds.
Full shared API plus first-run suite: 6 passed in 38.37 seconds, including Finder
foreground checks, stale rejection and mixed chemistry. Evidence is retained at
local-validation/rc3-shared-acceptance-1 and rc3-shared-acceptance-2. Native-derived
first-run, caption and scope PNGs were reviewed on white; core orientation and
label counts passed. Equal conservative envelope centres are portable-verified,
not a claim of universal pixel-perfect native-ink centring.

Clean serial portable suite: 1043 passed, 79 skipped in 13.63 seconds. A preceding
overlap with native tests caused two lock refusals; no production code was changed
to bypass coordination. Fresh extracted source installation independently passed
1043 portable tests, 79 skipped in 15.13 seconds. The wheel was installed separately
and verified to import from site-packages with rc3 metadata and working CDXML writer.
Version and uv lock advanced to 0.10.0rc3. Handoff guide, client comparison form and
redacted validation summary are in docs/TEST_ON_MAC.md, TEST-RESULTS.md and
VALIDATION-0.10.0rc3.md. Archives exclude local credentials and native test bundles.
No Git commit, push or package-index publication. Independent-Mac acceptance remains
pending; the package is a test candidate, not a stable release.

## 2026-09-16: replaced-substituent orientation and shared auto panels

Fixed two regressions from the ten-analogue user test. Whole-live-parent matching
failed when the requested H/F/Cl derivatives removed its methyl branch. The API
planner now reuses the existing conservative whole-supplied-ring-core rule when
that match fails, anchoring the verified core to a unique matching live graph.
Without a live match it uses the first requested structure as reference. This is
not unrestricted MCS inference; inputs with no verified core still have independent
depictions, and the advanced tool accepts an explicit scaffold.

The harness now selects plain grid layout for shared auto panels before native
execution while retaining the inferred core. It no longer plans unsupported
decorations and forces a second request. Explicit advanced-tool groups remain
rejected rather than silently discarded. Background grouping is unchanged.

Three regressions failed before implementation, then passed. The actual retained
user before.cdxml and ten requested structures were also replanned read-only:
three columns, house scale, live reference, every centred core atom within 0.03 pt
without rotational fitting. Portable suite: 1036 passed, 79 native tests skipped.
A real stdio MCP test now covers the same parent-plus-ten auto call, label count,
native core coordinates, house style, same untitled document and forbidden
intermediate imports. It is not yet run: the separate user Codex MCP process owns
the installed endpoint. That process was not terminated. No new native acceptance
or visual verification is claimed. Restart the testing MCP client to load changes;
no add-in reinstall is required. No commit, push or extra features in this change.

## 2026-09-16: plain batch caption and centre-alignment regression

The client report exposed formula fallback captions and vertical top alignment.
Native snapshots also showed DMT and formula captions converted into molecular
fragments, including nested abbreviations. Caption text now sets the documented
InterpretChemically=no property locally, preserving document defaults. Unlabelled
SMILES/InChI inputs receive numbers instead of formulas. The grid centres each
molecular envelope horizontally and vertically on equally spaced cell centres.
Existing common-parent orientation and chemical scale are retained.

Regression tests failed on all three old behaviours before implementation, then
passed. An additional preflight now refuses unverifiable existing fragments before
inserting anything, rather than discovering that problem after an append. Earlier
bad captions are not automatically rewritten. Full portable verification: 1032
passed, 77 skipped; a subsequently added native caption-count test is awaiting the
user's current MCP endpoint to be released. Native rendered centre precision and
caption behaviour are not yet claimed as verified for this change.

## 2026-09-16: installed add-in missing after application restart

Reproduced the client failure: package and installed files existed, saved enabled
status was true, but the native command and Add-in Manager entry were absent.
ChemDraw Preferences > Directories had an empty ChemDraw Items search list.
The bundled manual identifies that list as the startup add-in search locations.
Added the existing per-user ChemDraw support directory through Preferences and
restarted after verifying all open documents were empty and unmodified. Native
addin_available changed from false to true without reinstalling the package.
The setup response now distinguishes an unavailable command from missing files
and includes this search-path remedy, covered by a failing-then-passing regression.
A separate API-read probe could not own the endpoint while the user's current
MCP process held it; no process was killed and no drawing was changed.

## 2026-09-16: ordinary drawing migrated to the one-canvas API

The ordinary chemdraw_draw and advanced chemdraw_draw_structures entry points now
route auto/shared/interactive molecule batches through the installed desktop API.
The whole batch is planned locally using RDKit's ChemDraw CDXML writer, then
inserted once. No per-molecule native import, clipboard placement or arrow keys.
Both live-read and analyze return graph identities from current unsaved content;
captions remain separate. One unique matching live parent supplies orientation.
New objects carry house typography and strokes without restyling old objects.

Real stdio MCP acceptance with _open_working disabled passed: a modified fused
parent with a stale Caffeine caption, actual graph readback, eight more analogues,
same untitled document, nine molecules total, unchanged inventory apart from the
test canvas, Finder retained focus. Native house checks and exported-image review
passed. Evidence: local-validation/api-ordinary-4. A second native batch passed
tetrahedral/alkene stereo, isotope, formal charges, aromatic NH and explicit H:
local-validation/api-mixed-3. The first failed mixed runs caught native label
reinterpretation; charge text and isotope superscript runs now match proven
native encodings. No uncertain append was retried into its original document.

SVG export from an untitled document was separately tested without filename or
modified-state changes. CDXML is read through the API; resvg rasterizes native
SVG. Native export may add derived AS/BS metadata, checked separately from graph,
geometry and drawing properties. Shared artifacts contain the whole canvas.

Decorated groups/reactions, circled charges, arbitrary graphics and custom
layout/style remain outside this API path and fail explicitly. Explicit background
still uses the older workflow. This is a logged-in desktop integration, not a
headless renderer. Local client skill/tool instructions now describe this routing.
No commit, push or package publication was performed in this change.

Final portable verification: 1029 passed, 77 skipped in 14.31 seconds. Native
reruns api-final-1 through api-final-3 completed the ordinary parent/eight-analogue
insertions and mixed chemistry batches with chemistry, geometry, style and canvas
inventory checks passing. The last suite was not wholly green: foreground checks
expected Finder but observed Vivaldi, Obsidian or ChemDraw in different runs.
Foreground retention is therefore not consistently verified, despite earlier
passing evidence; no cause is assigned without further isolation. The resulting
drawings were not retried. Recorded test-owned untitled canvases were closed when
still present, with recovery artifacts retained.

## 2026-09-16: direct desktop API bridge accepted through real MCP

Added the original local authenticated add-in transport under the distinct name
ChemDraw MCP Native API. The official desktop ChemDrawAPI 1.6 getCDXML and
addCDXML calls now have full-profile MCP and CLI entry points. This is an opt-in
backend, not a claim that the existing drawing harness has been migrated.

Native debugging identified two transport issues: the local WebKit GET omitted
Origin and POST sent file://; initial add-in opening required activating ChemDraw.
Exact Host/private bearer checks remain enforced. Later operations do not require
OS focus. A stable private endpoint survives process reconnects. Credentials and
generated packages stay local and are not repository assets.

Exact-coordinate verification now bypasses clipboard-specific bounding-box
translation while retaining the existing chemistry, mapping, page and collision
checks. Native object IDs may be renumbered and text ink bounds recalculated;
atom positions may only vary within the existing 0.03 pt rounding tolerance.

The real stdio MCP test passed in 6.45 seconds: untitled read; five structures in
one API append with Finder frontmost; stale-token rejection; sixth structure in
the same document; unchanged existing content/page/file binding/document inventory.
The test closed only its own drawing after saving recovery snapshots. Evidence:
local-validation/addin-mcp-native-8/test_native_api_untitled_batch0/addin-native-report.json.
Earlier transport and verifier failures remain diagnostic evidence, not successes.

Portable suite: 1002 passed, 75 skipped in 13.83 seconds. No commit or push.
Pending: route ordinary name/SMILES drawing and scaffold-aligned scope generation
through this backend, add broad native fixtures, and test on another Mac. The
legacy draw/shared pipelines still use their existing intermediate-document and
clipboard paths until that migration is implemented and verified.

## 2026-09-16: real-client duplicate-window and untitled-read follow-up

The client transcript exposed gaps in the earlier shared-delivery milestone.
Advanced draw_structures still used separate-document delivery, and the client
called it twice successfully to change labels. Both final windows remained.
Live reading and analysis also still demanded a named document. An uncertain
shared insertion was incorrectly treated as completed by that client because
export artifacts existed.

Advanced draw_structures now accepts document_id and shared mode through MCP
and the CLI manifest; auto selects shared delivery when a document is visible.
Explicit interactive mode still means a separate final document. Tool descriptions
and server instructions distinguish these routes, prohibit whole-job retries just
to relabel, and require honoring uncertainty. Generated validated CDX sources are
closed before the shared paste, so a later paste failure cannot leak that final.
Unsupported shared reactions/decorated groups stop before native generation.

Untitled live-read and analyze now use no-save native Copy As snapshots. Clipboard
bytes are restored, selection becomes all objects, and returned state says so.
Current-selection actions refuse dispatch if snapshotting changed that selection.
Untitled live tokens ignore regenerated page handles and printer metadata while
retaining content and geometry. Background/separate production still guards other
untitled documents; its message now points to shared delivery where appropriate.

Keyboard placement now reconciles delayed movement, bounds confirmed no-op pulses,
releases held keys on failure and never repeats the paste. An initial native trial
stopped on changed selection geometry; that safety check remains strict. The later
three-test run passed, followed by all four native cases in 121.17 seconds:
untitled insertion/read/analysis without filename assignment, placement and Undo,
two successive real MCP additions, and an advanced three-molecule MCP panel in
the same target. Existing objects and native inventory were checked. The failed
test-owned document was backed up and closed; user drawings were not closed.

Portable result: 980 passed, 74 skipped in 8.16 seconds. Native evidence is retained
under local-validation/shared-routing-native-20260916-d. Native operations were
serialized. Intermediates are hidden after native opening; brief opening flashes
are NOT eliminated. A visibility probe found no extra visible windows after hidden
create/export/cleanup calls, but does not establish zero transient flashes.
No commit, push, release or client configuration change. Running MCP processes
must reload to use the changed code.

## 2026-09-16: shared molecule delivery accepted

Glenn approved narrowly scoped keyboard placement. Native selection bounds cannot
be set on this ChemDraw build (-10000), and CDX paste framing does not control
placement. Shared delivery now pastes native CDX, measures only the new selection,
uses bounded arrow-key nudges with position readback, and verifies existing
chemistry/coordinates, added chemistry/geometry, planned position and page size.
Clipboard formats and bytes are restored. No SMILES/MOL paste is used.

The unconditional shared gate is removed. Auto reuses one visible document;
explicit document_id chooses among several. Blank and populated untitled documents
work without saving or closing. Separate interactive/background modes remain.
Shared support is currently flat molecules/captions on one physical page, not
reactions, decorated panels or arbitrary graphics. Generation still uses hidden
native intermediates; this is not true headless rendering.

Native acceptance: 2 passed in 61.65 seconds. Actual MCP stdio made two successive
additions to the same document with no extra result documents retained. The
placement test checked preservation, planned position within 1 pt, clipboard
restoration and Undo restoration. Native page handles/printer records regenerate
on Copy As and are excluded from drawing fingerprints, not drawing/page geometry.
Undo requires the paste plus individual nudges, not one operation.

An additional native trial created a test-owned untitled document and inserted
pyridine without assigning a filename. The actual CLI then added aspirin with
default auto and no document argument, retaining the same ID and both molecules.
Evidence: local-validation/shared-default-20260916/drawing. Portable result:
971 passed, 72 skipped in 7.98 seconds. A parallel portable/native invocation
initially collided on the cooperative lock; rerunning sequentially passed.
No commit, push, release or client-config change. Running servers must reload to
import the changed Python modules.

## 2026-09-16: shared delivery implementation blocked on native positioning

Added an experimental shared-delivery module, clipboard transaction script,
placement/preservation tests, and shared/document arguments in CLI and MCP.
The shared entry point is deliberately gated with shared_placement_pending before
any native operation. It is NOT delivered as a working feature. Existing auto,
interactive and background behavior is unchanged.

Native CDX paste and no-save CDXML reads work on the owned test fixtures. Repeated
selectAll must check command availability when everything is already selected.
The native selection-bounds setter returned -10000. CDX framing bounds did not
control placement: pasted content remained page-centered. Do not enable that
route as collision-aware insertion. Native CDX export also normalized print
metadata, so Undo comparison must snapshot after that separate export.

Portable checks: 968 passed, 71 skipped in 8.08 seconds. Native shared acceptance
has NOT passed. The next tested route would use focused keyboard movement of only
the pasted selection; explicit approval was requested and not yet received.
No keyboard events were sent. The supplied manual documents one-point arrow-key
movement. System Events reports UI elements enabled, but that is not an acceptance
test. Current native inventory was empty at the final read; no automatic closing
of pre-existing documents was performed.

No release, commit, push or MCP-client configuration change.

## 2026-09-16: shared-document clipboard capability spike

Glenn approved a controlled clipboard experiment and chose shared-document work
over prioritizing true headless rendering. Native CDX clipboard data can append
editable chemistry to the same document without a helper window. Explicit app
activation was needed for reliable native Undo in the probe. Completed trials
restored original clipboard formats and bytes exactly. Copy As CDXML Text reads
the selected drawing without a native save, but selecting all changes the human's
selection, so it is not yet a transparent replacement for live-read.

The direct SMILES/MOL routes failed: aromatic interpretation was incorrect, and
MOL paste requested expansion to 39 pages. The user was told to cancel the prompt.
Those routes are now disabled at probe entry and must not ship. No production
clipboard endpoint or general shared-document editor was added. Findings and
remaining guards are in docs/HEADLESS_AND_SHARED_DOCUMENT_RESEARCH.md.

## 2026-09-15: headless and shared-document feasibility

Glenn requested actual headless rendering, otherwise one persistent human/agent
working document without window churn. Investigated the installed native API,
cold startup and vendor server documentation. Findings and sources are in
docs/HEADLESS_AND_SHARED_DOCUMENT_RESEARCH.md.

Explicit AppleScript launch after confirmed shutdown produced a non-frontmost
application with zero documents and zero windows. Ordinary startup via document
listing created a blank untitled document. An initial launch raced termination
and returned -600; the successful trial waited for confirmed shutdown. This is a
desktop-startup improvement candidate, not display-free rendering or proof of
zero window flash during imports. No production behavior changed.

Hidden native export and document-addressed cleanup worked. Five same-document
creation variants (caption, atom, molecule from text, two binary structure insertion
locations) returned -10000 and left object counts unchanged. General shared-document
insertion remains unimplemented. No clipboard fallback was used. Existing same-ID
read/edit/export integration tests passed again: 2 passed in 11.58 seconds,
local-validation/shared-document-recheck.xml. No pre-existing user documents were
present; only test-created documents were closed and the final inventory was empty.

Revvity documents a separate ChemDraw Web Service with server-side SVG generation;
it is supplied with the JS subscription and its API carries a private/changeable
warning. It was not installed or tested here. Native desktop headless support has
not been established. No package, license, client configuration or GitHub changes.

## 2026-09-15: native harness acceptance unblocked

The user saved the template as Chemdraw-template_Sharpless-1.cdxml. The file was
present and the native document inventory was empty before testing. No user
document was saved, edited or closed by this run.

Actual reduced-profile MCP acceptance: 3 passed, 1 skipped in 52.37 seconds,
recorded in local-validation/harness-native-final.xml. Cases cover a mixed panel
with tetrahedral/alkene stereo, isotope, fused heterocycle and formal charges;
an automatically grouped common-core panel with native shadow frame and dotted
dividers; and an explicit reaction. All mandatory gates passed. Background finals
closed, and the native inventory remained empty. The untitled-document guard was
skipped because the session no longer contained an untitled document; its earlier
positive evidence remains separate.

All three native PNGs were inspected on white. Artifacts and white inspection
images are retained in local-validation/harness-native-accepted-artifacts.
Chemistry, labels and frame/dividers are legible; layout is not yet optimal.
The mixed five-molecule case chooses four columns and leaves a sparse final row.
Group bands also leave unused width. Next product work should improve bounded
automatic layout selection and expand native corpus coverage, without relaxing
identity or collision gates or introducing molecule-specific exceptions.

Portable reconfirmation after native tests: 961 passed, 70 skipped in 8.20 seconds,
local-validation/harness-portable-confirmed.xml. No implementation change was
needed for this acceptance run. No commit, push, client configuration change or
release. Independent-Mac acceptance remains pending.

## 2026-09-15: guarded drawing harness, not example-specific polishing

Glenn clarified the product requirement: ordinary imprecise prompts should reach
a reliable forced pipeline, including from a weaker model. Stop optimizing one
example figure. The useful product is the harness and guardrails around native
ChemDraw, with breadth tested across different chemistry.

Added the typed `chemdraw_draw` front door and matching `chemdraw-mac produce`.
The optional drawing MCP profile exposes only this tool and diagnostics; full
retains the advanced surface and now directs new drawing requests to the harness.
Typed names/CAS use explicit network opt-in and bounded candidate handling;
explicit SMILES/InChI remain offline. Products must be supplied, never predicted.
The code owns numerical style, generated compound numbering, measured column fit,
native rendering, required audit gates, independent delivered-graph checks,
conservative measured collision screening and final artifact checks. Result states
distinguish completed, needs_input, rejected and uncertain. There are no skip-check
fields, silent alternative renderer, or uncertain-write retries.

Related-panel defaults require a whole supplied ring-containing parent that
matches every input with stereochemistry. Exact single-aromatic-attachment motif
rules determine descriptive groups; unknown cases remain Other substitutions.
This is not unrestricted scaffold inference or an electronic-property calculation.
Reference-constrained new MOL seeds solve native mirror-layout mismatches without
reflecting existing drawings or relaxing the rigid-fit tolerance. Grouped panels
reuse existing native frame/divider tools and the measured column count.

Shared production presentation hides intermediates in molecule, grid, reaction
and scope-job workflows. Auto mode is sampled before app-launching reads. Only
the outer completed result is presented or closed; nested jobs do not prematurely
close their inputs. Direct core create/import visibility remains unchanged.

Portable result: 961 passed, 70 skipped in 8.55 seconds, recorded in
local-validation/harness-portable-final.xml. This includes 38 chemistry-corpus
input/support cases, not 38 native visual acceptances. The existing grouped native
production path completed a 12-structure background run with chemistry/layout
checks before the harness was added. That is component evidence, not acceptance
of the new front door.

The three new positive native harness tests did not complete: an unrelated
untitled user document cannot be preservation-exported without assigning a file.
The first run misreported this as uncertainty. A failing regression now enforces
a read-only preflight needs_input response with the affected document identified.
Actual reduced-profile MCP guard test: 1 passed in 1.41 seconds, report
local-validation/harness-native-preflight.xml. The user document stayed unchanged.
Do not rerun positive native tests until it is saved or closed by the user. No
automatic save/close, client-config change, commit, push or release was performed.

The local chemdraw-house-style skill now routes new requests to the native harness
instead of the old RDKit renderer and passes the skill validator. Native positive
acceptance, measured collision false-positive assessment, broader structure
coverage and second-Mac acceptance remain required before a release claim.

## 2026-09-15: existing-document actions and background native rendering

Glenn requested one live ChemDraw window beside the terminal, no preview or
duplicate working document, and unattended use as well. New shared CLI/MCP
interfaces read the actual in-memory document, dispatch token-checked native
actions on explicitly addressed user documents, show/hide one window, and render
supplied CDXML in a hidden owned document. Both profiles expose the four tools.
Reads report raw objects and current selection bounds/counts without requiring
RDKit. Existing documents are never promoted to server ownership or closed.
The recovery snapshot precedes an action; uncertain writes are not retried.

The background renderer exports CDXML/SVG/PNG/PDF, writes a result report, creates
no HTML preview and closes its owned document only after successful exports.
It does not certify chemistry, replace the validated drawing workflows or make
all older workflows background-aware. A logged-in licensed desktop is required;
an initial window flash is possible. Display-free operation is not established.

Native probes confirmed hidden cleanup/export and restoration. The advertised
selection-content getter and molecule creation from supplied native structure
data returned error -10000. General same-document atom edits remain unimplemented;
no clipboard/GUI fallback was introduced. Manual changes are detected on the next
read, not continuously. Snapshot checks do not atomically lock human edits, and
selection bounds/counts are not selected-object identity.

An initial native test failed because assigning the selection object to a variable
invoked a broken native getter. Direct count/bounds property references worked;
a failing regression preceded the correction. Final portable result: 883 passed,
66 skipped in 8.23 seconds (local-validation/live-document-portable-final.xml).
Final focused native result: 2 passed in 12.32 seconds
(local-validation/live-document-native-final.xml), covering core MCP same-document
cleanup, external native edits, stale-token rejection, ownership isolation,
hidden export and the actual background CLI with all four formats. The earlier
failed test's owned scratch document was identified, backed up and closed.
The original open user document remained untouched. No release, commit or push.

Additional native regression run: all eight tests in tests/test_live.py passed
in 58.08 seconds, including both MCP profiles, polish and previous analogue
edits (local-validation/live-document-core-regression.xml). This is a focused
regression run, not the complete native suite or another-Mac acceptance.

## 2026-09-15: expanded edits, placement guards and consistent production

The full-profile target editor now supports explicit element/H/unit-charge edits,
plain nonaromatic bond orders with both endpoint H counts, supplied-fragment
attachment (1 through 100 atoms, including methyl), and removal of a branch across
an explicit connecting bond. Retained coordinates and other molecules/captions
remain fixed. Requested H/charge values are checked against the decoded graph.
Ring cuts, invalid valence, unsupported stereo changes and dangling crossing
references are refused. The existing CLI/MCP endpoint exposes the exact operations;
these are copied-CDXML edits rendered by ChemDraw, not native UI selection setters.

Attachments support twelve deterministic 30-degree placement candidates. New
collisions with atoms, captions, labels and conservative bond envelopes fail
preflight; native measured labels are checked again after rendering. Existing
collision pairs are reported without silently repairing source artwork. Visual
review found a collinear fragment join hiding skeletal carbon despite valid graph
checks. A failing regression preceded a 120-degree terminal join and refusal of
new hidden-carbon vertices. The corrected native export was inspected on white.

Charge placement now uses actual inherited local obstacle bond widths, multiple
bond spacing and wedge allowances instead of the requested symbol's stroke as
a proxy. Newly placed symbols undergo a second clearance check against the saved
native drawing. Built-in presets now replace local style overrides and receive
the same native numerical/font verification as custom presets. Simple reaction
captions use the shared 10 pt visible-clearance convention instead of a baseline
offset. Existing explicit lab-style settings remain available and unchanged.

Final portable result: 873 passed, 64 skipped in 8.38 seconds, recorded in
local-validation/expanded-edit-portable-final.xml. Final targeted native run:
9 passed in 67.00 seconds, local-validation/expanded-edit-live-final.xml.
Separate native production/placement run: 11 passed in 124.24 seconds,
local-validation/consistency-placement-live-1.xml. The latter covers custom-style
draw/reaction, built-in aligned and ionic drawings, circled charges, lone pairs
and electron-source arrows. These are separate focused runs, not a complete native
suite or another-Mac acceptance. An intermediate portable run overlapped the live
client and two mocked native-action tests hit the cooperative lock; the final
portable run was serial and passed. No uncertain write was retried.

White-background native previews were inspected for the corrected fragment,
charge edit, carbonyl, reaction, aligned aromatic pair and circled ions. Task
documents were backed up and closed by successful tests with unchanged baseline
document inventories. Review artifacts remain in the named local-validation
folders. No release build, commit, push or publication occurred. Input restrictions,
bounded-search limits and approximate rather than pixel-exact collision coverage
are documented in docs/TARGETED_EDITING.md and docs/SYMBOLS.md.

## 2026-09-15: precise snapshot targets and bounded editing

Added full-profile inspect-targets, prepare-selection and edit-targets interfaces
through shared CLI/MCP functions. Targets are CDXML atom, bond and molecule IDs
bound to a source snapshot, not screen coordinates or native UI highlights.
Atoms expose element, XY position, charge, isotope, hydrogen and stereo data;
bonds expose endpoints, order and display. Actual XYZ geometry remains distinct
from 2D wedge notation. Native AppleScript and JXA selection-assignment probes
failed on this ChemDraw build, so native individual-object selection is not claimed.

The bounded editor supports directed solid/hashed wedges with explicit stereo-change
authorization, saturated 3-to-8-membered carbon rings attached by one single bond,
and native alignment/distribution of explicitly chosen molecules. Alignment runs
ChemDraw's command on an isolated subset and transfers only verified translations
back into a full document copy. Untargeted coordinates and caption anchors remain
unchanged. Sources are retained; successful edits produce native editable CDXML,
SVG/PNG, an audit and before/after review. Ring fusion, spiro attachment, general
collision solving and arbitrary grouped/reaction documents are not supported here.

Final portable verification: 853 passed, 58 skipped in 7.45 seconds, recorded in
local-validation/targeted-portable.xml. Three fresh native MCP fixtures passed in
26.17 seconds, covering nitrogen ring attachment, directed hashed wedge and
three-molecule alignment with a fourth molecule/caption left fixed. Evidence:
local-validation/targeted-live-2.xml and the corresponding fixture result folders.
Native SVGs were reviewed on white backgrounds. An initial alignment fixture
exposed harmless isolated-bond Warning metadata; a failing regression test preceded
support for retaining and reporting that warning. All completed task/probe copies
were backed up and closed; the pre-existing document remained untouched.
No package rebuild, commit or push was performed. See docs/TARGETED_EDITING.md.

## 2026-09-15: direct native commands and native naming

Added `chemdraw_native_action` and `chemdraw_draw_name` to both profiles, bringing
core to twelve MCP endpoints. The action endpoint dispatches twelve allowlisted
ChemDraw commands: structure/reaction cleanup, six alignments, two distributions,
and label expansion/contraction. CLI native-action imports a private working copy;
MCP requires session ownership and the requested frontmost document, preserves
current selection by default, and supports explicit selection of all objects.
A backup precedes the action. Disabled commands return unavailable_for_selection.
No raw command, clipboard or GUI fallback is exposed.

Native naming uses ChemDraw's caption conversion command, not an RDKit depiction
or coordinate seed. It requires explicit network consent because ChemDraw may
fall back to ChemACX without reporting which lookup provider was used. It creates
native CDXML/SVG/PNG, review HTML and a retained audit. Runtime checks establish
structure presence and unchanged pre-existing document metadata, not independent
chemical identity. Native source-caption placement remains visible and can leave
substantial whitespace; this interface is not yet a polished name-caption layout.

Red/green portable tests cover command dispatch, ownership, recovery ordering,
disabled commands, input validation and actual stdio discovery/calls in both
profiles. Final portable result: 834 passed, 55 skipped in 7.54 seconds, recorded
in local-validation/native-tools-portable-final.xml. Two native core-MCP naming
fixtures passed independent graph checks, including a specified R stereocentre
(local-validation/native-names-live.xml). Eleven native action cases passed in
42.48 seconds (local-validation/native-actions-live-final.xml), checking graph
preservation plus actual edge/centre alignment and equal distribution gaps.
Label expansion/contraction are dispatch-tested but not live-fixture accepted.

The original messy reaction showcase correctly returned unavailable: ChemDraw
did not recognize it for native reaction cleanup. A synthetic single-step,
straight-arrow fixture passed; the unavailable case remains a separate negative
test. Native cleanup does not harmonize every style difference: visual inspection
of local-validation/native-action-visual-check/reaction-white.png confirms that
the source's unequal molecule strokes remain. All known completed task copies,
including the copy retained after the first fixture assertion, were backed up
and closed. The pre-existing document was left open. No retry of uncertain writes,
package rebuild, commit or push was performed in this increment.

## 2026-09-15: independently usable core MCP and optional workflows

The basic native MCP was already implemented. The server now has an explicit
`--profile core` tool surface with ten direct native operations; `--profile full`
retains the existing default toolset. `chemdraw-mac serve` forwards the same option.
Core reuses the exact existing functions and schemas, does not require RDKit, and
does not expose the workflow tools. This is one package with selectable tools,
not two services or a new embedded language model. The connected AI client owns
natural-language interpretation; reusable server workflows own explicit drawing,
layout and preservation operations. README and docs/ARCHITECTURE.md now explain
that distinction and prioritize general input-driven capabilities over per-molecule
functions. Experimental metal work is separate from ordinary core usability.

Eight new portable profile tests passed, including fresh stdio discovery/calls,
non-core call rejection, unchanged full discovery, matching schemas, shared bridge
dispatch, CLI forwarding and an RDKit import blocker. The development working
tree's portable suite passed 803 tests with 41 skips before adding the second
native profile parametrization. Both native scratch profiles then passed in
17.85 seconds: creation, private-copy import, inspection, per-molecule and whole
document cleanup, style copy, CDXML/CDX/SVG/PDF/PNG exports, and closure of only
their known copies. Pre-existing document inventory/metadata matched afterward.
The final portable rerun passed 803 tests with 42 native skips in 7.90 seconds.
Reports: local-validation/core-profile-portable-final.xml and core-profile-native.xml.
This does not establish another-Mac or arbitrary chemical-subset acceptance.

The focused Git snapshot was also tested separately, excluding the pending
installer, cage, charge-search and complex changes. Its portable suite passed
742 tests with 36 native skips in 7.72 seconds. Its two full/core native scratch
tests passed in 17.64 seconds. Reports: local-validation/core-profile-focused-portable.xml
and core-profile-focused-native.xml. Only this independently tested profile,
documentation and export-guard increment is selected for the focused commit.

A preceding export probe exposed native save assigning a filename to an untitled
drawing during a snapshot. Core export now refuses that case before dispatching
save, with a source-order regression check. The prior drawing was not deleted;
its assigned backup name was not silently reverted. Live rejection of a newly
created untitled document remains untested.

The failed CDX binary-aromatic-patching test specification was moved to ignored
local-validation/abandoned_aromatic_cdx_spec.py, not implemented or weakened into
a passing production test. A later native probe preserved aromatic ring orders
with closed curves inside the molecular fragment. That general representation
finding is not integrated yet; ferrocene remains unavailable in the production
workflow. Existing local rc2 artifacts are unchanged.

## 2026-09-15: spatial chelate and native multicentre investigation

Development schema 2 is reachable through the existing complex-draw CLI and chemdraw_draw_complex MCP endpoint. It adds explicit coordination line/wedge/hash displays, original procedural chelate coordinates, optional per-atom RGB colour and a whole-complex corner charge annotation. Glenn clarified that blue nitrogen was only a reference-image detail: black labels remain the default, including the shipped ruthenium recipe. The initial long slanted Square bracket was replaced by a compact 16-point two-line corner. Native line supersession is verified, not mistaken for extra reaction arrows. Bond stroke changes, attachment membership, XYZ, graph records, native warnings and relevant crossing foreground order are checked separately.

The black ruthenium example passed the native workflow and white-background visual inspection at local-validation/ruthenium-black-final/review.html. It has three 2,2'-bipyridine chelates, plain axial bonds, two solid and two hashed metal-donor bonds. The charge corner no longer causes an unmatched-bracket warning. Six donor-valence warnings from conventional order-1 coordination depiction remain visible and are retained in the audit; chemical plausibility and Delta/Lambda assignments are not certified. The overall 2+ is a checked annotation, not a falsely asserted atomic charge sum.

Ferrocene remains a refused regression fixture, not delivered output. Actual MultiAttachment membership survives native import, but CDXML aromatic order 1.5 changed to single bonds; the validator refused the changed hydrogen/order records. Distributed multicentre charges were also discarded in a separate probe. A read-only inspection of a private copy of the installed Metallocenes template established working native binary patterns, including aromatic order, attachment nodes and ring outlines. No vendor coordinates or artwork were copied into project fixtures or public files. This isolates an import-path limitation rather than claiming ChemDraw cannot draw ferrocene.

Portable acceptance: 794 passed, 41 native skips, recorded in local-validation/spatial-complexes-portable-final.xml. A serial native set passed four cases in local-validation/spatial-complexes-native-confirmed.xml: direct v1 copper, actual fresh stdio MCP copper and ruthenium, and the expected ferrocene refusal with closure of its own failed copy. An earlier native run stopped during post-export document checking on a stale document ID, retained its uncertain owned copy, and is not counted as passed. A separate concurrent portable run hit the cooperative native lock; the final portable run was repeated serially. No uncertain native write was retried. Existing 0.10.0rc2 distribution files were not rebuilt or replaced. No commit, push or package publication performed in this increment.

## 2026-09-15: local 0.10.0 release candidate, onboarding and drawing fixes

The approved native molecular terminal sequence is integrated into interactive first-run onboarding, replacing the old ASCII ring. Alizarin replaces uric acid. Caffeine, azulene, saccharin, 5-MeO-DMT, urea, aspirin, vanillin, alizarin and dopamine are bundled as native-export-derived silhouettes at four terminal sizes. Names are hidden; fixed geometry receives a cyan reveal sweep under "Natural language → ChemDraw". The continuous bar is phase-weighted and only completes after the actual smoke test passes. Dependency installation progress remains uv's output before first-run starts. JSON/MCP do not animate. Actual Terminal first-run completed at local-validation/onboarding-integrated/first-run.json.

Circled-charge candidates use a finer angular/distance search without reducing symbol size, stroke or owner clearance. Nitrobenzene now passes with both native associations intact; tetramethylammonium still fails closed when no safe placement exists. Native crossing-cache validation and ID remapping allow cubane, bullvalene and adamantane, while saved relative foreground order remains checked. Native recomputation can change cache membership and absolute Z numbers, so verification compares order across relevant declared/geometric pairs instead of string equality. Cage and nitro previews were inspected on white.

Before the separate metal feature, the complete native-enabled suite passed 785 tests in 408.97 s (local-validation/rc1-native-full.xml). The final portable suite after metal work passed 773 with 39 native skips in 6.35 s (local-validation/rc2-portable-final.xml). Both additional metal native tests then passed in 6.60 s, including fresh stdio MCP transport (local-validation/complex-native-final.xml). These are distinct evidence sets, not a claimed single combined full-suite run. All native evidence remains on ChemDraw 23.0.1.11 on this Mac.

Experimental complex-draw / chemdraw_draw_complex is reachable through CLI and MCP, taking explicit atom/H/formal-charge records, donor-to-metal dative bonds and supplied CDXML-point XYZ positions. It creates a private native copy without cleanup or inferred geometry and verifies saved records and coordinates. The five-atom copper/ammine fixture retains positive and negative nonzero Z metadata. A real initial failure showed that plain chemically interpreted Cu2+ text became a nested two-copper fragment; explicit superscript charge text fixes the writer, while the validator still rejects nested fragments. This is record preservation and a 2D projection, not a 3D renderer or chemical plausibility certificate. Native image review passed; recipe and limitations are in examples/coordination-explicit.json and docs/METAL_COMPLEXES.md.

Package metadata is now 0.10.0rc2. Offline wheel/source builds passed. The rc2 wheel was installed with uvx from /tmp, outside the checkout, and both first-run and complex-draw completed native checks successfully. Evidence: local-validation/rc2-installed-first-run/first-run.json and local-validation/rc2-installed-complex/audit.json. Both final private drawings remain open. Wheel inspection confirms 43 files including welcome assets, crossing and complex modules and licence notices. The source archive includes the explicit complex recipe and another-Mac checklist, excluding local validation, environments and proprietary references. A fresh server reports 39 tools. The final handoff includes SHA-256 checksums beside the archives. docs/ANOTHER_MAC_TEST.md provides tomorrow's independent-Mac checklist. No package publication, stable-release certification or Git push is part of this local handoff.

## 2026-09-15: v0.9.2 one-command native first run

Glenn approved a one-command onboarding workflow with a small molecular terminal animation and asked whether the same workflows work from desktop assistant apps. `first-run` and new MCP `chemdraw_first_run` now share one implementation: dependency discovery, native connection, explicit caffeine/aspirin drawing through cleanup and grid validation, required artifact checks and a retained `first-run.json` report. Default output is uniquely named. The final drawing stays open; pre-existing documents are preserved. Fresh server discovery reports 38 tools.

Interactive CLI uses a six-position ASCII ring with truthful stage labels and opens the local review on success. JSON/nonterminal output remains machine-readable, with no browser or escape sequences. MCP has neither presentation behavior. Missing dependencies, existing destinations, busy/uncertain operations, partial exports, interruption and browser-launch failures have regression coverage. Ctrl-C initially lost the native stage/output path; the failing regression now passes. There are no automatic write retries, extra uncertainty cleanup, permission changes or client-configuration edits.

Verification: full locked portable suite passed 733 tests with 35 native skips in 6.43 s, recorded in local-validation/first-run-portable-final.xml. Targeted serial native suite passed 5 tests in 117.38 s, recorded in local-validation/first-run-native.xml: the new actual stdio first-run plus four existing draw cases. The test closes only its own final copy and checks the original document inventory. This is not a repeat of the earlier full 34-test native acceptance.

The 0.9.2 wheel and source archive built offline. The installed wheel was exercised through uvx from outside the checkout, including interactive ring animation, successful browser launch and native output at local-validation/first-run-cli-v092/review.html. Its white-background native preview was visually inspected: readable structures, aligned captions/IDs and no apparent label overlap. The original transparent exports remain unchanged. Checks passed on ChemDraw 23.0.1.11 with Python 3.13.2; this remains same-Mac evidence. Wheel contents retain the native module and all AGPL/upstream notices, excluding local validation bundles.

README and docs/FIRST_RUN.md provide the Git-source uvx command and locked-checkout alternative. docs/MCP_CLIENTS.md documents Claude Desktop JSON and Codex local configuration, native-job timeout considerations and the local-versus-web boundary using official client documentation. Client settings were not changed. A native doctor call through the current connected assistant session also responded successfully. Another-Mac acceptance, crowded-charge refinement, metal complexes, desktop-extension packaging and package publication remain separate work.

After publishing implementation commit d08c1c4, the exact README Git-source uvx command was run from /tmp with JSON/no-open flags and a new output directory. uv fetched that public commit, built and installed an isolated tool environment, and completed the actual native drawing with all four returned checks true and exit 0. Retained evidence: local-validation/first-run-github-v092/first-run.json and review.html. This verifies the public-source invocation on the same Mac, not another machine or a published package index release.

## 2026-09-15: open-source licensing and collaboration

Glenn requested making the project open source after discussing permissive and copyleft options. Original project code is now licensed under GNU AGPL version 3 only (AGPL-3.0-only), preserving the stated preference for access to covered improvements while allowing commercial use. LICENSE is the unchanged official GNU text, verified byte-for-byte; NOTICE declares project copyright and warranty terms. Existing upstream MIT notices remain unchanged. No restriction on ordinary user drawings or research, no promise that all independent paid clients are covered, and no contributor copyright assignment were added.

README and CONTRIBUTING invite compatibility reports, reproducible drawing examples and focused pull requests. Current status, agent guidance, provenance and release checklist distinguish open-source availability from a tested stable release. Historical milestone entries retain their then-current licence status.

Packaging regression tests failed for missing licence metadata/text before the change and now pass. Full portable suite: 716 passed, 34 native tests skipped in 6.43 s. The locked dependency check and offline wheel/source builds passed. The wheel declares License-Expression AGPL-3.0-only and includes LICENSE, NOTICE, THIRD_PARTY_NOTICES.md and the upstream MIT text; the source archive includes the same notices and excludes local validation/environment files. Drawing behavior was not changed, so native tests were not rerun for this licence-only increment. Package publication, another-Mac acceptance and the onboarding/charge/metal-complex work remain separate.

## 2026-09-15: v0.9.1 coordination, charge ownership and readable previews

GitHub examples now use opaque white-background SVG copies. The original transparent exports and their native drawing elements are unchanged. This fix was published in commit a9809f8, with a regeneration script and structural regression test.

Native CLI and MCP workflows now share a per-user, cross-process gate with a bounded two-second wait. Nested workflows are reentrant; create/import/close and file wrappers hold the gate across their complete transactions. Busy contention is reported separately from uncertain native outcomes. The protocol does not coordinate manual GUI changes, other automation or separate Macs. Process exit releases the lock, but does not prove an already dispatched AppleEvent completed. See docs/NATIVE_COORDINATION.md.

The earlier circled-charge failure was a genuine native reassignment from nitrogen to a nearby carbon. Candidate positions now require the intended atom to be uniquely nearest, in addition to existing clearance checks; final native chemistry and ownership remain checked. The original four charged structures pass in plain mode. Opt-in circled mode passes for glycine zwitterion and benzoate, with three uniform native symbols. Crowded tetramethylammonium and nitrobenzene remain refused in circled mode at the current house style. No validator was weakened, charge silently changed, or molecule distorted to force acceptance.

Final portable acceptance: 713 passed, 34 native tests skipped in 6.32 s, recorded in local-validation/portable-v091-final.xml. Full serial native acceptance: 34 passed in 441.91 s, recorded in local-validation/native-coordination-v2.xml, with retained artifacts under local-validation/native-coordination-v2/. Interrupted runs are not counted as passes. Native tests and the CLI demo preserved pre-existing documents.

The actual CLI draw command with examples/ions-circled.json produced local-validation/ions-circled-v091/review.html and charged/figure.cdxml, SVG and PNG. Its final working copy remains open. The white-background preview was visually inspected: three matching circled charges are clear of atoms, bonds and captions, although the negative charges sit low beside the caption row and remain a visual-refinement opportunity. All saved chemistry, coordinate, symbol and page checks passed. Doctor reports ready with ChemDraw 23.0.1.11 and the shared gate.

Package metadata is 0.9.1. The dependency lock validates and wheel/source builds succeed locally; validation bundles and proprietary references remain excluded. Public source hosting is approved; package publication, original-code licensing and independent-Mac acceptance remain separate gates. Marco DeCorti's acknowledgment is retained.

## 2026-09-15: public experimental repository

Glenn explicitly approved making the repository public. GitHub visibility was changed and verified PUBLIC. Reviewed the sole existing commit's file inventory and scanned tracked text for credential patterns; no matches were found. Local validation outputs, environments, builds, proprietary templates and reference PDFs remain excluded. Marco DeCorti's acknowledgment is retained. Documentation now distinguishes public experimental source from a stable release and from an open-source licence grant. No code or test behavior changed in this publication step; the documented unfinished-work status remains current.

## 2026-09-15: private repository and contributor acknowledgment

Glenn approved private GitHub hosting. Repository: https://github.com/glebo309/chemdraw-mcp-macos, verified PRIVATE before the initial push. Marco DeCorti is acknowledged in the README for visual guidance, reference examples and checking generated drawings. No collaborators were invited, public release made or original-code licence granted.

The initial source snapshot deliberately retains current unfinished test-first work. Latest portable run: 683 passed, 32 skipped, 11 failed in 6.05 seconds, all failures in the new coordination tests. The experimental one-call circled-charge native demo stopped at chemistry validation and is not accepted. See docs/DEVELOPMENT_STATUS.md for the exact boundary and next steps. Local validation artifacts, environments, distributions and proprietary references remain excluded.

## 2026-09-15: local v0.9 complete jobs, ownership and portable styles

All four approved increments are exposed through the CLI and MCP, with 37 registered tools in a fresh server connection. The implementation follows test-first development; native clients run serially and preserve existing documents. Local package metadata is 0.9.0. Public release, licence selection and independent-Mac acceptance remain separate pending gates.

- Complete scope jobs combine an explicit mapped parent, candidate acceptance, deterministic category assignment with retained secondary memberships, native cleanup, conserved scaffold alignment, actual group bands, headings, optional frame/dividers and final exports. The full acetophenone example contains 14 candidates in 3/6/5-compound bands, with null yields. Native creation and white-background visual review passed.
- Expanded reactions accept explicit water/hydroxide/halide/Na+/K+ participants and bounded charge-balanced salts, positive supplied coefficients and up to three explicit rows on one physical page. Salt components retain ownership. Na/K use the narrowly checked native CDXML ion seed instead of deleting MOL-import AbnormalValence metadata. Native asymmetric arrow bounds and cross-row caption assignment produced retained regressions. A 120 pt row separation passed the unchanged native role/condition verifier; it is now the default, not a universal arbitrary-layout guarantee.
- Snapshot-bound ownership sidecars move explicit captions, native symbols and internal curves with their molecules. Horizontal reaction movement passed natively. Vertical movement within a reaction scheme fails preflight because an actual native test lost explicit reactant roles. A plain molecular sheet passed both-axis movement through MCP. One-sided cross-owner curve moves and native manual-drag attachment remain unsupported. Route suggestions evaluate 24 bounded cubic candidates against conservative measured obstacles and require explicit selection. Both charge-source attack and bond-source leaving arrows passed native rendering; arrowhead ink still requires visual review.
- Portable lab styles are numerical JSON packages, not the legacy draft skill or an alternate renderer. They contain supported settings, a version, hash and reference records, reject conflicting recipe overrides, check fonts on the rendering Mac and retain the exact package with successful native output. The native MCP style/drawing/ownership chain passed. No proprietary template, font or application resource is included.

Portable acceptance: 676 passed, 32 native tests skipped in 6.52 s, recorded in local-validation/portable-v09-release-candidate.xml. The full serial native gate passed 32 tests in 394.64 s, recorded in local-validation/native-v09-electron-final.xml. That process loaded the reaction-series module before the final coefficient-font correction, so the fresh-process typography regression is recorded separately below. Known issues and scope-specific limitations are retained in docs/KNOWN_ISSUES.md, docs/SCOPE_JOB.md, docs/REACTION_EXPANDED.md, docs/OWNERSHIP.md and docs/LAB_STYLE.md. Demo, release checklist and report template are prepared without publication.

Glenn caught a stale SN2 test fixture drawing from the Br label. New annotation and route APIs now reject atom-label sources. Explicit displayed negative-charge/lone-pair sources represent two electrons; graphical electron dots represent one; donating bonds remain supported sources. Atom/bond targets are unchanged. Neutral-donor tests add explicit lone pairs, and fishhook rendering fixtures use bond sources. Corrected native CLI bundle local-validation/sn2-sources-v09 was visually inspected at 3200 px and preserves the source. The final working copy remains open. The local review hub is local-validation/v0.9-review.html.

Independent inspection also found coefficients at 8.25 pt beside 14 pt atom labels: the general style pass had overwritten them with caption typography. Explicitly owned coefficient text is now restored to the atom family/size before native measurement, with regression coverage and native verification of both font and size. No global caption style was changed.

The fresh-process expanded-reaction regression passed in 30.28 s, recorded in local-validation/native-v09-coefficient-final.xml. All four saved coefficients are explicitly 14 pt Helvetica Neue, and coefficient_font_and_size is verified true. The native PNG was visually inspected. This output supersedes the smaller-coefficient previews retained in the earlier full-run directories; the review hub links the corrected version.

The 0.9.0 wheel and source distribution build successfully. Archive inspection confirms the five new workflow modules and portable style example are included, while local validation artifacts, the environment and proprietary CDS files are excluded. The dependency lock validates and a fresh server registers 37 tools. No publishing, original-code licence grant or Synology installation occurred.

## 2026-09-15: local v0.8 styles, reactions, symbols and scope finishing

Version 0.8.0 exposes twenty-seven MCP tools, with the same workflow implementation callable from the terminal. The five approved increments are implemented: numerical CDS/CDX/CDXML style import, explicit atom-owned charge/electron annotations, explicit reaction rows, opt-in PubChem name/CAS candidates, and mapped substitutions on supported pre-substituted/heteroaromatic parents. Glenn's additional scope-frame request is also implemented.

- The original Sharpless CDS was read without modification. Actual settings include 18 pt bonds, approximately 1.58 pt strokes, 14 pt Helvetica Neue atom labels and captions. The supported saved settings/font families are checked separately from molecular identity. The five-candidate pyridine scope at local-validation/pyridine-sharpless-v2 passed native checks and visual review. Template/font files are not redistributed.
- Explicit reaction construction accepts supported supplied participants and above/below conditions, not inferred products or conditions. The native Sharpless example at local-validation/reaction-sharpless-v1 passed role, graph/stereo, caption, gap, scale and page checks. It is an illustrative ethanol/ethanal layout, not a specified experimental oxidation protocol.
- PubChem is opt-in per call, returns candidates with provenance and ambiguity, and does not silently select a match. An actual caffeine lookup returned CID 2519 and the expected checked graph. Public query only; no research compounds were transmitted. Mapped aromatic proposals remain offline, with no yields or reactivity predictions.
- Native CirclePlus/Minus and LonePair geometry was calibrated against actual SVG. Graphical electron dots use a native filled-circle Oval because nearby Electron symbols can change Radical state. Charge signs derive from existing formal charge, never a guessed display glyph. Five native MCP fixtures cover positive/negative creation and charge/lone-pair/electron-source arrows. The corrected SN2 example starts at the circled charge and C-I bond midpoint; bundle local-validation/sn2-symbol-source-v1.
- Optional decorate-scope and chemdraw_decorate_scope add native rounded shadow frames, true dotted separators and optional explicit headings to existing nonoverlapping bands. Source positions and labels are retained. No automatic donating/withdrawing classification or group reordering. The complete fourteen-candidate example is local-validation/scope-framed-v2/review.html, with native CDXML/SVG and transparent PNG. Native SVG and corrected PNG were visually inspected. Reproducible source/recipe are examples/scope-decoration-input.cdxml and examples/scope-decoration-recipe.json.
- Independent review fixed export ordering, uncertain cleanup, actual caption bearings, inherited local width/colour and native font/number serialization. Native typography equivalences are narrow and evidence-backed, not broad font-substitution permission. Final symbol/annotation/decoration CDXML is exported after raster/vector rendering so render-time mutation cannot evade verification.
- The shadow example exposed a sips SVG rasterization bug: the native SVG clip hole rendered correctly in a browser and native PDF, while sips made the whole interior grey. PNG now uses pinned offline resvg-py 0.5.0 on the unchanged native SVG, in a timed worker with bounded local-only resources and checked RGBA dimensions. An actual pixel regression checks transparent interior and partially transparent shadow. No ChemDraw geometry was changed to conceal the conversion bug.

Portable acceptance: 558 passed, 26 native tests skipped in 3.68 s. The complete post-rasterizer native gate passed all 26 tests in 248.61 s, including frame-only and named-heading cases plus positive/negative charges and source arrows. Native clients ran serially and preserved pre-existing document state. Artifacts are retained in local-validation/native-v08-final and the stable summary in local-validation/validation-v0.8.0.json. The visually checked framed PNG is 2172 by 3200 RGBA, with sampled interior alpha zero. Supported native evidence is limited to this development Mac and ChemDraw 23.0.1.11.

The 0.8.0 wheel and source distribution build successfully; packaged modules include styles, resolver, reaction, symbols, scope decoration, raster worker, native AppleScript and retained adapted-source licence. Source examples are included; local-validation, private book/template files and the virtual environment are excluded. Runtime rasterizer attribution is in THIRD_PARTY_NOTICES.md and upstream-sources.json. No public release, remote, new original-code licence or shared-skill installation.

## 2026-09-15: explicit native electron-flow annotations

Version 0.6.0 adds inspect-annotations/annotate and two corresponding MCP tools, for seventeen tools at this milestone. Native full heads and both fishhook directions use explicit atom/bond endpoint offsets and cubic controls. Supported existing circled charges and molecular graphs are retained. No new electron dots, radical-state editing, automatic routing or native moving-attachment claim.

- The first native save-cycle failed because pretty-print whitespace outside text runs was treated as label content. Formatting-only whitespace is now excluded, with actual text-run content preserved.
- Reviewer regressions cover unsupported charge styles, nonfinite/negative dimensions, changed curve geometry and source mutation. Additional main-agent regressions cover changed charge backgrounds and source deletion during export.
- Full native annotation milestone: 13 tests passed in 88.08 s, including all previous workflows plus full/left-half/right-half curve saves. Half-head variants are rendering fixtures, not proposed SN2 chemistry.
- Actual CLI bundle: local-validation/sn2-annotations-v1/review.html. Native PNG was visually inspected on white; its two curves reproduce Glenn's approved reference. Original reference folder was not modified.
- Version 0.6.0 wheel and source distribution built locally before the subsequent input/scope expansion. Latest combined counts belong to the later milestone below.

## 2026-09-15: native input, standard scopes and alignment

Glenn authorized continued local development while unavailable, including subagent implementation/review, without confirmations. Publication, external services, licence changes and modification of pre-existing user drawings remain out of scope.

Version 0.7.0 exposes twenty MCP tools. Offline identifiers, a bounded standard aromatic scope proposer and explicit-input native drawing are callable through CLI/MCP. The proposer preserves an explicit monosubstituted benzene parent handle and produces fourteen unique electronic/positional/steric/reference candidates with relative labels and blank yields. It is not reaction prediction. Image interpretation remains in the image-capable client, with no recognizer project or dependency added.

- Identifier inspection accepts strict SMILES or canonical Standard InChI, retains explicit H/isotopes/stereo, and reports InChI normalization and graph-roundtrip equivalence separately. No name/CAS resolver or network provider.
- New drawings take explicit IDs, labels and SMILES. RDKit supplies a checked MOL coordinate seed; actual ChemDraw imports, runs native Clean Up Structure, saves, measures and renders. Source labels are caller supplied, not verified chemical names. All native work uses private copies.
- Optional explicit common-scaffold alignment rotates/translates normalized candidates to the first native structure without reflection or scaling. Chemistry, stereo, pairwise distances and fit RMSD are checked, then native saving remeasures labels. Symmetric matches are deterministic drawing choices, not inferred correspondence outside the supplied scaffold.
- Live integration caught incorrect MOL chiral-flag semantics, fake physical-page assumptions, overlapping initial assembly and unstable coordinate sorting after native rounding. All have regression coverage and are documented in KNOWN_ISSUES.md. The final matcher keeps its original 0.03 pt tolerance and ordered reaction-arrow endpoints.
- Batch now supports the bounded native annotation subset, including full and both fishhook heads plus supported existing circled charges. Three head variants exported through all five native/vector/raster formats in the dedicated native test. New symbol creation and arbitrary graphics remain unsupported.
- File-grid input is frozen before import and checked after final export, with its exact source snapshot/hash and uncertain-operation recovery recorded in the audit. No retry or automatic close follows an uncertain native outcome.
- Portable tests: 298 passed, 17 opt-in native tests skipped in 1.62 s. Full native suite: 17 passed in 154.12 s. It covers the bridge, polish, analogue edits, scope and frozen file-grid import, batch, full/left/right electron arrows, explicit new drawings including isotope/stereo and scaffold alignment, and all-format annotated batch export. Native clients ran serially and pre-existing document state was preserved. Run artifacts are under pytest-166 in the local pytest temporary directory; the stable validation summary is local-validation/validation-v0.7.0.json.

The three-column fourteen-candidate manifest is examples/acetophenone-scope-draw.json. Its graph set exactly matches the offline acetophenone proposal. The alignment-enabled final bundle is local-validation/standard-scope-v3/review.html, with native editable CDXML, SVG and transparent PNG under figure/. Its white-background review preview was visually inspected. All measured median bond lengths are 18.0000 through 18.0014 pt, largest normalized scaffold fit RMSD is 0.0026354 pt, and the previously tilted ortho-methyl candidate rotates 30.0003747 degrees. Labels and IDs align; no yields are supplied. assets/standard-scope.svg is the matching native export for the README. Earlier evidence was not overwritten.

Version 0.7.0 wheel and source distribution built successfully. The wheel includes the alignment/input/annotation modules, native AppleScript and upstream licence notice; the source distribution includes reproducible examples and the SVG, excluding local-validation and the development environment. Twenty MCP tools and the actual identify/propose-scope CLI paths were checked. User originals and the approved SN2 reference remain untouched. No publication, external name provider or original-code licence grant.

## 2026-09-15: batch export and existing electron-arrow reference

Version 0.5.0 adds CLI batch and MCP chemdraw_batch_export, bringing the server to fifteen tools. An explicit manifest of supported CDXML files produces consistently keyed CDXML/SVG/PNG plus requested PDF/CDX, source/post-export snapshots, per-item audits and an HTML contact sheet. No styling or layout transformation runs.

- Native access is sequential. Each item uses a private working copy, closed with a backup after a determinate result. Native exceptions stop subsequent items, retain uncertainty and never trigger a retry or a second close.
- Missing and unsupported inputs are preflight rejections, so valid siblings can still export. A partial or interrupted batch exits nonzero through the CLI. Failed artifacts remain diagnostic.
- Source bytes are frozen and hashed before native import. Mapped chemistry/stereo/coordinates, captions, supplied arrow properties and explicit reaction-scheme references are checked. Source hashes and unchanged working content are checked after export. Pre-existing open-document inventory, metadata and unsaved XML content are compared; those backups stay in the bridge workspace, not the contact sheet.
- Independent review produced five failing regressions: dropped scheme metadata, changed arrowhead size, leaked extra documents, changed unsaved source content and source-key backup collision. All five are fixed. Backup files now live in an item's snapshots subdirectory.
- Native validation initially failed because isolated fragments lost document settings. The fix follows the existing scope helper: retain the root/page settings while removing unrelated page children. Native scheme inference when none was supplied is documented separately from preserving explicit source roles.
- Final portable suite: 123 passed, 10 opt-in native tests skipped. Full native suite: 10 passed in 66.87 s, including two valid batch inputs, a rejected missing input and all five output formats. Pre-existing document state was preserved.
- Actual CLI demo: local-validation/batch-v1/review.html. Three previously generated figures each exported as CDXML, SVG, PNG, PDF and CDX. All checks passed. The HTML contact sheet was rendered in an isolated headless browser and visually inspected; screenshot retained as contact-sheet-preview.png. The example scope percentages remain invented software-test values, not research results.
- Version 0.5.0 wheel and source distribution built locally. No publication, remote, external resolver or original-code licence grant.

Glenn supplied /Users/glenn/Downloads/SN2_house_style as the desired mechanism reference. The actual preview, CDXML/native CDXML, recipe, audit and original generator at /Users/glenn/ChemDraw-Output/horgh1-v9/sn2_example.py were inspected. It already writes two native editable curved electron-pair arrows, without GUI mouse automation. Next mechanism work should reuse that proven curve planning with the new explicit-document bridge, not the legacy front-document exporter. The source/target association and clearance checks are not yet a generalized tool. Research and evidence are recorded in docs/ELECTRON_ANNOTATION_RESEARCH.md. Native lone-pair/radical symbols and fishhooks are format-supported; project-specific attachment/fishhook save-cycle tests remain future work. The reference folder was not modified.

High-level batch currently rejects curves and molecular symbol graphics, including that legacy SN2 drawing. The lower-level native bridge can import/export them, but batch preservation support must not be claimed before its validator and tests cover them.

## 2026-09-15: native scope grids

Version 0.4.0 adds the CLI grid command and MCP chemdraw_grid_document, bringing the server to fourteen tools. A recipe assigns every source fragment and caption to one explicitly ordered compound, with a compound ID and optional caller-supplied yield. Names are retained, not inferred. Zero and missing yields remain distinct.

- Native measured molecular/name/metadata bounds determine uniform cell dimensions. Captions and metadata share row baselines. Overflow fails instead of shrinking molecules or changing page size.
- Each fragment is normalized to the selected median bond scale, retaining orientation. Multiple fragments assigned to a compound receive one shared layout translation after normalization. This is not a salt-spacing optimizer or common-scaffold alignment engine.
- Exact source/native object coverage, per-atom mapped chemistry/stereo/coordinates, caption anchors and visible horizontal centring, compound/yield binding, inter-object overlaps and saved-page fit are checked. Native ink centring tolerance is 0.75 pt; planned caption anchors and compound centres use 0.05 pt.
- Supported flat single-physical-page molecules and captions only. Reactions, nested groups, page graphics and native molecular symbol graphics fail closed. Plain formal-charge atom attributes are supported.
- Analyze exposes a top-level source token for supported multimolecule drawings. CLI file import validates before native creation and remaps IDs. Working copies and available file/unsaved-content checks preserve the source.
- TDD cycle included independent reviewer regressions for extra native fragments, extra captions and misplaced visible caption bounds. All four failures were fixed; the final review found no blocker within the supported boundary.
- Full portable suite: 104 passed, 9 opt-in native tests skipped in 0.43 s. Full native suite: 9 passed in 61.61 s, including basic scope and disconnected sodium/chloride scope tests. Native clients were run serially and pre-existing document state was preserved.
- Actual eight-compound, four-column CLI demo: local-validation/scope-v1/review.html. Native output was visually inspected. All eight median bond lengths lie from 18.0000 to 18.0014 pt; all audit checks passed. Names and IDs are aligned, with invented test percentages including 0% and a missing yield. These are not experimental data.
- Reproducible fixtures: examples/scope-input.cdxml and examples/scope-recipe.json. Native SVG exports: assets/scope-before.svg and assets/scope-after.svg. Editable CDXML and transparent native-derived PNG are in the local review bundle.
- grid_positions adapted from the pinned Michael Leitch MIT source; upstream-sources.json and THIRD_PARTY_NOTICES.md updated, full notice retained in the built wheel.
- Version 0.4.0 wheel and source distribution built successfully. Package includes scope.py, native.applescript and the upstream licence notice. Usage, compatibility and contribution instructions updated.

Visual review remains required: native bounds and graph preservation do not establish all intramolecular glyph collisions, source chemical correctness, experimental yields or printed-page clipping. No external naming provider, publication, remote or original-code licence grant was added.

## 2026-09-15: explicit analogue editor

User approved the next bounded milestone and requested additional subagent research. The terminal `edit` command and MCP `chemdraw_edit_document` now create an edited native working copy from one molecular fragment with explicitly selected atoms/bonds. Original files and pre-existing documents remain untouched.

- Neutral main-group element/H changes and ordinary nonaromatic bond-order changes. No atom insertion/deletion, new stereochemistry or charged/isotopic target edits.
- `analyze` provides atom/bond IDs plus an export-content token; live edits reject stale snapshots.
- Every page caption needs an explicit replace, retain or remove decision. Changed atom labels are regenerated instead of carrying stale text.
- Chemical diff includes requested changes and observed implicit-H changes. Native roundtrip checks mapped chemistry/stereo, individual atom coordinates and saved label text, rather than only formula or unordered geometry.
- CLI file input validates before native import and remaps atom/bond/caption IDs. The final edited native document remains open; temporary source copies are closed with backups.
- Independent reviewer supplied failing tests for creation/removal of unspecified tetrahedral centres and formula-label corruption. All were fixed under the TDD workflow.
- Final portable suite: 75 passed, 7 opt-in native tests skipped. Six native integration tests passed together in 39.98 s, including four analogue operations and a chiral remote-halogen swap. The seventh native SVG regression then passed in 7.35 s after the fixture correction documented in docs/KNOWN_ISSUES.md.
- Corrected CLI demo: local-validation/bromo-analogue-v2/review.html, visually inspected. The halogen substitution retained all ten atom coordinates with maximum displacement 0.0 pt after native saving. Reproducible inputs are examples/chlorobenzoic-acid.cdxml and examples/bromo-analogue-recipe.json; native SVGs copied to assets/analogue-before.svg and assets/analogue-after.svg.
- New research: docs/NAME_CONVERSION_RESEARCH.md and docs/LAYOUT_WORKFLOW_RESEARCH.md. Strong follow-ons are scope grids, batch export, offline identifiers and strict name resolution. They remain research, not implemented tools or installed providers.

Version increment: 0.3.0, local only. Still no public release, remote or original-code licence grant.

## 2026-09-15: first native figure-polishing increment

The existing native bridge now has a terminal interface and a bounded figure-polishing workflow. Code is in a local Git repository on main; no remote, commit or publication has been created.

### Implemented and exercised

- CLI diagnostics, document listing, semantic analysis and polish commands.
- MCP diagnostics, analysis and polish tools using the same implementation.
- Source CDXML preflight for CLI imports; required optional RDKit validator for polish.
- Actual per-molecule median bond-length normalization, common fonts and strokes.
- Existing orientation retained, including wedges, explicit H and supported isotope/charge attributes.
- Explicit single-row caption and condition ownership, measured native bounds, equal component gaps, shared caption baseline and centred conditions.
- New native working copy, before/after PNG and SVG, editable CDXML, recipe, audit and HTML review.
- Final native graph comparison, molecule-scale measurement, inter-object box overlap checks and source metadata/file/unsaved-content comparison.
- Delayed native open reconciliation through read-only listing, without repeating the write.

### Evidence

- Portable suite: 48 passed, 2 opt-in native tests skipped.
- Native suite: both MCP stdio integration tests passed in 15.31 s with ChemDraw 23.0.1.11 on this Mac. Pre-existing document metadata remained unchanged.
- Native reaction demonstration: local-validation/oxidation-v3/review.html. Before/after SVGs also copied into assets/ for the project documentation. The white-background PNG was visually inspected.
- Demo chemistry: CCO and CC=O retained. Final median bond lengths 18.0013 and 17.9970 pt; caption baselines both 66.74 pt; requested component gap 24 pt. The [O] annotation is schematic, not a specified experimental reagent.
- Additional local normalization checks on the earlier LSD, betaine and HorGH1 CDXML outputs retained the decoded supported molecular identities. These checks are not a claim that arbitrary complex documents are supported.
- Independent review supplied regression cases for unsupported atom/bond queries, polymers, per-fragment identity mapping, explicit H and unsaved source-content changes. They now pass.

### Research and provenance

Eleven upstream repositories are pinned in upstream-sources.json. Box/find_overlaps are adapted from Michael Leitch's MIT-licensed live-chemdraw-mcp, with full notice. No other upstream source is vendored. RDKit is an optional installed dependency. See docs/UPSTREAM_RESEARCH.md for decisions and docs/ROADMAP.md for later work.

### Remaining release gates

- Independent-machine installation and additional ChemDraw versions are not tested.
- Nested groups, multipage layouts, polymer/query features, arbitrary page graphics, automatic scaffold edits and name resolution are not implemented in polish.
- No general charge-collision solver or mechanism-arrow editor in the new server.
- No new GUI, unattended installer or cross-process editing lock.
- Machine checks do not replace visual and chemical review. The server leaves visual_review as required.
- The older local house-style skill remains a draft and is not the release interface.
- Public licence, remote repository and publication require Glenn's approval.
