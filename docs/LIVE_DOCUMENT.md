# Existing documents and background rendering

The CLI and both MCP profiles expose the same native implementations. These
interfaces do not open a browser or require a preview page.

## Work on the document already open in ChemDraw

```sh
chemdraw-mac documents
chemdraw-mac live-read DOCUMENT_ID
chemdraw-mac live-action DOCUMENT_ID --action align_left --selection current --source-token TOKEN
```

Replace the ID and token with the current returned values. In a connected AI
client, ask it to read the existing document and operate on your current selection.
It calls `chemdraw_read_live_document` then `chemdraw_live_action`, without
importing another copy. Both untitled and named drawings are now read through the
installed desktop API, without assigning a filename, saving, selecting all or
accessing the clipboard. See [one-time add-in setup](DESKTOP_ADDIN.md).

The live action supports the same allowlist as `native-action`: structure/reaction
cleanup, six alignments, two distributions and label expansion/contraction.
The document must be frontmost within ChemDraw. `current` uses the selection you
made in ChemDraw; `all` explicitly selects everything, including captions.
Disabled commands return `unavailable_for_selection` rather than success.

Each read snapshots fresh in-memory CDXML, including unsaved edits. It returns raw
object records, a local snapshot path and a token bound to the document ID, file,
content and selection bounds/counts. With chemistry support, `molecular_graphs`
includes canonical SMILES and explicit atom/bond records. Unsupported graphs are
reported, not replaced by guessed identities. Captions may be stale and do not
identify the molecule. Reads and edits leave that document open. A read is not a subscription:
manual changes become available at the next call, not automatically while the
assistant is idle. There is no continuous watcher in this increment.

Before a live action, another snapshot must match the expected token. The snapshot
is also the recovery backup. No ownership promotion occurs, so a user-opened
document remains ineligible for `close_working_document`. No automatic save to the
original file, rollback, copy replacement or uncertain-write retry occurs.

This is not an atomic human/agent collaboration lock. The cooperative native lock
coordinates our clients, not your mouse. Selection bounds/counts do not identify
every selected object; different selections can share these measurements. Avoid
manual changes during an action. If a native action fails, inspect the actual
document and refresh before deciding whether to try again.

## Hide a window or render unattended

```sh
chemdraw-mac visibility DOCUMENT_ID hide
chemdraw-mac visibility DOCUMENT_ID show
chemdraw-mac render --input /absolute/path/drawing.cdxml --output /absolute/existing/parent/new-output
```

`visibility` changes only the explicitly supplied document window. MCP exposes
`chemdraw_set_visibility(document_id, visible)`.

`render` accepts explicit CDXML and produces `figure.cdxml`, `figure.svg`,
`figure.png`, `figure.pdf` and `result.json`, with no HTML review. Native ChemDraw
exports the editable/vector files; the existing resvg worker rasterizes native
SVG for PNG. There is no cleanup, chemistry invention or chemical-preservation
certificate. This is a low-level rendering path, not an alternative validated
SMILES drawing workflow.

The default hides the newly created document after opening and closes only that
owned document after all exports succeed. `--show` instead leaves it visible and
open. MCP exposes `chemdraw_render_cdxml(cdxml, output_dir, background=True)`.
The output directory must be new, absolute and have an existing parent. Existing
user documents are not hidden or closed. An uncertain failure retains the new
document, which can be found with `documents` and revealed with `visibility`.

Background means a hidden window inside an activated, licensed, logged-in Mac
desktop session. A window may flash briefly during opening. No login-free,
display-free server support is claimed. License or permission dialogs can still
interrupt automation. Other high-level workflows do not automatically gain this
background mode.

## Verified boundary and missing piece

On the development ChemDraw 23.0.1 build, hidden-window cleanup/export and window
restoration worked. The native integration tests exercise same-document cleanup
through core MCP, fresh content after a separate native client changes the drawing,
stale-request rejection, refusal to close the externally owned document, hidden
SVG export, and CLI background CDXML/SVG/PNG/PDF rendering with no leftover window.

The general atom/substituent editor still creates native-rendered copies. It is
not silently used when a same-document edit is requested. The declared selection
content getter and `make new molecule ... with data` probe returned native error
`-10000`; no arbitrary same-document structure replacement is implemented here.
Reading selection counts and bounds works only through direct property references,
not by first coercing the selection into a variable. That distinction has a
regression test. A bounded native clipboard bridge now supports untitled reads
and checked molecule/caption insertion. It is not a general GUI automation tool.

`chemdraw_draw_structures`, like `chemdraw_draw`, reuses a visible working document
in auto mode for supported plain panels. Pass `document_id` with shared mode when
several documents are open. Explicit interactive mode still requests a separate
final document. Retrying the whole drawing to change its captions is not an edit
and would append the molecules again; do not use it as a relabeling operation.

Another-Mac acceptance, continuous change notifications and general in-place
chemical editing remain separate unfinished capabilities.
