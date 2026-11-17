# Native commands, dialogs, NMR and document tools

These tools work on any open ChemDraw document, including your own unsaved
drawings. They call ChemDraw's own functions; nothing here reimplements a
ChemDraw feature. All are in the `core` and `full` profiles.

| Tool | What it does | Typical time* |
| --- | --- | --- |
| `chemdraw_list_commands` | Lists ChemDraw's named commands (about 1,600), whether each is enabled for the front document, and whether `run_command` accepts it | 0.2 s |
| `chemdraw_run_command` | Runs one named command on a document and reports object counts before and after, new documents, and any dialog it opened | 0.4 s |
| `chemdraw_dialog` | Lists open ChemDraw dialogs (text, numbered fields, radio buttons, checkboxes, buttons), or fills one and presses a button | 0.3 to 1.5 s |
| `chemdraw_predict_nmr` | ChemNMR 1H or 13C prediction for a structure in a document or a SMILES, parsed into shifts with increments and 1H coupling text | 3 to 4 s |
| `chemdraw_check_structure` | ChemDraw's chemical warnings (valence, unusual bonds, unrecognized labels) for every object, without the Check Structure alert | 0.14 s |
| `chemdraw_document_settings` | Reads or changes bond length, line widths, label and caption fonts and sizes, bond spacing, chain angle and magnification in place | 0.19 s |
| `chemdraw_preview` | Returns a PNG of the document as ChemDraw renders it, so the assistant can look at the result | 0.18 s |
| `chemdraw_document_changes` | Molecules (as SMILES), captions and object counts added or removed since the previous read | 1 s |

\*Median of four runs on Apple Silicon with ChemDraw 26.1 and a small
document. Native calls go through one persistent `osascript` helper that keeps
the script compiled; see [performance](DRAWING_PERFORMANCE.md#native-helper-and-add-in-long-poll).

`chemdraw_list_styles` also lists ChemDraw's bundled journal stationery (ACS
1996, Nature Research, RSC 1 and 2 column, Wiley, Synthesis/Synlett, Adv. Synth.
Catal., Helv. Chim. Acta and others). Pass a stationery path to
`chemdraw_import_style` to get its preset for drawing.

## Examples

> Undo that.

`chemdraw_run_command(document_id, command="undo")`

> Map the reaction atoms and number the compounds in my scheme.

`chemdraw_run_command(..., command="mapReactionAtoms", selection="all")`, then
`command="autoNumberReaction"`.

> Scale the selection to 150 %.

`chemdraw_run_command(..., command="showScaleDialog")` returns
`status: dialog_open` with the dialog's fields and buttons. Then
`chemdraw_dialog(choose="Scale by", fields={"1": "150"}, button="Scale")`.

> Predict the 1H NMR of ethyl acetate.

`chemdraw_predict_nmr(smiles="CCOC(C)=O")` returns 4.12 (CH2), 2.04 (CH3) and
1.26 (CH3) ppm with ChemDraw's increment breakdown. The spectrum stays open in
ChemDraw unless `keep_open=false`; `output_dir` also saves CDXML, SVG and PNG.

## How commands are run

`undo` and `redo` bring ChemDraw to the front first (the reply says
`activated_chemdraw: true`). Measured on ChemDraw 26.1: while another
application is active they are used up without reverting anything. Every other
command runs without activating ChemDraw.

`run_command` brings the target document to the front inside ChemDraw (the
application is not activated), optionally selects everything, and dispatches
the command without waiting for its reply. In the same native call it reads
the document state and counts open dialogs. ChemDraw handles events in order,
so that state follows the command. Only a long-running command needs further
polling, bounded by `wait_seconds`; `still_running` is never treated as
success, and the command is never dispatched twice.

Some commands open a sheet (Scale, Rotate, Object Settings) and return at
once; others open an application-modal alert (Check Structure, a failed
reaction cleanup) that blocks ChemDraw until it is closed. Both are reported
as `dialog_open` with their full contents, and `chemdraw_dialog` answers them.

Refused commands: quit, print, preferences; file commands (open, save, close,
new, file choosers, stationery and sample paths); clipboard commands (copy,
cut, paste and their variants, which would overwrite your clipboard); network
add-ins; `convertNameToStructure` (use `chemdraw_draw_name` with network
consent); NMR and Check Structure (use their dedicated tools). Every refusal
names the alternative. `chemdraw_list_commands` shows the decision for each
command.

## Dialog access and permission

Dialogs are read and answered through macOS Accessibility, limited to the
ChemDraw process: named buttons, numbered text fields, radio buttons and
checkboxes. No keystrokes or mouse movement are sent and no other application
is touched. The app that runs the MCP server (Claude Desktop, Codex, a
terminal) needs Accessibility permission in System Settings > Privacy &
Security > Accessibility. Without it, commands still run, the reply carries
`dialog_check: unavailable`, and an open dialog has to be closed by hand.

## Limits

- Commands act on ChemDraw's current selection. `selection="all"` selects
  every object first, which changes your visible selection.
- `chemical_preservation_verified` is always false for a raw command; read
  the document or look at a preview afterwards. `undo` reverts a command.
- Document settings affect what is drawn or cleaned next, not existing
  geometry, and ChemDraw does not record them in its undo history.
- NMR values are ChemDraw estimates, not measured data. ChemDraw editions
  without ChemNMR report the command as unknown.
- `document_changes` names molecules by SMILES from a lenient read when the
  strict graph check rejects a fragment; that SMILES describes the change and
  is not an identity certificate.
