# Desktop assistant setup

The CLI and MCP server call the same native workflow code. A local assistant can ask ChemDraw to make an editable drawing without the user typing individual terminal commands. The MCP server must run on the Mac with licensed ChemDraw and the relevant Automation permission. This project exposes local stdio, not a remotely reachable HTTP service.

## Install the server once

In a checkout:

```sh
uv sync --locked --extra chemistry
```

Use the absolute installed executable path in client settings. This avoids dependence on a GUI application's shell PATH, current directory or startup-time package downloads:

```text
/absolute/path/chemdraw-mcp-macos/.venv/bin/chemdraw-mcp-macos
```

Do not point the client at `chemdraw-mac first-run`: that is a one-shot CLI command, not the server. `chemdraw-mac serve` is an alternative stdio server entry point.

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

Use the client's developer configuration entry point and restart/reload it after changes. Preserve unrelated server entries. This repository does not yet distribute a one-click desktop-extension bundle. Organization policy may restrict local servers.

## Check the connection

First ask the assistant to call `chemdraw_doctor`, a diagnostic check. When you want an actual drawing, ask it to call `chemdraw_first_run`. That call creates the fixed caffeine/aspirin example and returns editable CDXML, native SVG/PNG, a review page and machine checks. The final drawing remains open in ChemDraw.

MCP calls produce no terminal animation and do not automatically launch the browser. Whether a preview is displayed inline depends on the client; the returned local review/file paths remain available. These setup instructions establish the local connection route, not a claim that every desktop app/version has undergone end-to-end acceptance testing here.

Web-only sessions do not gain access to this Mac just because the local server is configured. Do not expose the desktop bridge to the public network as a workaround.
