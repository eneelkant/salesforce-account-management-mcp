# Client Setup

All clients use the **same tool registry**. Only transport and authentication integration differ.

## Local vs remote auth

| Client pattern | Transport | Salesforce auth | MCP network auth |
|----------------|-----------|-----------------|------------------|
| Cursor / Claude Desktop local | STDIO | Server-side env / `auth login` | N/A (no HTTP) |
| ChatGPT / remote Gemini / remote Claude | Streamable HTTP | Server-side only | Required bearer or proxy-injected bearer |

## Cursor

1. Install the package (`scripts/setup.sh` or `pip install -e .`).
2. Run `salesforce-account-engagement-mcp auth login` once to obtain refresh tokens.
3. Copy `examples/cursor-mcp.json` into your Cursor MCP settings.
4. Replace `/PATH/TO/...` and credential placeholders.
5. Keep secrets in env vars / local overrides — never commit them.
6. Restart Cursor and verify tools appear (e.g. `ae_check_connection`).

STDIO is the recommended local transport.

## Claude Desktop

1. Use `examples/claude-desktop-config.json`.
2. Point `cwd` / command at your virtualenv Python or installed console script.
3. STDIO transport.
4. Confirm Claude can list tools after restart.

Remote Claude-compatible MCP hosts can use Streamable HTTP **only** with MCP HTTP auth configured (see below).

## ChatGPT (remote)

1. Deploy with `MCP_TRANSPORT=streamable-http` and `MCP_HTTP_AUTH_MODE=bearer` (or `proxy`).
2. Terminate TLS at your reverse proxy; expose `https://YOUR_HOST/mcp`.
3. Register a custom connector / developer-mode MCP pointing at that URL.
4. Configure the connector to send `Authorization: Bearer <MCP_HTTP_BEARER_TOKEN>`.
5. Keep Salesforce OAuth credentials on the server — do **not** paste Salesforce refresh tokens into ChatGPT headers.
6. See `examples/chatgpt-remote-mcp.json`.

## Google Gemini

1. Prefer STDIO where the Gemini host can launch local MCP processes (`examples/gemini-mcp-config.json`).
2. For remote Gemini connectors that support Streamable HTTP, reuse the ChatGPT remote pattern including MCP bearer auth.
3. **Do not assume every Gemini product surface supports the same MCP transport.**

## Shared verification

```bash
python scripts/health_check.py --offline
# with Salesforce credentials:
python scripts/health_check.py --live
```
