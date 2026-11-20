# Security Model

## Defaults

| Setting | Default | Meaning |
|---------|---------|---------|
| `AE_READ_ONLY` | `true` | All create/update/delete blocked |
| `AE_ALLOW_CREATE` | `false` | Opt-in create |
| `AE_ALLOW_UPDATE` | `false` | Opt-in update |
| `AE_ALLOW_DELETE` | `false` | Separate delete opt-in |
| `AE_REQUIRE_WRITE_CONFIRMATION` | `true` | `confirm=true` required |
| `AE_REQUIRE_DELETE_CONFIRMATION` | `true` | `confirm=true` + matching `confirm_id` |
| `AE_MAX_RECORDS` | `200` | Per-request ceiling (max 1000) |
| `AE_MAX_CONCURRENT_REQUESTS` | `5` | AE concurrency limit |
| `MCP_TRANSPORT` | `stdio` | Local process transport (no remote HTTP) |

When `AE_READ_ONLY=true`, create/update/delete flags are forced off.

## Local STDIO vs remote Streamable HTTP

| Mode | Auth model |
|------|------------|
| **STDIO** (Cursor, Claude Desktop local) | Process isolation. Host launches the MCP; no HTTP listener. Salesforce tokens stay in the process/env/token store. |
| **Streamable HTTP** (ChatGPT / remote Gemini / remote Claude) | **Fail-closed.** Server refuses to start unless `MCP_HTTP_AUTH_MODE` and the matching shared secret are configured. MCP clients must send `Authorization: Bearer <secret>`. Salesforce tokens are **never** accepted from MCP clients and are never returned in tool output. |

### Streamable HTTP auth modes

```env
MCP_TRANSPORT=streamable-http
MCP_HTTP_AUTH_MODE=bearer          # or proxy
MCP_HTTP_BEARER_TOKEN=...          # required for bearer
# OR
MCP_HTTP_PROXY_SHARED_SECRET=...   # required for proxy
```

- **bearer** — MCP clients (or your connector config) send `Authorization: Bearer <MCP_HTTP_BEARER_TOKEN>`.
- **proxy** — An authenticated reverse proxy terminates user auth and injects `Authorization: Bearer <MCP_HTTP_PROXY_SHARED_SECRET>` to the MCP process. The MCP trusts only that shared secret, not end-user Salesforce tokens from the network.

Missing mode/secret → startup error. Unauthenticated remote MCP endpoints that could expose Account Engagement access are not permitted.

Optional:

```env
MCP_HTTP_RESOURCE_URL=https://your.host/mcp   # audience / protected-resource metadata
MCP_HTTP_ISSUER_URL=https://your-issuer.example
```

## Salesforce credential handling

- Store Salesforce client secrets and refresh tokens only in server-side env / `SF_TOKEN_STORE_PATH`.
- Do not place Salesforce tokens in Cursor/ChatGPT/Gemini connector headers for remote HTTP.
- Tool redaction strips passwords, tokens, and visitor IP addresses.
- Logs redact bearer tokens and client secrets.

## Tool / API protections

- No silent deletes or bulk destructive tools
- List membership removal requires membership ID + delete confirmation
- Free-text prospect/visitor fields marked as untrusted data (prompt-injection resistance)
- Audit log records tool name, operation, record type/id, success — never secrets
- Pagination: prefer `nextPageToken`; `nextPageUrl` followed only after HTTPS + allowlisted AE host + `/api/v5/` validation
- Non-idempotent POSTs are not auto-retried

## Enabling writes

```env
AE_READ_ONLY=false
AE_ALLOW_CREATE=true
AE_ALLOW_UPDATE=true
# Delete is separate:
AE_ALLOW_DELETE=true
```

Then pass `confirm=true` (and for deletes, `confirm_id` equal to the target id).
