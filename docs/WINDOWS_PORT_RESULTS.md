# Windows port results

Status: PORT COMPLETE FOR THE SHARED ENGINE ON ONE MACHINE, WITH DOCUMENTED GAPS. Not independently accepted.
All runs were on the development laptop (one Windows account). Mac regression acceptance has NOT been run and is required before any merge.

## Source and environment

- Baseline: kit archive `chemdraw-mcp-dev-20260927-8757786-working.tar.gz`, SHA-256 `da7af5cc6420842fdb4b0340119880740bd76a8d41cc8a0c1348035be0a92897` (base commit 87577861, includes the working-tree changes in source/SNAPSHOT.json). No Git history was used; a pristine extraction was kept for the diff.
- Windows changes: attached patch `changes.patch` (160 files, about 10.0k lines; `diff -ruN` of pristine vs working tree, apply with `patch -p2` from the source root). No branch, no commits, nothing pushed or merged.
- Windows build: Windows 11 Home 10.0.26300 (26H2), x64.
- ChemDraw: Professional 26.1.0.6327, x64 (Revvity), reached through its COM automation server `ChemDraw_x64.Application` (running instance via the Running Object Table; the server never launches ChemDraw).
- Python 3.13.12 (python.org), RDKit 2026.3.6, resvg-py 0.5.0, pywin32 312, mcp 1.30.0, pytest 9.1.1, pytest-asyncio 1.4.0, PyInstaller 6.22.3 (build only), Pillow 12.3.0 (build and tests only; not in the runtime).
- Phase 1 report: `reports/2026-10-06-marco-01/` (8/8 checks passed, validator exit 0).
- Display scaling on the test machine was 200 % (192 DPI); this matters for the SVG unit finding below.

## Native operation mapping

Interface: ChemDraw COM type library (inventory: `evidence/typelib_members.txt`, 2006 members). All COM calls run on one dedicated worker thread with a timeout; a timed-out call poisons the worker and is never retried. Document IDs are deterministic 31-bit values from sha256(process id + document key) because COM exposes no numeric ID; they are checked against the Mac guard (no rounding).

