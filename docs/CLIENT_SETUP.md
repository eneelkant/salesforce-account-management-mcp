# Client Setup

All clients use the **same tool registry**. Only transport and host configuration differ.

## Cursor

1. Install the package (`scripts/setup.sh` or `pip install -e .`).
2. Copy `examples/cursor-mcp.json` into your Cursor MCP settings.
3. Replace `/PATH/TO/...` and credential placeholders.
4. Keep secrets in env vars / local overrides — never commit them.
5. Restart Cursor and verify tools appear (e.g. `ae_check_connection`).

STDIO is the recommended local transport. Optional Streamable HTTP:

```bash
salesforce-account-engagement-mcp --transport streamable-http --port 8000
```

## Claude Desktop

1. Use `examples/claude-desktop-config.json`.
2. Point `cwd` / command at your virtualenv Python or installed console script.
3. STDIO transport.
4. Confirm Claude can list tools after restart.

Remote Claude-compatible MCP hosts can use Streamable HTTP when configured by the host.

## ChatGPT

1. Deploy the Docker image or process with `MCP_TRANSPORT=streamable-http`.
2. Terminate TLS at your reverse proxy; expose `https://YOUR_HOST/mcp`.
3. Register a custom connector / developer-mode MCP pointing at that URL.
4. Keep Salesforce OAuth credentials on the server; do not paste refresh tokens into ChatGPT headers.
5. See `examples/chatgpt-remote-mcp.json`.

ChatGPT account features and connector availability vary; HTTPS reachability is a deployment prerequisite.

## Google Gemini

1. Prefer STDIO where the Gemini host can launch local MCP processes (`examples/gemini-mcp-config.json`).
2. For remote Gemini connectors that support Streamable HTTP, reuse the ChatGPT remote pattern.
3. **Do not assume every Gemini product surface supports the same MCP transport.**

## Shared verification

```bash
python scripts/health_check.py --offline
# with credentials:
python scripts/health_check.py --live
```
