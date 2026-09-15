# Third-party notices and provenance

This file distinguishes source incorporated into this project from projects only evaluated. Original project code is licensed under AGPL-3.0-only; see [LICENSE](LICENSE) and [NOTICE](NOTICE). Third-party components retain their applicable licences and notices below. No endorsement by upstream maintainers or ChemDraw's vendor is implied.

## Incorporated source

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

PNG conversion uses the separately installed [resvg-py 0.5.0](https://pypi.org/project/resvg_py/0.5.0/) dependency, whose wheel includes an MIT LICENSE with Copyright (C) 2024 baseplate-admin. [Binding source and licence](https://github.com/baseplate-admin/resvg-py). The underlying [resvg 0.48.0](https://github.com/linebender/resvg/tree/v0.48.0) is dual MIT/Apache-2.0. No upstream rasterizer source is copied into this project; the local adapter calls its public API. Preserve the applicable dependency notices when packaging dependencies. This is pixel conversion of ChemDraw's native SVG, not molecular depiction by another chemistry toolkit.

## ChemDraw

The v0.9 offline integral-group compatibility plan follows the native object shape inspected in installed ChemDraw 23.0.1 BioDrawResources examples and the archived vendor Group/Integral documentation linked in [ownership](docs/OWNERSHIP.md). No example artwork, application resource files or vendor source are incorporated. This research-only plan does not establish native manual-drag compatibility.

ChemDraw is proprietary software and a trademark of its respective owner. Users supply their own licensed installation. This repository is independent and unofficial; ChemDraw itself and its proprietary assets are not distributed here.
