# Troubleshooting

## Authentication failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Missing Business Unit ID | Env not set / invalid format | Must be 18 chars starting with `0Uv` |
| 401 from AE API | Expired access token, no refresh | Configure `SF_REFRESH_TOKEN` + `SF_CLIENT_ID` |
| OAuth scope errors | Missing `pardot_api` | Update External Client App scopes |
| Sandbox calls hit production host | Wrong base URL | Use `https://pi.demo.pardot.com` with `https://test.salesforce.com` |

## Permission errors from tools

- Default mode is read-only. Set `AE_READ_ONLY=false` and enable the specific allow flags.
- Writes require `confirm=true`.
- Deletes require `confirm_id` matching the target record id.

## Pagination errors

- `nextPageToken` expires after ~4 hours — restart the query.
- Unsafe `nextPageUrl` hosts are rejected by design.
- Offset is deprecated; prefer page tokens.

## API limits

- Concurrency capped at 5 (`AE_MAX_CONCURRENT_REQUESTS`).
- Daily limit surfaced via `x-api-usage` (`ae_get_api_usage_status`).
- RateLimitError returns actionable messaging — do not retry blindly.

## Client cannot see tools

- Confirm the process starts (`salesforce-account-engagement-mcp`).
- Check MCP JSON path / Python interpreter.
- Run `ae_get_tool_catalogue` once connected.

## Unsupported features

- Engagement Studio admin → `ae_engagement_studio_status`
- External activities → `ae_external_activities_status`
- These intentionally do **not** return simulated data.
