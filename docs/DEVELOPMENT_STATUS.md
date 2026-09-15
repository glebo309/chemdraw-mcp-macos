# Experimental development snapshot

Updated 2026-09-15. Package version 0.9.1 remains experimental, with native evidence limited to the development Mac and ChemDraw 23.0.1.11.

## Current checks

- Full portable command: `.venv/bin/pytest -q`. Recorded result after licensing checks: 716 passed, 34 native tests skipped, no failures. No native behavior changed in the licence-only increment.
- Per-user cross-process coordination is implemented, including reentrant native workflows and complete low-level create/import/close transactions. Busy contention is distinguished from uncertain native outcomes.
- Opt-in `charge_style: "circled"` is available in draw and styled draw jobs. The default remains plain; returned `artifacts` points to the actual final CDXML/SVG/PNG.
- The original native failure was a real charge reassignment from nitrogen to a nearby carbon. Placement now rejects a charge center closer to another atom. Crowded tetramethylammonium and nitrobenzene at the current house style remain refused in circled mode; plain-charge graphs are supported.
- Full serial native acceptance passed all 34 tests in 441.91 seconds, including all four original plain-charge graphs and three circled charges across glycine zwitterion and benzoate. The actual CLI ionic demo also passed and its preview was visually inspected on white. Negative charges sit low beside the caption row, a remaining visual-refinement opportunity. Evidence paths are recorded in PROJECT_PROGRESS.md; interrupted runs are not counted as passes.
- Opaque GitHub previews preserve the original transparent exports and every native drawing element. Marco DeCorti's acknowledgment is retained.
- The 0.9.1 wheel and source archive build offline. Archive checks confirm the coordination module and upstream notice, with local validation bundles and proprietary references excluded. Built packages are local, not published releases.

## Next work

1. Verify installation and native drawing on another Mac with its own licensed ChemDraw.
2. Improve crowded circled-charge placement without weakening graph, stereo or owner checks. Current refusals are explicit limits, not solved layouts.
3. Continue molecule-first usability and consistent styling. Reactions combine explicit molecules; charts and general figure composition are not the current priority.
4. Investigate explicit coordination bonds and supplied spatial depictions for metal complexes. General metal-complex construction and 3D geometry are not implemented or certified.
5. Complete the remaining stable-release acceptance and distribution review. Original project code is now AGPL-3.0-only.

The repository was made public with Glenn's approval on 2026-09-15 and subsequently licensed under AGPL-3.0-only at his request to make it open source. It includes source, tests, documentation and synthetic examples. It excludes local-validation bundles, virtual environments, built distributions, proprietary templates, application binaries and reference PDFs. Open-source licensing does not establish a stable release.
