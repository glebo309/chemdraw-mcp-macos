# Import local document styles

`import-style` extracts a bounded set of bond and typography settings from a local
ChemDraw style or drawing file. It returns a validated custom preset without opening
ChemDraw. The drawing workflows can then apply that preset to their own working
copies using desktop ChemDraw for rendering.

## Inspect, then use

```sh
uv run chemdraw-mac import-style \
  --input /absolute/path/my-style.cds \
  --output /absolute/existing/parent/style-report.json

uv run --extra chemistry chemdraw-mac draw \
  --manifest examples/acetophenone-scope-draw.json \
  --style /absolute/path/my-style.cds \
  --output /absolute/existing/parent/styled-scope
```

`--output` on `import-style` is optional. The command always prints its report as
JSON. A saved report requires a new absolute filename and an existing parent
directory; an existing file is never overwritten. `draw --style` explicitly overrides
the manifest's `preset`. The drawing output directory must also be new and absolute.
Style inspection requires neither RDKit nor a running ChemDraw application. Drawing
still requires its optional chemistry dependencies and licensed native application.

MCP `chemdraw_import_style(path)` returns the same inspection report. Pass the
report's `preset` object, rather than the whole report, as `preset` to
`chemdraw_draw_structures`, `chemdraw_polish_document`, `chemdraw_grid_document` or
`chemdraw_apply_style`. Reaction building also accepts the same custom `preset`.
Their existing named presets remain available.

## Supported input

| File | Imported source |
|---|---|
| `.cds`, `.cdx` | Binary CDX document-level properties and referenced font-table names |
| `.cdxml` | UTF-8 CDXML root style attributes and one explicit root font table |

Inputs must be local files of at most 10 MB. A `.cds` extension alone does not
establish support: the file must have a supported CDX document boundary and complete
required style settings. CDXML is parsed with entity expansion and external entity
access disabled. This is style extraction, not a binary chemistry converter or a
general validation of every object in a template.

