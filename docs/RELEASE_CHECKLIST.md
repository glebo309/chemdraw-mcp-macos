# Release and private handoff checklist

This is a preparation checklist, not permission for public release or redistribution. Glenn approved private GitHub hosting on 2026-09-15. Public release and the licence for original code remain separate decisions. Native acceptance on another Mac is still pending. A successful development-Mac run does not complete either gate.

## Required release gates

- [ ] Obtain an explicit licence choice for the project's original code and approval for the intended distribution. Existing third-party licences do not grant that licence.
- [ ] Complete installation and native acceptance on another Mac with its own licensed ChemDraw installation. Record exact macOS, processor architecture, ChemDraw build, Python and installed dependency versions. Do not describe untested combinations as supported.
- [ ] Reconcile package version, README, compatibility documentation, release notes and built artifact metadata for the exact candidate being handed off. Development source may contain features newer than the current package version.
- [ ] Run the full portable suite from the locked environment and retain the results for that candidate.
- [ ] Run opt-in native acceptance serially, using private test copies, and retain native CDXML/SVG/PNG, audits and environment records. Do not run a second native editing client concurrently.
- [ ] Visually inspect native-derived previews on white and check transparent PNG edges, text, charges, arrow sources/heads, headings, separators and shadow interiors. Also inspect editable ChemDraw output. Machine checks and human review are separate evidence.
- [ ] Confirm source files and pre-existing open/unsaved documents are unchanged. Exercise stale-token rejection, unsupported-input rejection and uncertain-operation handling without retrying an uncertain write.
- [ ] Complete dependency and provenance review for what will actually be distributed, including bundled dependency notices if distributing an environment. Retain [third-party notices](../THIRD_PARTY_NOTICES.md), [upstream provenance](../upstream-sources.json) and the incorporated-source licence in `licenses/`.
- [ ] Inspect the final archive contents. Exclude private research drawings, proprietary templates/book pages, fonts, application binaries, secrets, local-validation bundles and virtual environments unless separately authorized and appropriately licensed. Use the redistributable example sources, not private reference material.

## Acceptance procedure

From the candidate source directory on the receiving Mac:

```sh
uv sync --locked --extra chemistry
uv run --extra chemistry chemdraw-mac doctor --no-connect
uv run --extra chemistry chemdraw-mac doctor
.venv/bin/pytest -q
CHEMDRAW_LIVE_TEST=1 .venv/bin/pytest -q
```

The first diagnostic is offline; it does not establish native connectivity. The second connects to the installed application but is not itself a render test. Before the native suite, open and activate the user's licensed ChemDraw and resolve any macOS Automation prompt deliberately. Do not automate licence activation or dismiss unrelated application dialogs. Native tests are opt-in; skipped tests are not passes.

Then run the [demo walkthrough](DEMO_WALKTHROUGH.md) in a fresh output directory and record both machine results and visual observations. Keep detailed logs outside the release archive. Fill current acceptance totals and paths in [project progress](../PROJECT_PROGRESS.md), without converting older feature-specific evidence into a blanket compatibility claim.

## Claims that must remain explicit

| Area | Accurate disclosure |
| --- | --- |
| Rendering | Desktop ChemDraw imports, cleans where requested, saves and renders chemical drawings. PNG is offline rasterization of unchanged native SVG using pinned `resvg-py`; it is not a second chemical renderer. There is no silent renderer fallback. |
| Optional chemistry dependency | RDKit is optional for the basic native bridge, but required for high-level graph validation, identifier/proposal operations and applicable MOL coordinate seeds. Its presence does not replace licensed ChemDraw for native production. |
| Native coverage | Development evidence is tied to the recorded ChemDraw build and Mac. Other Macs, versions and architectures require their own acceptance. Windows/Linux native production is not supported by this backend. |
| Scope job | Explicit mapped parent, candidate acceptance and ordered category membership; actual measured group rows. Null yields remain null. Neither category labels nor graph preservation predict experimental success. |
| Reaction series | Explicit supplied participants, coefficients, conditions and ordered rows; bounded salt/small-species support. No inferred products, balancing, mechanism or experimental outcomes. |
| Ownership and routes | Snapshot-bound ownership supports workflow-controlled translations. Route suggestions require explicit endpoints and an explicit selected candidate. They do not establish native manual-drag attachment or a general chemical/collision correctness certificate. |
| Lab styles | Versioned, hashed numerical settings and conventions, with actual font-family preflight on the rendering Mac. Conflicting explicit recipe settings fail. No fonts, proprietary artwork or template files are embedded. |
| Network | Native production, local style inspection and scope proposals do not need a naming provider. PubChem resolution transmits only the explicit query with per-call opt-in; no automatic candidate selection. |
| Failure and review | `checks_passed` covers implemented checks, not chemical truth or human approval. Failed/uncertain partial artifacts are diagnostic. Unknown native outcomes stop without retry or automatic closure. |

The project is independent and unofficial. Users supply their own ChemDraw licence. Do not imply vendor endorsement, distribute ChemDraw, or suggest that this wrapper bypasses application licensing. See [compatibility](COMPATIBILITY.md), [style import](STYLE_IMPORT.md) and the workflow-specific contracts for the supported subset.

## Private handoff contents

Once the relevant sharing authority is established, prepare the exact source/archive candidate, locked dependency metadata, notices, checked-in examples and these instructions. Include a short environment/result summary with known failures and pending gates. A privately reviewable bundle is not a public release, compatibility certification or permission to publish it elsewhere.
