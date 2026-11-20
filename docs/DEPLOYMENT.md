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

## Optional sandbox smoke (read-only, opt-in)

Live Account Engagement sandbox checks are **disabled by default**. They require
sandbox credentials, stay read-only, and never print tokens or PII.

### Prerequisites

1. Salesforce **sandbox** External Client App / Connected App with callback  
   `http://127.0.0.1:8765/oauth/callback` (HTTP loopback only).
2. Env (sandbox only — never production write flags):

```env
SF_CLIENT_ID=...
SF_CLIENT_SECRET=...          # if required by the app
SF_LOGIN_URL=https://test.salesforce.com
SF_REDIRECT_URI=http://127.0.0.1:8765/oauth/callback
PARDOT_BUSINESS_UNIT_ID=0Uv...
PARDOT_API_BASE_URL=https://pi.demo.pardot.com
AE_READ_ONLY=true
AE_ALLOW_CREATE=false
AE_ALLOW_UPDATE=false
AE_ALLOW_DELETE=false
```

### Commands

```bash
# 1) Interactive OAuth (PKCE). Tokens land in SF_TOKEN_STORE_PATH (mode 0600).
salesforce-account-engagement-mcp auth login

# 2) Offline health (config + local token presence; no Salesforce call required
#    when using --offline).
python scripts/health_check.py --offline

# 3) Opt-in live read-only smoke (connection + 1 prospect/campaign/list + refresh).
#    Explicit flag required. Do not run until sandbox creds + authorization exist.
RUN_AE_INTEGRATION=1 AE_READ_ONLY=true \
  pytest tests/integration/test_sandbox_optional.py -q
```

### Safety

- Skipped unless `RUN_AE_INTEGRATION=1`.
- Asserts `AE_READ_ONLY=true` and create/update/delete remain off.
- Queries use `fields=id` + `limit=1` only; assertions keep sanitized pass/fail
  summaries (counts / ok flags) — no emails, names, or token values printed.
- Do **not** enable this job in CI without a dedicated sandbox secret store and
  explicit approval.
