# Another-Mac acceptance

The local 0.10.0rc2 candidate is for testing, not a stable release. The receiving Mac needs its own licensed and activated ChemDraw. No existing drawings need to be closed or replaced.

## Candidate installation

Transfer the exact candidate wheel and its SHA-256 record to the receiving Mac. With uv installed, replace the path below with the actual wheel path:

```sh
uvx --from '/absolute/path/chemdraw_mcp_macos-0.10.0rc2-py3-none-any.whl[chemistry]' chemdraw-mac first-run
```

The first download/build progress belongs to uv. The molecular animation starts when the installed command runs. The actual smoke test draws caffeine and aspirin, not the decorative sequence. Allow macOS Automation access deliberately if prompted. Do not change permissions automatically or dismiss unrelated dialogs.

## Check these five things

1. Installation and application discovery finish without manual source edits.
2. The terminal animation has intact fixed structures, alizarin rather than uric acid, no molecule names, and a phase progress bar.
3. ChemDraw opens the editable caffeine/aspirin figure and the native checks pass.
4. The review looks correct: atom labels, bonds, charges, spacing and transparent preview edges.
5. A pre-existing unsaved drawing remains unchanged.

Then try the same server from the desired assistant application using [desktop setup](MCP_CLIENTS.md). A terminal permission does not establish that the assistant app has the same permission. MCP should return structured results with no terminal animation.

## Record locally

- Candidate wheel SHA-256:
- macOS version and Apple Silicon/Intel:
- ChemDraw full build:
- Python version (reported in first-run.json):
- First-run status and local report path:
- Visual review observations:
- Pre-existing document preservation:
- Assistant/client tested, if any:
- Errors and their exact text:

Keep detailed reports local until inspected for private paths or drawing content. A failure is useful evidence; do not disable validation to get a passing result. See [release gates](RELEASE_CHECKLIST.md) for full-suite acceptance.
