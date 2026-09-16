# Desktop assistant setup

## Graphical installation

The **ChemDraw MCP for Mac** disk image offers Claude Desktop and Codex local
client checkboxes. Choose either or both; Finish installs one shared runtime and
registers only those choices. Restart selected assistants afterwards. No Terminal
or manual config editing is required. The optional neutral MCPB is for hosts
which support bundle installation, not a separate runtime for each model.
See [graphical installer details and acceptance limits](DESKTOP_INSTALLER.md).

The source/terminal path below remains independently usable and keeps the existing
terminal animation. It does not open the graphical setup app. Other local MCP
clients can use the same executable over stdio; their individual installation and
tool-call behavior must still be tested. Multiple registered clients currently
need sequential native access: disconnect the other ChemDraw server if busy.

The CLI and MCP server call the same native workflow code. A local assistant can ask ChemDraw to make an editable drawing without the user typing individual terminal commands. The MCP server must run on the Mac with licensed ChemDraw and the relevant Automation permission. This project exposes local stdio, not a remotely reachable HTTP service.

## Install the server once

For the guided terminal route, use [terminal installation](TERMINAL_INSTALL.md).
`chemdraw-mac setup --client codex` (and/or `--client claude`) prepares the add-in,
tests a live read and registers the installed executable with preserved settings.
The manual examples below are alternatives, not extra servers to add alongside
the helper's `glecko_chemdraw` entry.

In a checkout:

```sh
uv sync --locked --extra chemistry
```

Use the absolute installed executable path in client settings. This avoids dependence on a GUI application's shell PATH, current directory or startup-time package downloads:

```text
/absolute/path/chemdraw-mcp-macos/.venv/bin/chemdraw-mcp-macos
```

Do not point the client at `chemdraw-mac first-run`: that is a one-shot CLI command, not the server. `chemdraw-mac serve` is an alternative stdio server entry point.

## Choose core or full

The same executable supports `--profile core` for direct native document operations
or `--profile full` for core plus drawing workflows. Full remains the default.
Core does not require the chemistry extra: `uv sync --locked` is sufficient in a
checkout. These are tool profiles in one package, not separate servers to install.

In a client's JSON server entry, add:

```json
"args": ["--profile", "core"]
```

For a TOML server table, add:

```toml
args = ["--profile", "core"]
```

Use `full` or omit the arguments for the existing full toolset. Restart/reload the
configured server after changing the profile. In core mode, test the connection
with `chemdraw_doctor`; `chemdraw_first_run` is a full-profile workflow and is not
exposed. A core client can instead import a supplied structure and export it.
See [the architecture guide](ARCHITECTURE.md) for the exact core tool list and limits.

## Codex local clients

Codex uses `[mcp_servers.NAME]` tables in `~/.codex/config.toml`; local clients on the same host share MCP configuration. See the [official OpenAI documentation](https://developers.openai.com/codex/mcp/) for current desktop settings and configuration behavior.

Merge this table without replacing other settings:

```toml
[mcp_servers.chemdraw_native]
command = "/absolute/path/chemdraw-mcp-macos/.venv/bin/chemdraw-mcp-macos"
tool_timeout_sec = 300
```

Alternatively register the executable from a terminal:

```sh
codex mcp add chemdraw_native -- /absolute/path/chemdraw-mcp-macos/.venv/bin/chemdraw-mcp-macos
```

Then set an appropriate `tool_timeout_sec` in that server table; the CLI registration does not add the longer timeout. Native multi-structure jobs can exceed the client's default. A client timeout is not evidence that the AppleEvent was cancelled: inspect the application before another write. The server's native-operation timeout and uncertainty safeguards remain separate.

Refresh/restart the server in the app after updating the checkout so its tool list reflects the installed version. No settings are edited by `first-run`.

## Claude Desktop

Claude Desktop supports local MCP servers; see [Anthropic's local-server guide](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop). For manual server configuration, merge this entry into the existing desktop MCP JSON configuration, not into a remote-connector URL field:

```json
{
  "mcpServers": {
    "chemdraw_native": {
      "command": "/absolute/path/chemdraw-mcp-macos/.venv/bin/chemdraw-mcp-macos"
    }
  }
}
```

Use the client's developer configuration entry point and restart/reload it after changes. Preserve unrelated server entries. A local graphical `.mcpb` test bundle is now available; see [desktop installer](DESKTOP_INSTALLER.md) for its current signing and acceptance limits. Organization policy may restrict local servers.

## Check the connection

Generate and install this Mac's private API add-in first using [the test-on-Mac guide](TEST_ON_MAC.md). Open a blank ChemDraw document, then ask the assistant to call `chemdraw_doctor`. It checks an actual RDKit CDXML roundtrip and a live API read, reporting missing setup, a busy endpoint or no document separately. When you want an actual drawing, call `chemdraw_first_run`. It appends caffeine and aspirin and returns editable CDXML, native SVG/PNG and JSON checks. No HTML review or browser; the drawing remains open in ChemDraw.

MCP calls produce no terminal animation and do not launch the browser. Whether a preview is displayed inline depends on the client; returned local file paths remain available. Test clients one at a time, with the same server version, full tool profile and instructions. These setup instructions do not claim that every desktop app/version has undergone end-to-end acceptance here.

Web-only sessions do not gain access to this Mac just because the local server is configured. Do not expose the desktop bridge to the public network as a workaround.
