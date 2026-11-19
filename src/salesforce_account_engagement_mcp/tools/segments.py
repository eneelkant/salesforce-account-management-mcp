"""Segmentation helpers — only confirmed API v5 capabilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import LIST_DEFAULT_FIELDS, TAG_DEFAULT_FIELDS

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


_ENGAGEMENT_STUDIO_UNSUPPORTED = {
    "supported": False,
    "feature": "Engagement Studio programs",
    "reason": (
        "Engagement Studio program administration is not available as a fully documented "
        "Account Engagement API v5 object surface comparable to lists/prospects. "
        "This MCP does not simulate Engagement Studio controls."
    ),
    "limitation_source": "api",
    "alternatives": [
        "Use ae_list_lists / ae_get_list for static and dynamic list metadata.",
        "Use ae_list_tags / ae_create_tag for tag-based organization.",
        "Manage Engagement Studio in the Account Engagement Lightning UI.",
    ],
}


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_dynamic_lists")
    async def ae_list_dynamic_lists(
        fields: str = LIST_DEFAULT_FIELDS,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List lists where isDynamic=true when the field/filter is accepted by API v5."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "lists",
                fields=fields,
                filters={"isDynamic": True},
                limit=limit,
            )
            result["note"] = (
                "Dynamic list membership rules are not fully administrable via this MCP; "
                "only list metadata from API v5 is returned."
            )
            return runtime.ok(
                result,
                tool_name="ae_list_dynamic_lists",
                operation="read",
                record_type="list",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_dynamic_lists", operation="read")

    @server.tool(name="ae_list_static_lists")
    async def ae_list_static_lists(
        fields: str = LIST_DEFAULT_FIELDS,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List lists where isDynamic=false when supported."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "lists",
                fields=fields,
                filters={"isDynamic": False},
                limit=limit,
            )
            return runtime.ok(
                result,
                tool_name="ae_list_static_lists",
                operation="read",
                record_type="list",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_static_lists", operation="read")

    @server.tool(name="ae_list_segmentation_tags")
    async def ae_list_segmentation_tags(
        fields: str = TAG_DEFAULT_FIELDS,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List segmentation tags (alias of tag query for marketing workflows)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query("tags", fields=fields, limit=limit)
            return runtime.ok(
                result,
                tool_name="ae_list_segmentation_tags",
                operation="read",
                record_type="tag",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_segmentation_tags", operation="read")

    @server.tool(name="ae_engagement_studio_status")
    async def ae_engagement_studio_status() -> dict[str, Any]:
        """Explain Engagement Studio support status (unsupported in this MCP / API gap)."""
        return runtime.ok(
            _ENGAGEMENT_STUDIO_UNSUPPORTED,
            tool_name="ae_engagement_studio_status",
            operation="read",
            record_type="engagement_studio",
        )

    @server.tool(name="ae_external_activities_status")
    async def ae_external_activities_status() -> dict[str, Any]:
        """Report external activities support status.

        External Activity endpoints vary by org edition and are not enabled here until
        verified for the target Business Unit. This tool refuses to fabricate results.
        """
        return runtime.ok(
            {
                "supported": False,
                "feature": "External Activities",
                "status": "pending_verification",
                "reason": (
                    "External activity APIs are not enabled in this MCP until verified "
                    "against the official v5 docs for the target org. No simulated data."
                ),
                "limitation_source": "mcp_verification",
            },
            tool_name="ae_external_activities_status",
            operation="read",
            record_type="external_activity",
        )
