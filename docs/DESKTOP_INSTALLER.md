# Graphical ChemDraw MCP setup

## rc10: explicit install route on every preparation screen

The preparation page always offers Save add-in installer to Downloads and the
Add from file instructions. Existing files no longer hide this route or imply
registration. If the entry is listed, enable it instead. The page explains that
the Downloads package can be deleted after setup. Test connection is the next
action. Normal instructions fit without scrolling; expanded help can scroll.
The final page still only finishes and closes setup.

rc10 includes same-document page expansion and physical-scale exports. See
PHYSICAL_EXPORT.md and PROJECT_PROGRESS.md for acceptance and limits. This does
not remove single-owner connection limits or establish another-Mac acceptance.

## rc9: compact themed selection and occupied-connection handling

The selection screen now uses pink checkboxes and the short Codex / ChatGPT
label. App selection and its validated name share one row; the full path is
available on hover. Normal selection and completion have no scroll container.
The window stays 800 by 400 points. Expanded installation help can still scroll.

An occupied add-in endpoint during preparation now returns the same actionable
busy state as diagnostics, rather than raw Errno 48. It does not disconnect other
clients or alter their private connection settings. Single-owner access remains
a limitation, not solved multi-client concurrency.

Portable checks: 1082 passed, 88 skipped. Frozen runtime and extraction checks:
10 passed, one live-read check skipped. Actual selected, prepared and connected
SwiftUI previews were inspected. Fresh desktop-client drawing remains pending.

## One Mac installer, selectable assistants

The main artifact is `ChemDraw-MCP-Apple-Silicon.dmg`. Open the disk image, then
open **ChemDraw MCP**. Select the installed ChemDraw app and choose **Claude
Desktop**, **Codex / ChatGPT**, or both. The supported
Codex local clients share the host's Codex MCP configuration. This does not
configure a web-only ChatGPT session or claim direct MCPB import support in Codex.

The same three-page setup and read-only connection check are retained. Finish
saves the selected local client connections and closes the window. Restart those
assistants afterwards to load their settings. One versioned app is copied to
`~/Library/Application Support/ChemDraw MCP/versions/`; both clients use the same
stable launcher under `ChemDraw MCP/bin/`. No shell profile, Python installation
or repeated package download is needed. Previous app versions are retained.

Only selected clients are configured. Claude uses its desktop JSON settings;
Codex uses `~/.codex/config.toml`. Other servers and preferences are preserved,
Codex comments are retained, and changed files receive private sibling backups.
A conflicting `glecko_chemdraw` entry is refused, not overwritten. Existing
Claude MCPB installations are recognized to avoid adding a duplicate JSON entry.
Upgrade an older Claude bundle before comparing it with this version in Codex.
The installer does not remove old third-party MCP servers or extensions.

`ChemDraw-MCP-Apple-Silicon.mcpb` is the alternative standards-based bundle for
hosts that implement MCPB installation. The helper recognizes that its current
host already registered it; it can optionally connect Codex as well. Other hosts'
MCPB import support must be tested individually. Plain MCP support alone does not
mean a host can install MCPB files.

Advanced users can fetch the GitHub source and use the terminal-only commands in
README and FIRST_RUN. The existing terminal animation remains, with no graphical
installer launch. This source route requires uv and Git; the graphical download
does not. There is no separate runtime per model or assistant.

Pink, lavender and soft yellow accents now follow Glenn's supplied artwork,
with lighter plum-charcoal surfaces, fine-line corner marks and a small tricolor
rule. The native molecule animation, compact dimensions and minimal final page
remain. No new decorative screens or post-finish page were added.

**Limits:** multiple assistants may be registered, but the existing native API
endpoint still has one process owner. Test drawing clients one at a time and
disconnect the other ChemDraw server if diagnostics reports it busy. This build
does not claim simultaneous multi-client drawing. It remains ad-hoc signed;
Developer ID signing/notarization and fresh client click-through tests are pending.

## Earlier bundle workflow and implementation

The rc7 test bundle was for Apple Silicon Macs with Claude Desktop and licensed
ChemDraw. It is an experimental local build, not a signed public release.
Only macOS 15.6 / ChemDraw 23.0.1.11 has been exercised here. Intel requires its
own build and native acceptance; no Intel executable is included.

## User experience

Double-click the `.mcpb` and approve installation in Claude Desktop. When Claude
starts the extension for the first time, the native setup window opens. It reuses
the nine existing native molecular silhouettes, gold reveal and a small
"Created by Glenn Bojanov" credit. Progress indicates completed setup stages,
not simulated installation percentages. Reduce Motion stops the animation.

The compact 800 by 400 point window starts with a prominent Select ChemDraw
button. Next is disabled until an application has been validated. Three pages
cover app selection, add-in installation and the connected result. Dependency
checks advance automatically to preparation; a check mark replaces the old
standalone software-checked page. Next on the installation page tests the actual
live API read. Finish requires that read.
The window explains Add-in Manager activation and the ChemDraw Items directory
remedy. No terminal commands, JSON configuration edits or Markdown reader are
required. ChemDraw installation/licensing and macOS permission consent remain
the user's responsibility. No arbitrary preference or security settings are changed.

