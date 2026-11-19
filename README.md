# Salesforce Account Engagement MCP

Production-ready [Model Context Protocol](https://modelcontextprotocol.io) server for **Salesforce Marketing Cloud Account Engagement** (formerly Pardot).

One shared MCP implementation powers:

1. **Cursor**
2. **ChatGPT** (remote Streamable HTTP)
3. **Google Gemini** (host-dependent)
4. **Claude Desktop** / Claude-compatible MCP clients

Built on the official MCP Python SDK (`MCPServer`, formerly FastMCP), `httpx`, and Pydantic. Talks exclusively to the **Account Engagement REST API v5**.

> This expands the original repository goal of configuring Salesforce External Client Apps and AI connectors into a full, tested MCP server.

## Key capabilities

- Salesforce OAuth (Authorization Code + PKCE, refresh tokens, sandbox/production/My Domain)
- Business Unit ID validation (`0Uv…`)
- Async AE API v5 client with concurrency limit (5), retries, safe pagination
- Prospects, campaigns, lists, memberships, visitors, activities, custom fields, forms, tags, list emails, landing pages
- Source-grounded analytics (calculated vs API-supplied metrics labeled)
- **Default read-only** security with explicit write/delete opt-in and confirmations
- STDIO + Streamable HTTP transports
- Docker, CI, and client configuration examples

## Architecture

```text
AI clients → MCP (stdio | streamable-http) → shared tools → AppRuntime
    → OAuth token manager → Account Engagement API v5
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Requirements

- Python 3.12+
- Salesforce org with Account Engagement
- External Client App / Connected App with `pardot_api` (+ refresh) scopes
- SSO-enabled user with AE access
- Business Unit ID from Setup → Business Unit Setup

## Quick start

```bash
./scripts/setup.sh
# edit .env with SF_CLIENT_ID, SF_CLIENT_SECRET, SF_REFRESH_TOKEN, PARDOT_BUSINESS_UNIT_ID
source .venv/bin/activate
salesforce-account-engagement-mcp
```

Windows: `./scripts/setup.ps1`

## Environment variables

Copy [`.env.example`](.env.example). Important keys:

| Variable | Purpose |
|----------|---------|
| `SF_CLIENT_ID` / `SF_CLIENT_SECRET` | External Client App credentials |
| `SF_LOGIN_URL` | `https://login.salesforce.com` or `https://test.salesforce.com` |
| `SF_REFRESH_TOKEN` / `SF_ACCESS_TOKEN` | OAuth tokens (prefer refresh) |
| `PARDOT_BUSINESS_UNIT_ID` | `0Uv…` 18-character ID |
| `PARDOT_API_BASE_URL` | `https://pi.pardot.com` or `https://pi.demo.pardot.com` |
| `AE_READ_ONLY` | Default `true` |
| `MCP_TRANSPORT` | `stdio` or `streamable-http` |

Full auth guide: [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

## MCP tool catalogue (summary)

| Area | Examples |
|------|----------|
| Account / health | `ae_get_account`, `ae_check_connection`, `ae_get_api_usage_status` |
| Prospects | `ae_list_prospects`, `ae_get_prospect`, `ae_search_prospects`, `ae_create_prospect`, `ae_update_prospect`, `ae_upsert_prospect`, `ae_delete_prospect` |
| Campaigns | `ae_list_campaigns`, `ae_get_campaign`, `ae_get_campaign_performance` |
| Lists | `ae_list_lists`, `ae_create_list`, `ae_add_prospect_to_list`, … |
| Activities | `ae_list_visitor_activities`, `ae_get_prospect_activity_summary` |
| Assets | `ae_list_forms`, `ae_list_list_emails`, `ae_list_landing_pages`, `ae_list_tags` |
| Analytics | `ae_get_prospect_engagement_summary`, `ae_find_duplicate_prospects`, … |
| Explicit gaps | `ae_engagement_studio_status`, `ae_external_activities_status` |

Complete matrix: [docs/API_COVERAGE.md](docs/API_COVERAGE.md).

## Client configuration

| Client | Example |
|--------|---------|
| Cursor | [examples/cursor-mcp.json](examples/cursor-mcp.json) |
| Claude Desktop | [examples/claude-desktop-config.json](examples/claude-desktop-config.json) |
| ChatGPT remote | [examples/chatgpt-remote-mcp.json](examples/chatgpt-remote-mcp.json) |
| Gemini | [examples/gemini-mcp-config.json](examples/gemini-mcp-config.json) |

Details: [docs/CLIENT_SETUP.md](docs/CLIENT_SETUP.md).

## Docker

```bash
docker compose up --build
# listens on http://localhost:8000/mcp (Streamable HTTP)
```

Non-root user, read-only defaults, healthcheck included. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Security model

- Default **read-only**
- Writes require `AE_READ_ONLY=false` + allow flags + `confirm=true`
- Deletes additionally require matching `confirm_id`
- Passwords, tokens, and IP addresses redacted
- Untrusted free-text fields annotated for prompt-injection resistance

See [docs/SECURITY.md](docs/SECURITY.md).

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests && ruff format --check src tests
mypy src
python scripts/health_check.py --offline
```

Optional live sandbox tests:

```bash
RUN_AE_INTEGRATION=1 pytest tests/integration -m integration
```

## API limitations

- API v5 only (not v3/v4)
- Campaigns are read/query in v5 (no create)
- Page tokens expire after ~4 hours; 100k record pagination ceiling
- Engagement Studio administration is **not** exposed (API/MCP gap)
- List-email **send** is intentionally not exposed
- Some prospect filters (name/company/score) are applied client-side and labeled

## Documentation index

- [Architecture](docs/ARCHITECTURE.md)
- [Authentication](docs/AUTHENTICATION.md)
- [API coverage](docs/API_COVERAGE.md)
- [Security](docs/SECURITY.md)
- [Client setup](docs/CLIENT_SETUP.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [AGENTS.md](AGENTS.md)

## Contributing

1. Branch from `main` (e.g. `feature/...`)
2. Add tests for new tools
3. Update `docs/API_COVERAGE.md`
4. Keep secrets out of git
5. Open a PR — do not push to `main` directly

## License

MIT
