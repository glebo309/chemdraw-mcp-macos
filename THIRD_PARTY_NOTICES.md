# Third-party notices and provenance

This file distinguishes source incorporated into this project from projects only evaluated. Original project code is licensed under AGPL-3.0-only; see [LICENSE](LICENSE) and [NOTICE](NOTICE). Third-party components retain their applicable licences and notices below. No endorsement by upstream maintainers or ChemDraw's vendor is implied.

## Incorporated source

The crossing-bond and explicit coordination modules use documented CDXML format semantics, recorded in [upstream-sources.json](upstream-sources.json), with original implementation code and synthetic regression fixtures. No vendor source or template artwork is included. The bundled welcome silhouettes were derived from this project's native ChemDraw exports of explicit molecular inputs; their source hashes and input provenance are retained in `chemdraw_macos/data/welcome.json`. They contain no fonts, ChemDraw application resources or textbook artwork.

### live-chemdraw-mcp

- Author/copyright: **Copyright (c) 2026 Michael Leitch**.
- Repository: <https://github.com/MALeitch/live-chemdraw-mcp>.
- Pinned revision: `a9cebc6cf61e4d9b019463019626684fdf30beb6`.
- Source: `chemdraw_connector/domain/layout_math.py`.
- Adapted components: `Box`, `find_overlaps` and `grid_positions` in `chemdraw_macos/geometry.py`. The grid adaptation receives already measured compound-plus-caption cell extents; column validation and native fit checks live in this project's scope workflow.
- License: MIT. The full upstream text is retained in [licenses/live-chemdraw-mcp.txt](licenses/live-chemdraw-mcp.txt).
- Scope: platform-independent geometry only. The Windows COM bridge and the rest of the upstream tool implementation have not been copied.

Keep this record and the full license with redistributed copies that contain the adapted code. Changes to the adaptation and additional upstream reuse must be recorded in [upstream-sources.json](upstream-sources.json).

## Evaluated projects, no source copied in this increment

These are acknowledgments and license observations from the pinned revisions, not notices claiming those projects are bundled. Runtime dependencies retain their own licensing and must be included in a release dependency audit.

| Project | License observed | Attribution or source notice |
|---|---|---|
| [ChemDraw Skill](https://github.com/ZiChenWang114514/chemdraw-skill) | MIT | Copyright (c) 2026 chemdraw-skill contributors |
| [CDXML Toolkit](https://github.com/leehiufung911/cdxml-toolkit) and [community fork](https://github.com/ZiChenWang114514/cdxml-toolkit-community) | MIT | Copyright (c) 2026 Hiu Fung Kevin Lee |
| [jurimaxam-dotcom/chemdraw-mcp](https://github.com/jurimaxam-dotcom/chemdraw-mcp) | Apache-2.0 | Repository credited by its published name; its root license contains the standard copyright placeholder, not a verified personal copyright attribution |
| [RDKit](https://github.com/rdkit/rdkit) | BSD-3-Clause | Root notice: Copyright (c) 2006-2015, Rational Discovery LLC, Greg Landrum, and Julie Penzotti and others. Individual source files have additional notices |
| [EPAM Indigo](https://github.com/epam/Indigo) | Apache-2.0 | EPAM Indigo project and contributors; individual source/dependency notices remain applicable |
| [EPAM Ketcher](https://github.com/epam/ketcher) | Apache-2.0 | Root license notice: Copyright 2021 EPAM Systems; preserve NOTICE if adopted |
| [Open Babel](https://github.com/openbabel/openbabel) | GPL-2.0 | Inspected CDXML source: Copyright (C) 2006 by Geoff Hutchison; Portions Copyright (C) 2010 by Joerg Kurt Wegner; Portions Copyright (C) 2012 by NextMove Software |
| [OPSIN](https://github.com/dan2097/opsin) | MIT | Copyright 2017 Daniel Lowe |
| [keyClip](https://github.com/mmaskeri/keyClip) | MIT | Copyright (c) 2019 Mark A. Maskeri (mmaskeri) |

The machine-readable record links exact revisions and license files. See [docs/UPSTREAM_RESEARCH.md](docs/UPSTREAM_RESEARCH.md) for reuse decisions and technical limitations. None of the above project licenses automatically covers third-party paper images, proprietary ChemDraw assets or locally installed fonts.

## Runtime SVG rasterizer

The optional macOS desktop-extension artifact bundles its Python interpreter,
project dependencies and the PyInstaller bootloader. The builder retains their
installed license/notice files under the helper app's Resources/Licenses,
including CPython's license and PyInstaller's bootloader exception. These binary
dependencies retain their own licenses. The original SwiftUI welcome window
reuses this project's existing native silhouette data, not vendor UI artwork.

PNG conversion uses the separately installed [resvg-py 0.5.0](https://pypi.org/project/resvg_py/0.5.0/) dependency, whose wheel includes an MIT LICENSE with Copyright (C) 2024 baseplate-admin. [Binding source and licence](https://github.com/baseplate-admin/resvg-py). The underlying [resvg 0.48.0](https://github.com/linebender/resvg/tree/v0.48.0) is dual MIT/Apache-2.0. No upstream rasterizer source is copied into this project; the local adapter calls its public API. Preserve the applicable dependency notices when packaging dependencies. This is pixel conversion of ChemDraw's native SVG, not molecular depiction by another chemistry toolkit.

## ChemDraw

Targeted editing uses original graph/geometry code and privately observed native
selection/command behavior. The existing project's validators are reused. The
Windows project's published selection notes were reviewed for comparison only;
no selection implementation or vendor code was copied. Native subset alignment
uses the existing allowlisted ChemDraw command bridge.

The allowlisted native-action and Name to Structure wrappers are original code,
based on the installed ChemDraw 23.0.1 scripting dictionary and targeted sections
of the ChemDraw 21 manual. Only API names and behavior were used. No dictionary
file, manual extract, vendor implementation or toolbar artwork is distributed.

Crossing-bond support follows the archived vendor `CrossingBonds` and `Z` documentation recorded in upstream-sources.json. No vendor implementation code was copied. The welcome animation bundles precomputed Unicode silhouettes of project-generated native drawings, with names, explicit SMILES and SVG hashes retained as provenance. It contains no font files, proprietary templates, textbook artwork or application resources.

The v0.9 offline integral-group compatibility plan follows the native object shape inspected in installed ChemDraw 23.0.1 BioDrawResources examples and the archived vendor Group/Integral documentation linked in [ownership](docs/OWNERSHIP.md). No example artwork, application resource files or vendor source are incorporated. This research-only plan does not establish native manual-drag compatibility.

ChemDraw is proprietary software and a trademark of its respective owner. Users supply their own licensed installation. This repository is independent and unofficial; ChemDraw itself and its proprietary assets are not distributed here.
## Spatial-complex format observations

The schema-2 complex writer and synthetic fixture coordinates are original project work. Property meanings were checked against the publicly accessible CDX/CDXML SDK pages for NodeType, Attachments, bond display and bond order, linked in upstream-sources.json. Targeted ChemDraw manual sections and an installed metallocene template were inspected privately to compare working native object patterns. No vendor artwork, coordinates, manual extracts or implementation source is incorporated or redistributed. PubChem's 2,2'-bipyridine description informed the ligand-connectivity check. Ferrocene remains an explicit native-import failure fixture, not a supported successful depiction.
