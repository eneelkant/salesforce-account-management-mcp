# Authentication

Account Engagement API v5 requires:

1. A Salesforce OAuth access token
2. The Account Engagement Business Unit ID (`Pardot-Business-Unit-Id` header)
3. An SSO-enabled Salesforce user with Account Engagement access
4. The correct API host (`pi.pardot.com` or `pi.demo.pardot.com`)

Separately, **remote MCP Streamable HTTP** requires MCP bearer/proxy auth (see [SECURITY.md](SECURITY.md)). That credential is not a Salesforce token.

## Salesforce External Client App

1. In Salesforce Setup, create an **External Client App** (or Connected App).
2. Enable OAuth.
3. Callback URL example: `http://127.0.0.1:8765/oauth/callback` (must match `SF_REDIRECT_URI`).  
   Local bootstrap accepts **HTTP loopback only** (`127.0.0.1` / `localhost` / `::1` with an explicit port). HTTPS redirect URIs are rejected unless you terminate TLS yourself outside this callback server.
4. Selected OAuth scopes (least privilege):
   - **Manage Pardot services** (`pardot_api`) — required
   - **Perform requests at any time** / refresh token (`refresh_token`) — required for refresh
   - Do **not** enable the broad Salesforce `api` scope unless your org explicitly needs Salesforce REST/SOAP beyond Account Engagement. Override only via `SF_OAUTH_SCOPES` if required.
5. Capture Consumer Key (`SF_CLIENT_ID`) and Consumer Secret (`SF_CLIENT_SECRET`).

Default requested scopes:

```env
SF_OAUTH_SCOPES=pardot_api refresh_token
```

## Business Unit ID

1. Salesforce Setup → Quick Find → **Business Unit Setup**
2. Copy the ID beginning with `0Uv` (18 characters)
3. Set `PARDOT_BUSINESS_UNIT_ID`

## Environments

| Account type | Salesforce login | AE API base |
|--------------|------------------|-------------|
| Production | `https://login.salesforce.com` | `https://pi.pardot.com` |
| Sandbox | `https://test.salesforce.com` | `https://pi.demo.pardot.com` |
| AE Developer Org | `https://login.salesforce.com` | `https://pi.demo.pardot.com` |
| My Domain | `https://YOURDOMAIN.my.salesforce.com` | as appropriate |

## OAuth bootstrap (Authorization Code + PKCE)

Preferred first-time login (local callback on localhost only):

```bash
# Requires SF_CLIENT_ID, SF_CLIENT_SECRET, SF_REDIRECT_URI, SF_LOGIN_URL
salesforce-account-engagement-mcp auth login
# or:
salesforce-account-engagement-mcp auth login --no-browser --timeout 300
```

What this does:

1. Generates PKCE `code_verifier` / S256 `code_challenge` and CSRF `state`
2. Persists pending PKCE state to `.ae_tokens/pkce_pending.json` (`0600`)
3. Prints (and optionally opens) the Salesforce authorize URL
4. Starts a one-shot localhost callback server matching `SF_REDIRECT_URI`
5. Validates `state`, exchanges `code` + `code_verifier`, deletes the pending PKCE file
6. Persists access/refresh tokens to `SF_TOKEN_STORE_PATH`

CLI errors and logs surface only a sanitized OAuth **error category** (for example
`access_denied`). Salesforce / IdP `error_description` text is never raised,
printed, or logged — it may contain sensitive provider detail.

## Other supported flows

- Refresh-token grant with locked refresh (no concurrent refresh races)
- Optional bootstrap via `SF_ACCESS_TOKEN` / `SF_REFRESH_TOKEN` env vars (still prefer `auth login`)

Tokens are stored atomically in `SF_TOKEN_STORE_PATH` (default `.ae_tokens/tokens.json`) with `0600` permissions when the OS allows it.

## Account Engagement request headers

```http
Authorization: Bearer <salesforce_access_token>
Pardot-Business-Unit-Id: 0Uv...
Accept: application/json
Content-Type: application/json
X-Return-Api-Usage: true
```

## Remote MCP client headers (Streamable HTTP)

```http
Authorization: Bearer <MCP_HTTP_BEARER_TOKEN or MCP_HTTP_PROXY_SHARED_SECRET>
```

Never send Salesforce refresh/access tokens as the MCP HTTP credential.

Never commit tokens, client secrets, or production Business Unit credentials.
