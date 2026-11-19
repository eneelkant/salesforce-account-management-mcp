# Authentication

Account Engagement API v5 requires:

1. A Salesforce OAuth access token
2. The Account Engagement Business Unit ID (`Pardot-Business-Unit-Id` header)
3. An SSO-enabled Salesforce user with Account Engagement access
4. The correct API host (`pi.pardot.com` or `pi.demo.pardot.com`)

## Salesforce External Client App

1. In Salesforce Setup, create an **External Client App** (or Connected App).
2. Enable OAuth.
3. Callback URL example: `http://localhost:8765/oauth/callback`
4. Selected OAuth scopes must include:
   - **Manage Pardot services** (`pardot_api`)
   - **Perform requests at any time** / refresh token (`refresh_token` / offline access)
   - Additional scopes only if required by your org policy
5. Capture Consumer Key (`SF_CLIENT_ID`) and Consumer Secret (`SF_CLIENT_SECRET`).

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

## Supported flows

- Authorization Code + PKCE (`SalesforceOAuthClient.build_authorization_url` / `exchange_code`)
- Refresh-token grant with locked refresh (no concurrent refresh races)
- Optional bootstrap via `SF_ACCESS_TOKEN` / `SF_REFRESH_TOKEN` env vars

Tokens are stored atomically in `SF_TOKEN_STORE_PATH` (default `.ae_tokens/tokens.json`) with `0600` permissions when the OS allows it.

## Request headers

```http
Authorization: Bearer <access_token>
Pardot-Business-Unit-Id: 0Uv...
Accept: application/json
Content-Type: application/json
X-Return-Api-Usage: true
```

Never commit tokens, client secrets, or production Business Unit credentials.
