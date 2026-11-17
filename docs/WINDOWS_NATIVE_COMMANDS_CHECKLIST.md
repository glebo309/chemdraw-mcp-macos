# Windows check for named commands, dialogs, NMR and document tools

This branch brings eight new tools from the macOS project to the Windows port.
They work and are tested on macOS (ChemDraw 26.1). **The Windows part was
written on a Mac and has never run on Windows.** Nothing in it is trusted until
the checks below pass on a Windows PC with ChemDraw.

You can give this whole file to your coding assistant (Claude Code, Codex,
Gemini CLI) and say: "Work through this checklist on this PC, fix what fails,
and write the results into the table at the end."

## What the new tools do

| Tool | In plain words |
| --- | --- |
| `chemdraw_list_commands` | Lists the menu commands ChemDraw offers, and which ones the assistant may run |
| `chemdraw_run_command` | Runs one menu command (Undo, Redo, Clean Up, Flip, Group, ...) on an open drawing |
| `chemdraw_dialog` | Reads a ChemDraw dialog (its text, boxes and buttons), fills it in and clicks a button |
| `chemdraw_predict_nmr` | ChemDraw's own 1H or 13C NMR prediction, returned as a list of shifts |
| `chemdraw_check_structure` | ChemDraw's warnings (wrong valence and so on) for a drawing |
| `chemdraw_document_settings` | Reads or changes bond length, line width and fonts of a drawing |
| `chemdraw_preview` | A picture of the drawing, so the assistant can see its result |
| `chemdraw_document_changes` | What changed in a drawing since the assistant last looked |

## Which files are Windows-specific

- `chemdraw_macos/windows_commands.py` (new): menu commands, Win32 dialogs, settings.
- `chemdraw_macos/windows_native.py`: new operations at the end of the file
  (`list_commands`, `dispatch_command`, `command_state`, `dialog_count`,
  `get_settings`, `set_settings`). They return the same shapes as the macOS
  script, so the shared code in `commands.py`, `nmr.py`, `settings.py` and the
  others runs unchanged.
- `chemdraw_macos/dialogs.py`: on Windows it calls `windows_commands.py`.
- `tests/test_windows_commands.py` (new).

## How the Windows design works (and where it may be wrong)

1. **Commands are menu items.** COM only exposes top-level menu items, not
   submenus (the same reason alignment is unavailable). The macOS names the
   tools use (`undo`, `cleanStructure`, `predict1H_NMR_Shifts`, ...) are
   mapped to menu captions in `COMMAND_ALIASES`. **Most captions in that table
   are guesses.** Any item can also be named directly as `"Menu > Item"`.
2. **A command runs on its own COM thread.** A command that opens a modal
   dialog does not return until the dialog is closed. If that happened on the
   bridge's worker thread, the worker would time out and refuse everything
   until restart. So `start_command` runs `Execute()` on a separate thread, and
   the worker only checks "finished, dialog open, or still busy".
3. **Dialogs are read with window messages.** `windows_commands.read_dialogs`
   finds visible `#32770` windows of `ChemDraw.exe` and reads their Static,
   Edit and Button controls. Clicking uses `BM_CLICK`, typing uses
   `WM_SETTEXT`. No keyboard or mouse. If ChemDraw draws some dialogs without
   standard controls, they will not be seen.
4. **Settings** use `Document.Settings` (points), converted to the twentieths
   of a point the shared code expects. Magnification is not in COM Settings
   and is reported as unavailable.

## Checklist

Before starting: start ChemDraw yourself and open a **new, empty** drawing
for the tests. Do not test on a drawing you care about.

1. **Unit tests.** `.venv\Scripts\python -m pytest -q tests/test_windows_commands.py tests/test_native_commands.py tests/test_windows_native.py`
   All must pass. The two COM tests at the end of `test_windows_commands.py`
   only run on Windows.
2. **Real menu captions.** Ask the assistant to call
   `chemdraw_list_commands` and save the full list. Compare every entry of
   `COMMAND_ALIASES` with the real captions and fix the table. The aliases that
   matter most: `undo`, `redo`, `cleanStructure`, `predict1H_NMR_Shifts`,
   `predict13C_NMR_Shifts`, `checkStructure`, `showScaleDialog`,
   `flipObjectsHorizontal`, `group`.
