"""Visitor tools (IP addresses redacted by default)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import VISITOR_DEFAULT_FIELDS
from ..runtime import drop_none

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_visitors")
    async def ae_list_visitors(
        fields: str = VISITOR_DEFAULT_FIELDS,
        limit: int = 50,
        prospect_id: int | None = None,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """List visitors. IP addresses are redacted in tool output for privacy."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "visitors",
                fields=fields,
                filters=drop_none({"prospectId": prospect_id}),
                limit=limit,
                next_page_token=next_page_token,
            )
            result["privacy_note"] = "ipAddress fields are redacted in MCP responses."
            return runtime.ok(
                result, tool_name="ae_list_visitors", operation="read", record_type="visitor"
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_visitors", operation="read")

    @server.tool(name="ae_get_visitor")
    async def ae_get_visitor(
        visitor_id: int,
        fields: str = VISITOR_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Get a visitor by ID. Sensitive fields such as ipAddress are redacted."""
        try:
            runtime.guard_read()
            result = await runtime.client.read("visitors", visitor_id, fields=fields)
            result["privacy_note"] = "ipAddress fields are redacted in MCP responses."
            return runtime.ok(
                result,
                tool_name="ae_get_visitor",
                operation="read",
                record_type="visitor",
                record_id=visitor_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc, tool_name="ae_get_visitor", operation="read", record_id=visitor_id
            )
