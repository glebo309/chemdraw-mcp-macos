# Desktop JavaScript API bridge (experimental)

The full MCP profile exposes a direct bridge to the documented desktop
`ChemDrawAPI` JavaScript API. It does not use the clipboard, keyboard nudges,
mouse drawing, or temporary drawing documents for reads and CDXML additions.
`chemdraw_draw` and `chemdraw_draw_structures` now use this backend for plain
molecule batches in auto, interactive and shared modes. Explicit background
jobs retain the older native import/cleanup workflow.

## One-time local installation

1. Call `chemdraw_addin_connect` in the full MCP profile, or run
   `chemdraw-mac addin-connect`.
2. If the response is `needs_setup`, install the returned `.chemdrawaddin` file
   through ChemDraw's Add-ins > Add-in Manager > Add from file.
3. The installed name is **ChemDraw MCP Native API**, distinct from earlier
   development probes. Connect again from the MCP client.

If an installed add-in disappears after restarting ChemDraw, inspect Preferences
> Directories > ChemDraw items location search priority. This list must include
the parent of the Add-ins folder, normally
`~/Library/Application Support/com.revvity.ChemDraw/`. An empty list was reproduced
on the development Mac: the files and enabled preference remained, but no command
loaded. Adding this path and restarting restored automatic discovery without
reinstalling the package. Preserve unsaved work before restarting. A
`addin_command_unavailable` response describes command availability, not proof
that the files are missing.

The generated package is private to this machine: it contains a local access
credential. Do not upload, commit, redistribute or share it. The package is
generated locally from the distributed Python and JavaScript sources.

The bridge binds only to `127.0.0.1` and checks the exact Host and a private
Bearer token. Only absent, `null`, and `file://` origins are accepted. The latter
two accommodate desktop file webviews; arbitrary website origins are refused.
The private port and token survive process restarts. A second owner of the same
installed endpoint is rejected, not silently substituted. One MCP process owns
the connection; sharing this installation between concurrent clients is not yet
supported.

Opening the connection panel brings ChemDraw forward once. Keep the MCP process
and the small modeless add-in panel open. Subsequent reads and additions work
while another application has keyboard focus. The active drawing within ChemDraw
must still match the supplied document ID. Closing the panel disconnects this
transport. This is desktop automation, not a headless ChemDraw engine.

## Read and append

Plain molecule batches use equally spaced row and column centres, with shorter
structures vertically centred rather than top-aligned. Molecular scale and
common-parent orientation remain unchanged. SMILES/InChI inputs without a label
receive compact compound numbers; explicit labels and supplied names are retained.
Captions explicitly set InterpretChemically=no, independently of the document
default, so names/formulas cannot become extra chemical fragments during insertion.
This uses the documented [text-object property](https://iupac.github.io/IUPAC-FAIRSpec/cdx_sdk/Text.htm).
Existing unsupported chemistry is checked before writing. Old captions already
converted into chemical fragments are not silently flattened or certified.

`panel="auto"` chooses a plain shared grid while retaining its verified common
core, rather than planning unsupported decorations and requiring a retry. When
substituent replacement removes part of the live parent's graph, a whole supplied
ring-containing molecule shared by all inputs can instead anchor to that live
parent's coordinates. This conservative automatic rule needs at least four inputs;
it does not guess a maximum common substructure. An explicit `scaffold_smiles` is
available on the advanced drawing tool. With no unique live match, a verified core
uses the first requested structure as reference. The planning report records the
chosen core and reference source. Graph inputs without any verified common core
are not claimed to share an orientation.

`chemdraw_addin_read_document(document_id)` returns the actual current CDXML,
selection CDXML, native document metadata and a `source_token`. It supports an
untitled document, without assigning a filename, saving, exporting through the
legacy bridge, or selecting all objects.

`chemdraw_addin_append_cdxml(document_id, cdxml, expected_source_token)` adds a
supplied CDXML payload directly to the same document. The payload must contain
flat, supported molecules/captions, explicit XY positions and conservative object
bounds, matching document defaults and colour tables, and fit a single page without
overlap. The read snapshot provides the target settings. IDs are remapped before
insertion, and verification independently handles native renumbering. Font tables
may gain entries but cannot redefine existing fonts. New objects carry their own
typography and line widths; existing content is not restyled.

The bridge checks freshness before writing and again inside the synchronous
JavaScript operation. It checks existing chemistry and atom positions, appended
chemistry and positions, page dimensions, native object counts, page fit and file
binding afterwards. Native coordinate rounding uses the existing 0.03 pt
verification tolerance; arbitrary translation is not accepted. Recovery CDXML
snapshots are retained in the normal backup directory. ChemDraw's own autosave
behaviour for named documents remains under the application's control.

Timeouts and post-write verification failures are uncertain outcomes, not success.
Never retry an uncertain write. A stale source token is rejected before insertion.
This is sequential collaboration, not an atomic multi-user editing protocol.
Do not switch the active ChemDraw drawing during a write.

Equivalent CLI entry points use the same implementation:

```sh
chemdraw-mac addin-read DOCUMENT_ID
chemdraw-mac addin-append DOCUMENT_ID --input /absolute/payload.cdxml --source-token TOKEN
```

The CLI opens and closes its connection panel per invocation. A persistent MCP
process reuses one panel for repeated operations. Neither creates another drawing
document for these API operations.

## Native acceptance and boundaries

On the development Mac with ChemDraw 23.0.1 / API 1.6, the real stdio MCP test
passed: read an untitled document, append five structures in one call with Finder
in front, reject a stale token, append a sixth structure, preserve existing
coordinates/page/file binding, and retain the same document inventory except for
the test-owned target. The test closes only that target after success.

```sh
CHEMDRAW_ADDIN_LIVE_TEST=1 .venv/bin/pytest -q -s tests/test_addin_live.py
```

Ordinary drawing also passed a real MCP test with native document opening
disabled: draw a modified fused-ring parent with a deliberately stale Caffeine
caption, read its actual unsaved graph, then add eight analogues in one call.
The same untitled document contained nine structures, preserved the parent,
retained its scaffold orientation and passed native house typography/scale checks.
Finder retained focus for the addition. The exported image was reviewed.
A second batch verified tetrahedral and alkene stereo, isotope labels, formal
charges, aromatic NH and an explicit hydrogen atom through native insertion.

The planner requires RDKit 2026.03.3 or newer with its ChemDraw CDXML writer
compiled in. It tries fitting column counts without shrinking bonds or dropping
structures and refuses a full page before writing. A unique matching live graph
provides orientation; captions never identify that graph. Exports contain the
whole current canvas. SVG export from untitled documents does not assign a
filename; CDXML comes from getCDXML, PNG from native SVG.

Supported here: flat molecules/captions, plain charges and house or ACS presets.
Not migrated: decorated groups, arbitrary graphics, reactions, custom layout and
custom styles. These require an explicitly chosen separate workflow, not silent
downgrading. Arbitrary replacement/deletion and independent-Mac acceptance remain
pending. Initial connection opens one modeless panel, not a drawing document;
this is not a headless engine.

API reference: [Revvity's official desktop add-in documentation](https://github.com/Revvity/ChemDraw-AddIns/tree/master/Documentation).