The binary reader uses tagged properties in little-endian order, including the
extended-length representation. The archived manufacturer's SDK describes a 28-byte
header followed by the document object. That documented layout is supported.
The local ChemDraw 23 native style fixture instead places the document after a
22-byte header; the implementation also supports that specifically observed layout.
It does not scan for a convenient object offset or declare the documented 28-byte
layout invalid. [CDX binary format](https://chemapps.stolaf.edu/iupac/cdx/sdk/IntroCDX.htm)

Document bond settings, label/caption font IDs, sizes and faces follow the SDK's
document properties. The reader accepts combined font-style records and explicit
font/size/face properties; explicit properties take precedence when both are present.
[Document object and property definitions](https://chemapps.stolaf.edu/iupac/cdx/sdk/Document.htm)

Font IDs resolve through the document font table. The binary table contains platform,
font ID, character-set metadata and font-name bytes. This implementation accepts
the two documented platform codes and ASCII binary font names; it does not copy font
files or reproduce the template's text encoding. CDXML supplies font names directly.
[CDX font-table definition](https://chemapps.stolaf.edu/iupac/cdx/sdk/DataType/CDXFontTable.htm)

Malformed or truncated records, unexpected trailing binary data, duplicate document
properties, duplicate font IDs, unresolved font references and unsupported font-table
layouts fail explicitly. CDXML requires exactly one font table and rejects missing
or duplicate font IDs. Binary traversal is bounded to 100,000 records and nesting
depth 64; font tables are bounded to 1,000 entries. These are implementation limits.

## Custom preset API

Python callers can use `inspect_style_file(path)` and pass its `preset` result into
the existing workflow APIs. `validate_style(spec)` checks a directly supplied
dictionary and returns normalized string values plus supported defaults.
`core.preset_settings(preset)` accepts either a named preset or this dictionary.

```python
from chemdraw_macos.styles import validate_style

preset = validate_style({
    'BondLength': 18,
    'LineWidth': 1.2,
    'BoldWidth': 2,
    'LabelSize': 14,
    'CaptionSize': 12,
    'font': 'Arial',
    'CaptionFontName': 'Arial',
})
```

These values are an illustrative custom preset, not a claim about a journal's rules.
The required fields are `BondLength`, `LineWidth`, `BoldWidth`, `LabelSize`,
`CaptionSize` and `font`. Font names must be nonblank strings of at most 120
characters without control characters. Optional `CaptionFontName` defaults to the
label family. Imported CDXML requires explicit resolved label and caption fonts.
If a binary source omits its caption font but otherwise supplies the required
settings, `defaults_used` includes `CaptionFontName` to disclose that fallback.

| Numerical field | Inclusive accepted range | Default when absent |
|---|---|---|
| `BondLength` | 5 to 100 pt | Required |
| `LineWidth` | 0.1 to 5 pt | Required |
| `BoldWidth` | 0.1 to 10 pt | Required |
| `LabelSize` | 4 to 72 pt | Required |
| `CaptionSize` | 4 to 72 pt | Required |
| `BondSpacing` | 1 to 100 percent of bond length | 18 |
| `ChainAngle` | 0 to 180 degrees | 120 |
| `MarginWidth` | 0 to 10 pt | 1.6 |
| `HashSpacing` | 0.1 to 10 pt | 2.5 |

Numerical strings or numbers are accepted; booleans, nonfinite values, unknown fields
and out-of-range values are rejected. Optional `LabelFace` and `CaptionFace` accept
only integer codes or matching integer strings in `0, 1, 2, 3, 96, 97, 98, 99`.
In existing text runs, styling changes the bold/italic bits while retaining other
run-level bits used for chemical typography. This is not a complete font-feature
or text-formatting importer.

## Font availability and application

Inspection reports `font_availability: "not_checked"`. Before a native workflow
uses a custom dictionary, `require_style_fonts` queries the rendering Mac's actual
AppKit font-family inventory. Both label and caption families must be present by
their supplied names. Missing families or an unavailable inventory fail before
native drawing/editing calls. No replacement family is silently chosen or installed.
The inventory check verifies family availability, not every face, glyph or final
rendered label; final native output still needs visual review.

The style layer writes supported document settings and explicit text-run fonts and
sizes. For custom presets it also replaces supported local object overrides, such
as an atom's explicit font/size or a bond's explicit spacing. It applies black
atom/bond/text styling and supported bond widths. It retains chemical text-run
formatting outside the requested bold/italic bits. Custom grid metadata uses the
requested caption face; the named presets retain their existing bold metadata
policy. Importing a
style does not import its colour palette. The workflow's existing geometry behavior
still applies: low-level `apply_style` creates a copy without rescaling coordinates,
while normalization in polish/grid/draw uses the requested bond length. Setting a
document's `BondLength` alone does not change existing atom coordinates.

## Evidence, source preservation and limits

The inspection JSON records the resolved source path, SHA-256 of the bytes inspected,
input format, validated `preset`, `defaults_used`, `unapplied_properties`, unchecked
font availability, `network_used: false` and limitations. The importer rereads the
source before returning and rejects a detected byte change. It never writes the
source file or opens it in ChemDraw.

`unapplied_properties` lists unused binary document-property tags or unused CDXML
root attribute names. It is not an exhaustive inventory of nested template content.
A coloured combined font-style property is reported as unapplied even when its
supported font/size/face fields were extracted, because its colour was not applied.
Review this list and `defaults_used` when deciding whether the subset suits the figure.

Custom styling verifies the native saved result in addition to the workflow's
chemistry/layout checks. The shared `verify_custom_style(expected, native, preset)`
checks supported numerical document settings and local overrides, resolved font
families, effective text sizes and bold/italic face bits. Font-ID renumbering and
text-run splitting are permitted. Explicit caption sizes, such as larger reaction
plus signs, are compared to the planned caption profiles. Chemical subscript and
superscript bits are retained during styling but are not independently certified
by this style verifier. It does not verify rendered glyphs or font-face availability.

The comparison permits up to 0.050001 pt for font-size quantization and 0.010001 in
the corresponding units for other numerical fields. These tolerances accommodate
the native application's saved precision; they are included in the verification
report. Changed or unresolved fonts, missing settings and differences exceeding
the bounds fail the workflow. The verifier does not add a new verification claim
for the existing named presets.

Polish, grid and reaction audits contain `custom_style_verification` when a custom
preset was checked. A custom draw includes the final verification in its nested
grid audit. Low-level `apply_style` exports its created copy before returning;
its response includes `styled_snapshot` and `custom_style_verification`. A failed
or uncertain verification export is not retried and the created copy is retained
for inspection without automatic closure. The original remains outside the
styled-copy editing path.

`draw --style` records the resolved preset in `request.json`. It does not
automatically include the separate style-source inspection report. Retain the
`import-style` JSON alongside the drawing bundle when the original style path/hash,
defaults and unapplied-property report matter.

Page size, print margins, template grids, headers/footers, artwork, molecular content,
colour palettes and font files are not imported. A successful style read does not
establish native compatibility for the whole source template. User-supplied template
files stay local and are not redistributed with this project; no proprietary template
or font licence is granted by the importer. Native workflows retain their existing
working-copy and uncertainty rules. Inspect final editable and rendered output before
using it. See [usage](USAGE.md) and [compatibility](COMPATIBILITY.md) for those boundaries.
