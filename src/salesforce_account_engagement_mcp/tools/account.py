"""Account / Business Unit / connectivity tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..auth.business_unit import business_unit_info

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_get_account")
    async def ae_get_account(
        fields: str = "id,company,website,addressOne,city,state,zip,country,phone",
    ) -> dict[str, Any]:
        """Retrieve Account Engagement account configuration (singleton account object).

        Uses GET /api/v5/objects/account. Returns account-level settings for the
        authenticated Business Unit. Distinguishes AE account data from Salesforce CRM Account.
        """
        try:
            runtime.guard_read()
            raw = await runtime.client.request(
                "GET",
                runtime.client.object_url("account"),
                params={"fields": fields},
            )
            payload: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {"value": raw}
            payload["object_note"] = (
                "This is the Account Engagement account singleton, not a Salesforce CRM Account."
            )
            return runtime.ok(
                payload, tool_name="ae_get_account", operation="read", record_type="account"
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_account", operation="read")

    @server.tool(name="ae_get_business_unit_info")
    async def ae_get_business_unit_info() -> dict[str, Any]:
        """Return configured Business Unit ID and environment metadata (no secrets)."""
        try:
            info: dict[str, Any] = dict(
                business_unit_info(
                    runtime.settings.pardot_business_unit_id,
                    api_base_url=runtime.settings.pardot_api_base_url,
                    login_url=runtime.settings.sf_login_url,
                )
            )
            info["auth"] = runtime.token_manager.snapshot()
            info["permissions"] = runtime.permissions.status()
            return runtime.ok(
                info,
                tool_name="ae_get_business_unit_info",
                operation="read",
                record_type="business_unit",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_business_unit_info", operation="read")

    @server.tool(name="ae_check_connection")
    async def ae_check_connection() -> dict[str, Any]:
        """Verify Salesforce OAuth + Business Unit connectivity with a minimal prospects query."""
        try:
            runtime.guard_read()
            result = await runtime.client.check_connection()
            result["auth"] = runtime.token_manager.snapshot()
            return runtime.ok(
                result,
                tool_name="ae_check_connection",
                operation="read",
                record_type="connection",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_check_connection", operation="read")

    @server.tool(name="ae_get_api_health")
    async def ae_get_api_health() -> dict[str, Any]:
        """Return API health summary: auth readiness, BU config, permission mode, last usage header."""
        try:
            auth = runtime.token_manager.snapshot()
            payload = {
                "auth_ready": runtime.settings.auth_ready(),
                "auth": auth,
                "business_unit_configured": bool(runtime.settings.pardot_business_unit_id),
                "api_base_url": runtime.settings.pardot_api_base_url,
                "api_version": runtime.settings.pardot_api_version,
                "permissions": runtime.permissions.status(),
                "max_concurrent_requests": runtime.settings.ae_max_concurrent_requests,
                "max_records": runtime.settings.ae_max_records,
                "last_api_usage": runtime.client.last_api_usage,
                "data_source": "local_configuration_and_runtime",
            }
            return runtime.ok(payload, tool_name="ae_get_api_health", operation="read")
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_api_health", operation="read")

    @server.tool(name="ae_get_api_usage_status")
    async def ae_get_api_usage_status() -> dict[str, Any]:
        """Return the latest x-api-usage header value after a lightweight API call.

        Account Engagement returns usage as calls-made/daily-max when
        X-Return-Api-Usage is set. This tool performs a limit=1 prospects query
        to refresh the header.
        """
        try:
            runtime.guard_read()
            await runtime.client.query("prospects", fields=["id"], limit=1)
            usage = runtime.client.last_api_usage
            payload: dict[str, Any] = {
                "api_usage": usage,
                "data_source": "salesforce_account_engagement_api_v5",
                "header": "x-api-usage",
                "interpretation": (
                    "Value format is typically <calls_made>/<daily_limit> when present."
                ),
            }
            if not usage:
                payload["limitations"] = [
                    "No x-api-usage header was returned on the probe request."
                ]
            return runtime.ok(payload, tool_name="ae_get_api_usage_status", operation="read")
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_api_usage_status", operation="read")
