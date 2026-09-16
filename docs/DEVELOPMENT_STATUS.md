# Experimental development snapshot

Updated 2026-09-17. Current candidate: **0.10.0rc13**. The Git route has an
`install.sh` entry point that installs locked dependencies and launches themed
terminal setup. The Apple Silicon DMG includes the graphical helper and runtime.
Shared native drawings support measured tables across physical pages and
physical-scale exports. Fresh terminal testing corrected both Apple Terminal
background colours and discovery of filename-suffixed add-in installations.

Graphical Finish also installs terminal commands using the bundled runtime and
a backed-up zsh PATH entry. Reaction preservation checks can read the active
untitled original without saving it. Full-profile guidance explicitly exposes
the existing electron-pushing annotation workflow; complete mechanism layout
and chemistry inference are not solved by that guidance.

The rc13 portable suite passes 1130 tests, with 91 opt-in skips. Four focused
native tests and twelve frozen-runtime/packaging checks passed. Native evidence
is limited to the development Mac and ChemDraw 23.0.1.11. Another-Mac acceptance,
Developer ID signing/notarization and transactional graphical updates remain
open. See PROJECT_PROGRESS.md for exact candidate checks. The older rc2 feature
record below is historical, not the current package version.

## Current checks

Subsequent development (not a rebuilt rc2 archive): explicit targeted atom/H/charge
and bond-order changes, supplied-fragment attachment and branch removal now have
native MCP coverage. Placement checks include bounded attachment-angle search,
hidden-carbon prevention and post-render measured-label clearance. Charge placement
uses local bond widths and rechecks saved native clearance. Built-in presets now
share custom-style verification, and simple reaction captions use visible spacing.
Latest portable check: 873 passed, 64 skipped; separate native runs passed nine
targeted cases and eleven drawing/style/symbol cases. See PROJECT_PROGRESS.md for
exact reports and boundaries. The rc2 evidence below remains its historical snapshot.

- Final portable suite: 773 passed, 39 native tests skipped in 6.35 s. Evidence: `local-validation/rc2-portable-final.xml`.
- Before adding the separate metal endpoint, the full suite with native tests enabled passed 785 tests in 408.97 s. Evidence: `local-validation/rc1-native-full.xml`. After adding it, both metal native tests passed in 6.60 s, including the actual fresh stdio MCP transport. These are separate runs, not a claimed combined full-suite result.
- One-call `first-run` / `chemdraw_first_run` checks dependencies and draws the fixed native caffeine/aspirin example. Interactive CLI now cycles through nine bundled native silhouettes, including alizarin instead of uric acid. Fixed geometry, no displayed names, ANSI16 colour and a continuous phase-weighted bar; completion follows passed checks. MCP and JSON remain animation-free. [First-run contract](FIRST_RUN.md), [desktop client setup](MCP_CLIENTS.md).
- Per-user cross-process coordination is implemented, including reentrant native workflows and complete low-level create/import/close transactions. Busy contention is distinguished from uncertain native outcomes.
- Opt-in `charge_style: "circled"` is available in draw and styled draw jobs. The default remains plain; returned `artifacts` points to the actual final CDXML/SVG/PNG.
- Denser bounded circled-charge placement passes native nitrobenzene with unchanged glyph size, stroke, owner and clearance checks. Crowded tetramethylammonium still fails safely at this house style; no claim of a universal collision solver.
- Cage drawings retain valid crossing references and relative foreground order. Cubane, bullvalene and adamantane pass native rendering and preservation checks; their preview was inspected on white. Native crossing caches may be recomputed and absolute Z values renumbered.
- Experimental `complex-draw` / `chemdraw_draw_complex` accepts explicit donor-to-metal dative bonds and supplied point XYZ coordinates in a separate workflow. Copper/ammine native direct and MCP tests pass. This preserves records and a 2D projection, not inferred stereochemistry or a 3D model. [Metal contract](METAL_COMPLEXES.md).
- Opaque GitHub previews preserve the original transparent exports and every native drawing element. Marco DeCorti's acknowledgment is retained.
- Release artifacts are built locally, not published to a package index. See [candidate handoff](ANOTHER_MAC_TEST.md) and the latest progress entry for archive and installed-wheel evidence. Marco DeCorti's acknowledgment and AGPL/upstream notices are retained.

## Next work

1. Verify installation and native drawing on another Mac with its own licensed ChemDraw.
2. Address remaining crowded-charge cases only with explicit geometry/style choices, never weakened owner checks or silently smaller symbols.
3. Continue molecule-first usability and consistent styling. Reactions combine explicit molecules; charts and general figure composition are not the current priority.
4. Expand metal fixtures and explicit spatial depiction deliberately. General complex construction, hapticity and 3D geometry prediction remain unsupported.
5. Complete the remaining stable-release acceptance and distribution review. Original project code is now AGPL-3.0-only.