3. **Enabled state.** Draw benzene, select nothing, and check whether
   `chemdraw_list_commands(pattern="Clean")` shows Clean Up Structure as
   enabled or disabled; then select the ring and check again. If `Enabled`
   never changes, COM reports a stale menu state and `run_command` must not
   rely on it (it would report `not_enabled` wrongly, or run disabled items).
4. **A simple command.** `chemdraw_run_command(document_id, "flipObjectsHorizontal", selection="all")`
   must return `status: completed` and the ring must flip on screen. Then
   `command="undo"` must flip it back. Check that ChemDraw shows the drawing as
   modified (asterisk in the title); `windows_native.py` notes that
   automation writes do not set Modified.
5. **A dialog that waits for you.** `command="showScaleDialog"` must return
   `status: dialog_open` with the dialog's text, its number field, its radio
   buttons and its buttons. Then `chemdraw_dialog(button="Cancel")` must close
   it, and `remaining_dialogs` must be empty. **Most important check:** after
   that, an ordinary tool such as `chemdraw_list_documents` must still work.
   If it says "A ChemDraw automation call timed out", the worker was blocked
   and design point 2 failed.
6. **Fill a dialog.** Open Scale again, then
   `chemdraw_dialog(choose="Scale by", fields={"1": "150"}, button="OK")`
   (use the real button and radio names from step 5). The ring must grow.
   Undo afterwards.
7. **An alert.** Check Structure opens an alert that blocks ChemDraw until
   OK is clicked. The tools refuse to run it on purpose (there is a better
   tool for it), so start it directly from a terminal in the project folder,
   replacing `ID` with the document_id from `chemdraw_list_documents`:
   `.venv\Scripts\python -c "from chemdraw_macos.core import Bridge; from chemdraw_macos.commands import execute; print(execute(Bridge(), ID, 'checkStructure', 'all', 10))"`
   It must print `'status': 'dialog_open'` with the alert text. Then close the
   alert with `chemdraw_dialog(button="OK")` and check that
   `chemdraw_list_documents` still works.
8. **Structure check.** `chemdraw_check_structure` on the five-bond carbon
   must return a warning such as "too many bonds". If it returns
   `ok: true`, COM's CDXML does not carry ChemDraw's `Warning` attributes and
   this tool needs another source on Windows.
9. **NMR.** `chemdraw_predict_nmr(smiles="CCOC(C)=O", keep_open=false)` must
   return shifts near 4.1, 2.0 and 1.3 ppm. On macOS ChemDraw opens the
   spectrum as a new document; check that the same happens on Windows and that
   the temporary documents are closed afterwards.
10. **Settings.** `chemdraw_document_settings(id)` must show bond length 14.4
    or whatever your drawing uses. Set `{"bond_length_pt": 17}` and check
    ChemDraw's Document Settings dialog shows 17 pt.
11. **Preview and changes.** `chemdraw_preview(id)` must return a picture of
    the drawing. `chemdraw_document_changes(id)` twice, deleting the ring in
    between, must report the ring as removed.
12. **Journal styles.** `chemdraw_list_styles()` must list the `.cds`
    stationery files (ACS, Nature, RSC, Wiley ...). The search looks in
    folders beside `ChemDraw.exe`; if none are found, find where ChemDraw keeps
    them on Windows and fix `styles.stationery_styles`.
13. **Nothing else broke.** Run the whole unit test suite and one ordinary
    drawing ("draw caffeine in my document").

## Results (fill in)

| Step | Pass / fail | Notes or fix made |
| --- | --- | --- |
| 1 Unit tests | | |
| 2 Menu captions | | |
| 3 Enabled state | | |
| 4 Simple command, undo | | |
| 5 Dialog, worker still alive | | |
| 6 Fill a dialog | | |
| 7 Alert | | |
| 8 Structure check | | |
| 9 NMR | | |
| 10 Settings | | |
| 11 Preview, changes | | |
| 12 Journal styles | | |
| 13 Nothing else broke | | |