| Existing operation | Actual Windows interface/member | Status | Evidence |
| --- | --- | --- | --- |
| active_document | `Application.ActiveDocument` mapped to the deterministic ID | supported | test_windows_native.py; test_live (8 live) |
| active_document_state | active document row (Name, Path/FullName, Objects.Count); re-checks that the active document did not change during the read | supported (`Modified` flag unreliable, see blockers) | test_live, test_addin_live |
| addin_available / addin_open | not used; the desktop add-in transport is replaced by a COM read/append channel (`channel_read`, `channel_append`, `read_document`) with the same guards (source token, exact positions, graph check after insertion) | supported by replacement | test_addin_live (5 live), real-client check 6 |
| visible_documents | Documents collection minus owned hidden working documents | supported | test_windows_native.py |
| list | `Documents` enumeration with name, file binding, modified, molecule count | supported | all live modules |
| open | `Documents.Open(path)`; visible documents are activated, hidden ones are held unactivated (windowless; released means closed) | supported | scope_table, paged_tables live |
| visibility | show = `Document.Activate()`; hiding an already visible document is not possible and is refused by the existing `ChemDraw did not apply requested window visibility` guard | partly supported | test_windows_native.py |
| live_state | `Document.Selection.Objects` count and bounds | supported | test_live |
| inspect | `Objects.Data("text/xml")` parsed to molecule boxes | supported | targeted, targeted_expanded live |
| export | `Objects.Data(MIME)`: CDXML `text/xml`, CDX `chemical/x-cdx`, SVG `image/svg+xml`; PNG is made offline from the native SVG by resvg. PDF: not offered by Windows ChemDraw | CDXML/CDX/SVG/PNG supported; PDF unsupported (refused before any native call) | test_export_formats.py, paged_tables, real-client check 5 |
| native_action | ChemDraw command objects found through the application menu bar and executed (`Structure > Clean Up Structure`, `Clean Up Reaction`, `Expand Label`, `Contract Label`); align/distribute live in submenus that COM does not expose | 4 commands supported; 8 align/distribute commands unsupported (removed from the Windows tool schema, refused before dispatch) | native_actions live (11, 8 are refusal assertions) |
| convert_name | `Objects.Data` put with `chemical/x-name` (ChemDraw's own name-to-structure), caption removed afterwards | supported | test_native_actions live |
| clean | `Objects.Clean()` (whole document) or per molecule through the same path | supported | native_actions live |
| close | owned hidden documents: release the COM reference; owned visible documents: `Modified=False` then the File > Close menu command (`Document.Close` is a no-op on this build). Callers back up first and only close owned documents | supported | test_windows_native.py, every live module closes its documents |
| (private) clear_owned_scope | Edit > Select All then Edit > Clear on the owned front document with a file-binding check (`Objects.Clear()` drops the file binding and changes the ID) | supported | scope_table live |
| (private) select_document | `Activate()` with an expected-active guard; also valid when no document is active | supported | test_windows_native.py |
| (private) empty_document_style | `Document.Settings` | supported | document_defaults live |

## Changes

All Windows branches are gated on `sys.platform == 'win32'`; the macOS code paths were not edited in behaviour (see Mac regression caveat).

Platform adapter (new): `windows_native.py` (COM worker, operations above), `windows_backend.py` (add-in backend replacement), `native_lock.py` (Windows file lock through `msvcrt.locking`, keeping ownership, re-entrancy and timeout), `private_files.py` (owner/SYSTEM/Administrators DACL helpers), `native_faces.py` (see Verification: text face fitting).

Shared-engine changes needed by Windows ChemDraw behaviour: `core.py`, `batch.py`, `live.py`, `physical_export.py` (PDF capability, SVG unit scale), `raster.py` (face fitting, `@Name` vertical fonts on Windows only), `scope_table.py` (hidden measurement, then one visible final document, because page size cannot change after open), `native_actions.py`/`targeted.py`/`server.py` (capability-driven schema), `styles.py` (Windows font inventory), `addin.py` (exclusive loopback port `SO_EXCLUSIVEADDRUSE`, private credentials), plus explicit UTF-8 file handling across many modules (47 existing source files changed in total).

Installer (new): `windows_install.py` (per-user layout, junction, launchers, PATH, client configs), `windows_setup_gui.py` (Tk, palette from Welcome.swift, braille-dot caffeine animation from `welcome.json`, saved diagnostics), `desktop_setup.py` Windows branches, `scripts/build_windows.py` (PyInstaller onedir, notices, source sdist, checksums, build-path guard), `packaging/windows_setup.py`.

Changed contracts: export formats and native actions are now properties of the platform (`Bridge.export_formats`, `available_actions()`); the MCP schema on Windows does not list PDF-only parameters/align actions as available. `Bridge.same_document_scope_finish` is False on Windows.

Dependencies: no new runtime dependency. pywin32 (COM, ACL, registry) is Windows-only.

Tests added (new files): test_windows_native.py (27), test_windows_install.py, test_windows_setup_gui.py, test_desktop_setup_windows.py, test_native_faces.py (18), test_export_formats.py, test_native_svg_scale.py, test_windows_capabilities.py, test_private_files.py, test_stdio_native_imports.py, test_window_view_state.py, test_windows_build_helpers.py, plus `tests/conftest.py` (pins the simulated-native tests to macOS conventions so they stay platform-independent) and `tests/native_helpers.py`. Tests were written before the production change where a defect was found (red then green), e.g. the build-path guard (2 failed, then 2 passed) and the SVG scale and face-matching tests.

Existing tests adapted (every adaptation commented in place): live tests assume a stale pre-Sep-27 flow in several places (they expect a result document to stay open or a gate result); these were changed to `presentation='background'` or to `checks` instead of gates. Windows-only adaptations: PDF refusal assertions, align refusal assertions, SN2 example symbol positions (see blockers), event sequence in scope_table, visible blank document in document_defaults.

## Verification

| Workflow | Command | Passed / failed / skipped | Native or mocked | Evidence |
| --- | --- | --- | --- | --- |
| Full unit suite | `pytest -q tests` | 1415 passed / 0 failed / 126 skipped (about 5 min) | mocked and simulated native | skip reasons below |
| Connection and identity | test_live.py | 8 / 0 / 0 | native | |
| Add-in replacement channel | test_addin_live.py | 5 / 0 / 0 | native | |
| Read, append, tables | test_draw_live 4, test_batch_live 1, test_scope_live 3, test_scope_table_live 4, test_paged_tables_live 1 | all pass | native | evidence/draw_live, paged_tables |
| Reactions and paper | test_reaction_batch_live 4, test_v08_live 2, test_v09_live | 6 / 0 / 0 and 4 / 2 / 0 | native | v09 failures: Blockers 4 and 5 |
| Scale and export | test_physical_export (unit), paged_tables, drawing_speed_live 1 | pass | native | timing/drawing_benchmark.json |
| Charges and arrows | test_symbols_live 5, test_annotations_live 3, test_batch_annotations_live 1, test_crowded_charges_live 1, test_complexes_live 4, test_cages_live 1, test_scope_decoration_live 2 | all pass | native | evidence/annotations, cages |
| Targeted editing | test_targeted_live 3, test_targeted_expanded_live 6 | all pass | native | |
| Native actions | test_native_actions_live | 11 passed (8 of them assert the align/distribute refusal) | native | |
| Harness and defaults | test_harness_native 3 (+1 skipped, needs a pre-existing untitled document), test_document_defaults_live 1 | pass | native | |
| Client access | real MCP stdio session against the INSTALLED runtime (tools: 53) and `chemdraw-mac doctor` | pass | native | install_update_report.json |
| Setup and upgrades | test_windows_install, test_desktop_setup_windows, test_windows_setup_gui, test_client_install (unit) plus install_test (21 checks) and setup_flow_test (9 checks) | pass | real install into a sandbox profile | install_update_report.json, setup_flow_report.json |
| Concurrency | test_native_lock.py | pass | mocked (lock), no dispatch when contended | |
| Real-client checks (CURRENT_SOURCE.md 1-6) | real_client_checks.py (MCP Python SDK against the installed runtime) | 19 checks passed | native | real_client_report.json |

Live total on the final tree: 78 passed, 2 failed (v09), 1 skipped across 24 modules, run serially, one native client.

Skip reasons (126, none blanket; list in `suite_skips.txt`): 97 are opt-in tests that need a licensed running ChemDraw, the add-in, or a built artifact. The licensed-ChemDraw ones are exercised by the live modules above (78 passed). Not run: 1 needing two released runtimes, 1 needing a built MCPB, 2 needing the Swift compiler, and 8 in test_desktop_bundle.py (see Blocker 13). 27 are macOS/POSIX-only (AppleScript, pty, zsh, app-bundle staging, POSIX permission bits); 2 are `install.sh` (forbidden on Windows by the kit); 2 need Developer Mode for symlinks; 1 is the Windows checkout connection that is NOT implemented (Blocker 3). Each skip carries its reason in the test.

## Native artifacts and visual observations

Artifacts in `evidence/` (checksums in SHA256SUMS): editable CDXML, native SVG and PNG from draw_live, annotations, cages, reaction_batch, installed_caffeine; the real-client table in `evidence/real_client/` (white and transparent PNG, SVG, framed preview). Visual review was done by looking at the images, separately from the graph checks:

- Framed batch (original plus 8 analogues, `groups`, `frame=True`): rounded frame with shadow, dotted separator, two group headings, common orientation of all analogues, captions centred under each structure, bonds at one scale, no overlap. One final visible document; one hidden measuring document (maximum temporary windows: 1, never a visible seed window).
- Plain append of the same batch into the existing canvas: no frame (by design, frame needs the grouped route), same orientation, captions aligned.
- Charge and arrow placement: circled charges follow the owner atoms in draw_live/ions_circled; arrowheads reviewed in annotations/figure.png.
- Text: ChemDraw measures regular text with a thinner face than a naive render picks (the per-user Helvetica Neue faces share one family name). The raster step fits faces from ChemDraw's own EMF metrics. Before/after: `evidence/raster_faces/` (before_fix_resvg_roman.png, after_fix_matched_face.png, chemdraw_own_render_x3.png). Residual difference: GDI synthetic bold is not reproduced by resvg, so a few bold labels render regular weight.
- Not visually checked: printed output, PDF (unavailable), a second machine's fonts.

Timing (this machine, native stage and agent-facing call measured by the client, not including model reasoning): offline caffeine draw 1.3 s; 8 analogues into the existing canvas 3.3 s; framed 9-molecule table 4.0 s; chiral alcohol plus tetrapeptide 2.4 s; explicit-target draw 1.2 s; export CDXML 0.03 s, SVG 0.2 s, PNG 0.6 s; installed-runtime caffeine with PNG/SVG/CDXML 4.9-6.4 s. Table of the 10-run benchmark: timing/drawing_benchmark.json (canvas 0.45-0.51 s, preview 0.51-0.64 s, baseline 1.07-1.61 s). One live module (paged_tables) took 828 s once in the final run and 26 s on three later runs; the 828 s was not reproduced and its cause is unknown (no ChemDraw dialog was recorded).

## Source preservation and failure handling

- A snapshot (hash of the CDXML without window geometry) was taken before each live batch and compared after it. The final comparison: pre-existing documents unchanged, zero extra documents open. At the last two snapshots ChemDraw had no open document at all.
- The tools only close documents they created (managed set); test-owned untitled documents were closed through the product's own close path with a backup.
- No uncertain native write occurred in the final runs; none was retried. A write with a stale token is rejected before any native call (real-client check 6, nothing written).
- Incident (earlier in the run, fixed): the first adapter started ChemDraw itself. A Claude-style client then terminates everything its server started (job object), which closes ChemDraw. The server now never launches ChemDraw. At that moment no user document was open in that copy; the user's own drawing had been saved and closed before.
- A previously reported "Saved" status was wrong: `Document.Saved/Modified` are unreliable on this build; the adapter does not trust them for ownership or close decisions.
- A non-active explicit target is refused (shared Mac/Windows rule: public writes require the target to be the active document) with nothing written (real-client check 3).
- Leftover: an empty folder `closed-working-copies` remains in the per-user product data folder (could not be removed in this session).

## Installation and update

- Candidate: `builds/0.10.0rc22-win.4/` (zip 75.6 MB, 147 MB extracted). Zip SHA-256 `122ae1dc60256b6167fc49fa25f4891c48a1f1ed999faa18d466bf6ff9de0c01`. Earlier candidates win.1-win.3 are superseded; win.3 leaked the build checkout path in one dist-info record, removed in win.4 by `drop_build_machine_records` plus a build guard.
- Layout per user: `%LOCALAPPDATA%/ChemDraw MCP/versions/<v>/ChemDraw MCP`, a `current` junction, `bin/*.cmd` launchers on the user PATH (once), Claude Desktop and Codex entries calling `current/chemdraw-runtime.exe --desktop-serve`, private settings.
- Clean install: 12 checks passed (versioned copy, junction, launchers, PATH once, client entries with unrelated settings kept, original Codex bytes kept as prefix, backups and configs private, installed CLI `doctor --no-connect`, MCP initialize/list_documents).
- Update win.3 to win.4: 9 checks passed (junction switched, previous version kept, client settings byte-identical, no new backups, PATH unchanged, new runtime current, MCP and a native offline caffeine drawing through the updated runtime, no document left open). 21/21 in `install_update_report.json`.
- Setup window: protocol test (check, live read test, finish, then installed server serving native tools) 9/9 in a sandbox profile; the frozen `ChemDraw MCP Setup.exe` starts, shows the themed window and the animation (`evidence/gui/setup_exe_smoke.png`); screens for every state in `evidence/gui/`. Diagnostics are retained automatically as private files.
- Safe by design: the installer never registers DLLs/OCX, never alters security settings, binds loopback only, and does not bundle ChemDraw, fonts, credentials or an add-in.
- Not tested: a real Claude Desktop or Codex restart picking up the entry (the check used the MCP SDK client against the installed runtime), a second Windows account/machine (the lab PC was not available), code signing or SmartScreen behaviour, an upgrade from a real previous user installation.
- This was ALL on the same laptop and account: it is not independent-machine acceptance.

## Blockers and next action

1. PDF export: Windows ChemDraw offers no PDF data type. Stage: export. Behaviour: ValueError before any native call; render_cdxml reports `unavailable_formats`. Evidence: test_export_formats, paged_tables. Understood.
2. Align/distribute (8 commands): submenu-only, not in COM. Stage: native_action. Refused before dispatch; removed from the Windows schema. Understood. Keyboard/mouse automation is not allowed, so no fallback.
3. Windows checkout connection (the `connect_checkout` equivalent): not implemented; one test skipped with that reason. The installed runtime path is complete.
4. v09 `styled_job`: `chemdraw_run_styled_job` with a custom lab style raises "Direct API batches ... separate explicit workflow" because `production_job(shared_molecules=True)` always routes `auto` to the shared path, which refuses custom styles. Platform independent source inconsistency (not a Windows adapter fault); please check on the Mac with native tests enabled. Understood.
5. v09 `complete_scope_job`: correct refusal "Native grid ink overflow" for 14 compounds. On Windows the page size of an opened document cannot change (COM ignores Width/Height and CDXML insertion does not apply the page), so the document keeps the user's default template page (here 720 x 540). Multi-page scope jobs on a small template page are therefore refused instead of paged. Understood; a new owned document with a larger template would avoid it.
6. Charge on isolated anions: ChemDraw 26.1 drops `Charge` on single-atom ions whose circled symbol sits outside its association zone when a CDXML is imported (examples/sn2-annotation-input.cdxml, made with ChemDraw 23, carries "not associated" warnings). The product refuses safely; tests move only the symbol positions (`native_helpers.importable_sn2`). Recommend regenerating that example. Understood.
7. `Objects.Data` put of a CDXML without `BondLength` rescales bonds to 18 pt; exact-append checks would refuse such input. Understood.
8. `Document.Modified/Saved` unreliable; `Document.Close` is a no-op; an unactivated automation document vanishes on release (hidden working documents rely on this). Handled; documented, not a failure.
9. Text rendering residual: synthetic bold not reproduced in the PNG path; first-time fonts missing on another machine will change widths (not tested).
10. Mac regression: not run. Windows tests do not establish it. Run the full suite and native tests on the Mac before merging.
11. Independent-machine acceptance: not done.
12. v09 and other live tests were run with ChemDraw empty; with a visible document open the auto presentation becomes interactive (final document stays open). Both states were exercised across the runs; the final run had no visible document.
13. `tests/test_desktop_bundle.py` (8 opt-in tests against a frozen runtime) hard-code the macOS .app layout (Info.plist, Library paths, a HOME-only environment). Run against the win.4 runtime: 3 passed, 5 failed on those layout assumptions (for example `Contents/Info.plist` missing; the Windows runtime needs LOCALAPPDATA/USERPROFILE). They were not ported; the equivalent Windows coverage is the sandbox install/update test (21 checks) and the setup-flow test (9 checks), whose scripts are in `commands/`. Platform assumption, understood. Porting them is open work.

Next action: Mac regression and a second-machine install of `builds/0.10.0rc22-win.4/`, then decide on blockers 3-5. Not published, not merged, nothing retagged.


## Addendum, 2026-10-08

- Candidate 0.10.0rc22-win.5 replaces win.4: the setup window's sprite animation no longer freezes when Windows "Animation effects" is off (only CHEMDRAW_MCP_REDUCE_MOTION=1 freezes it). Unit suite on this tree: 1416 passed, 126 skipped, 0 failed. The native install/update (20/20), setup-flow (9/9) and scripted-client (19/19) checks were re-run on win.5 on 2026-10-08 with ChemDraw open and the pre-existing drawing unchanged (same laptop only).
- The win.x zip is not part of this repository. Build it on Windows with `python scripts/build_windows.py <new dir> --version <v> --uv <uv.exe>`.
- Not tested on a second machine; not tested on macOS.
- Candidate 0.10.0rc22-win.6 adds Claude Code (registered through `claude mcp add --scope user`, never retried, existing different entries left alone) and Gemini CLI (`~/.gemini/settings.json`, documented `mcpServers` format, 300 s timeout) to the Windows setup, plus the stdio command for any other MCP client on the done screen. Unit suite 1424 passed, 126 skipped, 0 failed. Sandbox install/update win.5 to win.6 27/27, including the real `claude` CLI registering the entry in a sandboxed config and Claude Code health-checking the installed server as Connected; setup flow 9/9. Gemini CLI was not installed on the test machine: its entry follows the documentation but was not exercised by Gemini itself.

## Addendum, 2026-10-12

- Candidate 0.10.0rc22-win.8 (win.7 was built and installed on the test laptop only, never published).
- Drawing style: the setup lets each user choose a `.cds`/`.cdxml`; only its validated numbers, file name and hash are kept and become the `house` preset. `chemdraw_list_styles` reports whether it is applied.
- Speed: single drawings read COM object IDs through raw IDispatch and walk `doc.Objects` once per insert; on the same page 4.6 s to 2.2 s per drawing.
- Multi-page documents: a template that opens as a poster (observed: 2 x 3 pages, 1440 x 1620 pt) was refused by the shared append. The document is now set to 1 x 1 page through `NumPagesWide`/`NumPagesHigh` when it is empty or all content lies on the first page, re-read and verified unchanged; otherwise refused with steps. macOS gets the steps only. The test helper `new_untitled_document` had set 1 x 1 pages itself, which hid this case; `tests/test_single_page_live.py` uses real multi-page documents.
- Placement check: `rigid_offset` paired points by sorted rounded coordinates, so two captions in one table column (x about 85.345) could swap and a correct insertion was reported as not rigid (observed with eight analogues added to a live parent). Points are now paired by proximity, each supplied point once.
- Verification on the same laptop: unit suite 1460 passed, 0 failed. Native modules: 81 passed, 3 failed. The failures are the two v09 cases above and `test_harness_native`, which refused because an untitled user document was open (`unsaved_user_document`, by design); it was not re-run without that document. Sandbox install of win.7 then update to win.8: 27/27, including an offline caffeine drawing through the updated runtime. Not tested on a second machine; not tested on macOS.
