# Deployment

## Local STDIO

```bash
./scripts/setup.sh
source .venv/bin/activate
# one-time Salesforce login (PKCE):
salesforce-account-engagement-mcp auth login
salesforce-account-engagement-mcp serve
# or simply:
salesforce-account-engagement-mcp
```

STDIO does not open a network listener and does not require `MCP_HTTP_*` auth settings.

## Docker (Streamable HTTP) — auth required

```bash
cp .env.example .env   # fill Salesforce + MCP HTTP auth secrets locally
```

Minimum remote auth env:

```env
MCP_TRANSPORT=streamable-http
MCP_HTTP_AUTH_MODE=bearer
MCP_HTTP_BEARER_TOKEN=<long-random-secret>
# Salesforce tokens remain server-side:
SF_CLIENT_ID=...
SF_REFRESH_TOKEN=...
PARDOT_BUSINESS_UNIT_ID=0Uv...
AE_READ_ONLY=true
```

```bash
docker compose up --build
```

- Container runs as non-root user `mcpuser` (uid 10001)
- Default `AE_READ_ONLY=true`
- Process **refuses to start** if HTTP auth mode/secret is missing
- Healthcheck runs `scripts/health_check.py --offline`
- `STOPSIGNAL SIGTERM` for graceful shutdown

## Remote HTTPS + reverse proxy

1. Terminate TLS at nginx/Caddy/cloud LB.
2. Authenticate end users at the proxy (OIDC, mTLS, IP allowlist, etc.).
3. Prefer `MCP_HTTP_AUTH_MODE=proxy` and inject  
   `Authorization: Bearer <MCP_HTTP_PROXY_SHARED_SECRET>` to the upstream MCP.
4. Or use `bearer` and configure the remote MCP client with the shared bearer token.
5. Keep Salesforce OAuth credentials only on the MCP server / secret manager.
6. Point ChatGPT / remote Gemini connectors at `https://host/mcp` **with** the MCP Authorization header.

## Configuration validation

```bash
python scripts/health_check.py --offline
python -m json.tool examples/cursor-mcp.json
# Expect startup failure without auth when forcing HTTP:
MCP_TRANSPORT=streamable-http salesforce-account-engagement-mcp serve
```
