"""Tag tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import TAG_DEFAULT_FIELDS
from ..runtime import drop_none

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_tags")
    async def ae_list_tags(
        fields: str = TAG_DEFAULT_FIELDS,
        limit: int = 100,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """List tags (GET /api/v5/objects/tags)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "tags",
                fields=fields,
                limit=limit,
                next_page_token=next_page_token,
            )
            return runtime.ok(result, tool_name="ae_list_tags", operation="read", record_type="tag")
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_tags", operation="read")

    @server.tool(name="ae_search_tags")
    async def ae_search_tags(
        name: str | None = None,
        fields: str = TAG_DEFAULT_FIELDS,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search tags by name filter when supported."""
        try:
            runtime.guard_read()
            filters = drop_none({"name": name})
            result = await runtime.client.query(
                "tags",
                fields=fields,
                filters=filters,
                limit=limit,
            )
            result["filters_applied"] = filters
            return runtime.ok(
                result, tool_name="ae_search_tags", operation="read", record_type="tag"
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_search_tags", operation="read")

    @server.tool(name="ae_create_tag")
    async def ae_create_tag(
        name: str,
        confirm: bool = False,
        fields: str = TAG_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Create a tag (POST /api/v5/objects/tags)."""
        try:
            runtime.guard_create(confirm=confirm, target=f"tag name={name}")
            result = await runtime.client.create("tags", {"name": name}, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_create_tag",
                operation="create",
                record_type="tag",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_create_tag", operation="create")
