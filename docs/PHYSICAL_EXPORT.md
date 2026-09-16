# Export at consistent chemical scale

Ask your assistant: "Export this drawing for my paper at 600 DPI, with transparent
PNG, SVG and a PDF. Keep the chemical scale unchanged." For slides, ask for 300 DPI.

Use `chemdraw_export_figure(document_id, output_dir, dpi=600, include_pdf=False)`,
available in all profiles. The terminal equivalent is:

```sh
chemdraw-mac export-figure DOCUMENT_ID --output /absolute/new-folder --dpi 600 --pdf
```

SVG retains native paths, glyphs and transforms with dimensions in points. PNG
uses drawing points times DPI / 72, with transparency and embedded DPI metadata.
An 18-point bond is 150 pixels at 600 DPI, or 75 at 300 DPI. Different drawings
deliberately have different image dimensions. Cropping is not rescaling. Existing
inconsistent bond lengths are retained, not silently fixed. Insert images at
original size; fitting every image to the same width undoes consistent scale.

A single sheet uses native cropped drawing bounds. Multiple vertical sheets
produce one SVG/PNG pair per drawing sheet, plus a whole-drawing SVG and editable
CDXML. Native PDF retains physical paper and printer margins. Its hidden private
copy prevents naming an untitled original as a saving side effect. Only a
successfully exported copy is closed; uncertain native failures are never retried.

`export.json` records paths, pages, DPI, physical extent and source preservation.
No HTML review. The old low-level `chemdraw_export(... pixels=...)` remains a
fit-to-longest-side preview operation, not a consistent-scale publication export.

Supported: one canvas with 1 through 20 vertical physical sheets and a verified
uniform native coordinate transform. Horizontal tiling or unrecognized transforms
fail explicitly. PNG limits are 64 megapixels and 16000 pixels per side per sheet.
Selected-object extraction and automatic journal formatting are not implemented.
