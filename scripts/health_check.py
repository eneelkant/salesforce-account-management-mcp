#!/usr/bin/env python3
"""Health / configuration check for local and container deployments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from a checkout without installation.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def offline_check() -> dict[str, object]:
    from salesforce_account_engagement_mcp import __version__
    from salesforce_account_engagement_mcp.config import Settings
    from salesforce_account_engagement_mcp.server import create_server

    settings = Settings()
    server, runtime = create_server(settings)
    return {
        "ok": True,
        "version": __version__,
        "auth_ready": settings.auth_ready(),
        "business_unit_configured": bool(settings.pardot_business_unit_id),
        "read_only": settings.ae_read_only,
        "transport": settings.mcp_transport,
        "permissions": runtime.permissions.status(),
        "server_name": server.name,
    }


async def live_check() -> dict[str, object]:
    from salesforce_account_engagement_mcp.config import Settings
    from salesforce_account_engagement_mcp.runtime import AppRuntime

    settings = Settings()
    runtime = AppRuntime.from_settings(settings)
    try:
        result = await runtime.client.check_connection()
        return {"ok": True, "connection": result, "auth": runtime.token_manager.snapshot()}
    finally:
        await runtime.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Account Engagement MCP health check")
    parser.add_argument("--offline", action="store_true", help="Validate config/server only")
    parser.add_argument("--live", action="store_true", help="Call AE API (requires credentials)")
    args = parser.parse_args()

    if args.live:
        import asyncio

        payload = asyncio.run(live_check())
    else:
        payload = offline_check()

    print(json.dumps(payload, indent=2, default=str))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