Finish setup is enabled only after a successful live read. It releases the setup
helper's private endpoint, saves completion and closes the setup application.
There is no extra completed page or Open Claude button. The connected page hides
all installation instructions and recovery controls. Native tools refuse to
run before setup is complete. Normal drawings still use the same shared-canvas
API and house defaults. The setup test does not insert a drawing or certify
Claude's separate Automation permission.

Diagnostics appear only when setup needs attention, not as a normal setup task.
The UI saves a plain-text diagnostic summary on request. It contains versions and
dependency/readiness results, not drawings, document names or bridge credentials.
No reports are uploaded. The private add-in is generated locally, never bundled.

Warm charcoal, cream, muted pink and gold replace the previous teal palette.
The layout is unchanged. Molecular silhouettes are fitted uniformly using their
actual dot bounds, not padded terminal sprite dimensions. Each is centered in
the same area with its aspect ratio intact. The MCPB declares a bundled 512-pixel
molecular icon for the Claude extension card.

Share only the MCPB with another user. The .chemdrawaddin is a second ZIP-based
package generated privately on their own Mac. In rc6, Save installer to Downloads
opens a normal Save dialog and reveals the saved file. No hidden Library navigation
is needed. The package is CRC-checked before atomic export with owner-only access.
Fresh setup no longer writes installed add-in assets before Add-in Manager import.
Existing files trigger instructions to enable the existing entry, avoiding a
duplicate import. The source package lives outside the installation destination
so replacing that folder cannot delete the archive being imported.

The reported friend's invalid-ZIP file is not available for inspection. These
changes fix demonstrated setup hazards, not a claim to have reproduced that exact
remote ChemDraw error. Local generated ZIPs validate; native Add-in Manager import
on the friend's Mac still needs a retest. Do not share the generated private add-in.

## Package contents and build

`packaging/Welcome.swift` is the native SwiftUI setup application.
`packaging/SetupPresentation.swift` supplies its tested presentation transitions
and molecular ink geometry.
`chemdraw_macos/desktop_setup.py` is its bounded newline-JSON helper, frozen with
the same project, Python, RDKit and resvg. The MCPB runs that bundled executable
over stdio with the full profile. The existing raster-worker subprocess also
dispatches within this executable; no external Python is required.

Use an isolated build environment with the locked chemistry requirements and
PyInstaller 6.16.0. Run `scripts/build_desktop.py NEW_BUILD_DIRECTORY` with its
Python. Build on the target Mac architecture. The script compiles Swift, freezes
the runtime, retains dependency licenses, checks ad-hoc signatures, executes the
bundled chemistry/raster self-check and builds the MCPB. No client is installed.
The corresponding source archive must accompany redistribution.

The rc4 package failed after Claude installation because its ZIP extractor wrote
PyInstaller's library symlinks as small text files. The installed RDKit error was
"slice is not valid mach-o file" for libRDKitRDBoost.1.dylib. The rc4 ditto-based
extraction test preserved links and missed this. The rc5 builder materializes
all runtime links before signing and refuses symlinks in the final stage. A plain
ZIP extraction acceptance test reproduces the old failure and passes on rc5.

This development Mac had duplicate legacy/new SwiftBridging module maps in its
Command Line Tools installation. A local compiler VFS overlay masked only the
legacy duplicate for these builds; no installed toolchain file was changed.
`CHEMDRAW_BUILD_SWIFT_OVERLAY` optionally supplies such a build-local overlay.
Do not ship it as an end-user requirement.

## Evidence and remaining gates

- Portable setup tests cover readiness, application validation, endpoint release,
  private settings, unknown commands and strict JSON protocol.
- Actual frozen executable checks cover clean PATH/no system Python, chemistry
  CDXML roundtrip, rasterization worker, setup protocol and real stdio MCP
  initialization/discovery/offline chemistry.
- The frozen setup helper passed an actual live document read without drawing
  writes on this Mac. Welcome and add-in instruction screens were rendered from
  the real SwiftUI view and visually inspected.
- Anthropic MCPB CLI 2.1.2 validates the manifest.
- Glenn's rc6 screenshots show the fresh setup reached Connected to ChemDraw and
  passed the live document read. rc7 adds compiled Swift regression tests for the
  three-page flow, completion-close action and all nine molecule bounds. Actual
  SwiftUI welcome, installation and connected views were rendered and inspected.
  Automated tests do not substitute for a fresh rc7 click-through in Claude.
- The current app has an ad-hoc signature only. This Mac has no Developer ID
  signing identity. Developer ID signing plus notarization is required before
  claiming a smooth public-download installation. Do not disable Gatekeeper.
- Another-Mac installation, Claude-side Automation permission and actual first
  drawing from that client remain acceptance gates. Organization policy may block
  custom extensions.

Format and installation reference: [Claude MCPB documentation](https://claude.com/docs/connectors/building/mcpb).
Bundling reference: [PyInstaller feature notes](https://pyinstaller.org/en/stable/feature-notes.html).
