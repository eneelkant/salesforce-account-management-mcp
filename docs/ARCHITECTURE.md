# Architecture

## Overview

This repository implements a **single shared MCP server** for Salesforce Marketing Cloud Account Engagement (formerly Pardot). Cursor, Claude Desktop, ChatGPT, and Gemini hosts all consume the same tools, schemas, and business logic. Only the transport (stdio vs Streamable HTTP) and deployment topology differ.

```text
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Cursor    │  │   Claude    │  │  ChatGPT    │  │   Gemini    │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │ stdio          │ stdio          │ HTTP           │ stdio/HTTP*
       └────────────────┴───────────┬────┴────────────────┘
                                    ▼
                     ┌──────────────────────────┐
                     │  MCPServer (official SDK)│
                     │  shared tool registry    │
                     └────────────┬─────────────┘
                                  ▼
                     ┌──────────────────────────┐
                     │  AppRuntime              │
                     │  permissions / audit /   │
                     │  redaction / confirmation│
                     └────────────┬─────────────┘
                                  ▼
                     ┌──────────────────────────┐
                     │  AccountEngagementClient │
                     │  OAuth token manager     │
                     │  httpx + concurrency=5   │
                     └────────────┬─────────────┘
                                  ▼
                     Salesforce OAuth + AE API v5
```

\*Gemini MCP support depends on the specific host product.

## Package layout

| Path | Responsibility |
|------|----------------|
| `auth/` | OAuth (PKCE + refresh), token store, Business Unit validation |
| `client/` | Official AE API v5 HTTP client, pagination, retries, errors |
| `models/` | Pydantic inputs / default field sets |
| `tools/` | MCP tools grouped by domain |
| `security/` | Read-only defaults, confirmations, redaction, audit |
| `transports/` | stdio and Streamable HTTP runners |

## Design rules

1. **Official API v5 only** — no v3/v4 paths.
2. **No fake tools** — unsupported features return explicit unsupported status.
3. **Default read-only** — writes require env opt-in + confirmation.
4. **Safe pagination** — `nextPageUrl` host/scheme validated before follow.
5. **Redaction** — passwords, tokens, IP addresses never returned to the model.
