# Portable lab style packages

A lab style is a versioned JSON configuration, not an executable skill or an alternative renderer. Native ChemDraw still draws and exports the molecules. The package contains validated numerical typography, bond settings, layout spacing, symbol dimensions, conventions and optional reference hashes. It embeds no fonts, proprietary template artwork, application files or executable code.

The checked-in starting point is [publication-bold.lab-style.json](../examples/publication-bold.lab-style.json). Its chemical scale is 18 pt bonds, 1.58 pt line width and 14 pt Helvetica Neue atom labels. Captions use the established 8.28 pt house setting. The grid spacing matches the complete grouped scope example. Fonts must exist on the receiving Mac; they are checked before custom native rendering.

## Create, inspect and use

```sh
chemdraw-mac make-lab-style \
  --name my-lab --version 1.0.0 \
  --style /absolute/path/to/reference.cdxml \
  --output /absolute/existing/parent/my-lab.json

chemdraw-mac inspect-lab-style --input /absolute/path/to/my-lab.json

chemdraw-mac styled-job \
  --lab-style /absolute/path/to/my-lab.json \
  --workflow draw --recipe /absolute/path/to/structures.json \
  --output /absolute/existing/parent/new-drawing
```

The source style may be a supported CDS, CDX or CDXML file. Extraction is read-only and copies only the supported settings. Optional `--settings settings.json` supplies `grid`, `reaction`, `symbols`, and/or `references` data. It never copies the source template itself. See [style import](STYLE_IMPORT.md) for extraction limits.

The recipe is the ordinary workflow recipe, with its style/spacing omitted or exactly matching the package. Conflicting explicit values cause an error, not a silent override. Other workflow-specific options, such as the chosen candidates, columns, pixels, source IDs and conditions, remain explicit recipe inputs.

| Workflow | Settings actually consumed |
| --- | --- |
| `draw` | Numerical preset and grid `h_gap`, `v_gap`, `label_gap`, `margin` |
| `scope-job` | Numerical preset and actual group/grid spacing; explicit proposal acceptance remains required |
| `reaction` / `reaction-series` | Numerical preset and `gap`, `label_gap`, `condition_gap`, `row_gap`, `margin`; the expanded reaction path is used |
| `grid` | Numerical preset and grid spacing; recipe requires `input` CDXML path plus explicit cell ownership |
| `symbols` | `span`, visible `line_width`, `clearance`; recipe requires `input` CDXML path and explicit symbol requests; this does not restyle the source molecule |

Expanded reactions currently do not accept a scaffold-alignment request; such a conflict is rejected, not ignored. Workflow-specific physical page and spacing limits still apply. A package is not a promise that every number of molecules or every long name will fit a page. Neither molecular scale nor font size is automatically reduced to force a fit.

Default grid values are 18/24/10/36 pt for horizontal gap, vertical gap, label gap and margin. Default reaction values are 16/10/10/120/36 pt for component gap, label gap, condition gap, row gap and margin. The larger row separation avoids an observed native cross-row condition-assignment issue; it is not a universal guarantee for arbitrary captions. Default symbol span is 0.75 times the atom label size; its visible line width matches the molecular line width, with 2 pt clearance. Unsupported combinations outside the symbol workflow's bounds require explicit supported symbol settings when creating the package.

## MCP and Python

MCP tools are `chemdraw_create_lab_style`, `chemdraw_inspect_lab_style` and `chemdraw_run_styled_job`. They call the same implementation as the CLI. The create tool takes an explicit preset object, obtained for example from `chemdraw_import_style`. It writes only a new requested file. The run tool takes `package_path`, `workflow`, `recipe` and a new `output_dir`.

The Python functions live in `chemdraw_macos.lab_style`: `make_package`, `validate_package`, `load_package`, `save_package`, `styled_options` and `run_styled_job`. No external naming service or network connection is involved.

## Sharing and reproducibility

Keep the JSON and this guide in a versioned shared folder. When changing settings, generate a new package version. Each successful styled output retains the exact package as `lab-style.json`; its audit records the package name, version, content hash and workflow. The ordinary request file contains the actual applied numerical values. Existing output/package files are never overwritten.

The SHA-256 hash detects changed content; it is not a signature proving authorship or trust. Unsupported keys, duplicate JSON keys, malformed versions and mismatched hashes are rejected. Optional reference records contain exactly a safe name, SHA-256 and description. They do not read or execute a referenced file and do not automatically verify that another person has visually approved it.

The conventions are guidance with explicitly scoped consumers. Running `draw` does not automatically add circled charges, choose electron-flow arrows, infer reaction products or certify stereochemistry. Use the corresponding explicit workflows. Machine checks, chemical review and visual review remain separate.

The package can later be placed on Synology without machine-specific paths inside it. No NAS installation, permission change or public release is performed by creating it. Receiving-Mac validation and project licence/publication decisions remain separate gates in the [release checklist](RELEASE_CHECKLIST.md).
