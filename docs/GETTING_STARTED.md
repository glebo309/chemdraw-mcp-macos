# Examples and customization

These prompts go to your connected assistant. MCP carries structured tool calls;
the assistant interprets your words. Its tool choices can vary, and a successful
graph check does not establish that its chemical interpretation was correct.

## A first editable molecule

> Draw caffeine in my current ChemDraw document and label it Caffeine. You may
> resolve its name online if needed. Show me the resulting editable figure.

The ordinary front door is `chemdraw_draw`. Explicit SMILES can be used without
name lookup. Network name resolution requires consent. Several open documents
require choosing the intended document rather than guessing.

## Work from your edits

> Read the structure I edited in the active document. Use the actual graph,
> not its old caption. Propose eight substituent variations at this specified
> ring position covering electronic and steric changes. Show me the proposed
> identities before drawing; do not invent yields or predict reaction success.

After reviewing those identities:

> Add the accepted structures as one table in this document. Retain the parent,
> align the common scaffold, center molecules and labels, and use equal row and
> column spacing. Add physical pages as needed without shrinking bonds.

The supported shared-table workflow measures native ink, uses common cell
centres and caption baselines, and preserves existing content. A complete table
that needs more space can add identical vertical pages, up to the supported
limit. It does not require an endless canvas or independently inserted rows.
To forbid extra pages, request `page_policy: "keep"`; overflow then fails before
insertion. Unsupported objects or ambiguous scaffold mappings require resolution.

## Export for a paper or slides

> Export this document as native PDF and transparent 600-DPI PNG pages, keeping
> its original chemical scale. Also keep SVG and editable ChemDraw files.

> Export the same drawing at 300 DPI for slides, without fitting each molecule
> to the same image width.

The assistant should use `chemdraw_export_figure`. A bond of 18 pt occupies
150 pixels at 600 DPI and 75 pixels at 300 DPI. A larger molecule therefore has a
larger image at the same scale. When placing images in a manuscript, preserve
their physical size; resizing every image to the same width defeats this rule.
The exporter preserves source geometry, including any inconsistent input scale.
[Physical export contract](PHYSICAL_EXPORT.md)

## Customize the drawing style

> Inspect the numerical style in this ChemDraw reference file. Create a versioned
> lab-style package from its supported settings and show me those settings before
> using it for a new drawing.

The built-in `house` and `acs-1996` presets are convenient starting points. For a lab
standard, use [a versioned lab-style JSON](LAB_STYLE.md): bond length, stroke
width, atom/caption font sizes, and supported layout spacing. The included
[publication-bold package](../examples/publication-bold.lab-style.json) shows
the format. Fonts must already exist on the rendering Mac.

Custom style jobs currently use the documented copy-based `styled-job` route;
do not assume every custom package is accepted by shared-canvas drawing.
Keep the normal same-document route on its supported built-in presets. Numerical
style extraction does not copy proprietary template artwork, page decorations,
fonts or executable instructions. A style cannot redefine chemical identity or
bypass preservation checks.

## Customize your assistant instructions

For example, add this to your client's project instructions:

> For ChemDraw work, read my current document first. Preserve my edits. Use the
> drawing harness for new structures, retain scaffold orientation where verified,
> and keep molecular scale consistent. Center structures and captions in equally
> spaced table cells. Never invent yields. Use physical-scale exports for final
> figures. Report unsupported input and uncertain writes without retrying them.

These are instructions for the assistant, not code executed by the server.
Portable numerical styles belong in lab-style JSON; workflow preferences belong
in client instructions. [Architecture](ARCHITECTURE.md)
