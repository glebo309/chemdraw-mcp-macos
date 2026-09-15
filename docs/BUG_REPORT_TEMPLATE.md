# Minimal compatibility or drawing report

Copy this template into a private report or, after public release is authorized, a repository issue. Do not upload confidential structures, unpublished results, proprietary templates, fonts, licences or whole workspace folders. Prefer a small public or invented chemical example that reproduces the behavior.

## Environment

- Package version:
- macOS version and processor architecture:
- ChemDraw version/build and whether the application is activated:
- Python version:
- Installation method:
- CLI or MCP client; client version if relevant:
- Output of `chemdraw-mac doctor --no-connect`, after removing private paths:
- Did a native connection test succeed?

## Reproduction

- Command or MCP tool and explicit arguments, with private paths replaced:
- Minimal recipe and redacted supported CDXML, if safe to share:
- Expected result:
- Actual result:
- Audit status and exact error:
- Was any operation marked uncertain?
- Were other native editing clients running?

## Evidence

- Source and final native screenshots on a white background:
- Relevant redacted audit fields:
- Whether the editable CDXML, SVG and PNG differ visually:
- Whether original files/open documents changed:
- For a lab style, package name/version/hash and whether all font families are installed:

An uncertain native write must not be retried automatically. Keep its recovery snapshots locally and inspect the document inventory before deciding what to do. A successful graph check alone does not prove correct glyphs or a chemically valid mechanism.
