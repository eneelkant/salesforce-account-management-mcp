"""List management tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import LIST_DEFAULT_FIELDS
from ..runtime import drop_none

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_lists")
    async def ae_list_lists(
        fields: str = LIST_DEFAULT_FIELDS,
        limit: int = 50,
        order_by: str = "id ASC",
        next_page_token: str | None = None,
        is_dynamic: bool | None = None,
    ) -> dict[str, Any]:
        """List marketing lists (static and dynamic metadata via isDynamic where available)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "lists",
                fields=fields,
                filters=drop_none({"isDynamic": is_dynamic}),
                limit=limit,
                order_by=order_by,
                next_page_token=next_page_token,
            )
            return runtime.ok(
                result, tool_name="ae_list_lists", operation="read", record_type="list"
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_lists", operation="read")

    @server.tool(name="ae_get_list")
    async def ae_get_list(list_id: int, fields: str = LIST_DEFAULT_FIELDS) -> dict[str, Any]:
        """Get a single list by ID including folder relationship fields when requested."""
        try:
            runtime.guard_read()
            result = await runtime.client.read("lists", list_id, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_get_list",
                operation="read",
                record_type="list",
                record_id=list_id,
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_list", operation="read", record_id=list_id)

    @server.tool(name="ae_search_lists")
    async def ae_search_lists(
        fields: str = LIST_DEFAULT_FIELDS,
        limit: int = 50,
        name: str | None = None,
        updated_at_after: str | None = None,
        is_dynamic: bool | None = None,
    ) -> dict[str, Any]:
        """Search lists with documented filters."""
        try:
            runtime.guard_read()
            filters = drop_none(
                {"name": name, "updatedAtAfter": updated_at_after, "isDynamic": is_dynamic}
            )
            result = await runtime.client.query(
                "lists",
                fields=fields,
                filters=filters,
                limit=limit,
                order_by="updatedAt DESC",
            )
            result["filters_applied"] = filters
            return runtime.ok(
                result, tool_name="ae_search_lists", operation="read", record_type="list"
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_search_lists", operation="read")

    @server.tool(name="ae_create_list")
    async def ae_create_list(
        name: str,
        confirm: bool = False,
        title: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
        folder_id: int | None = None,
        fields: str = LIST_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Create a list (POST /api/v5/objects/lists)."""
        try:
            runtime.guard_create(confirm=confirm, target=f"list name={name}")
            body = drop_none(
                {
                    "name": name,
                    "title": title,
                    "description": description,
                    "isPublic": is_public,
                    "folderId": folder_id,
                }
            )
            result = await runtime.client.create("lists", body, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_create_list",
                operation="create",
                record_type="list",
                record_id=(result or {}).get("id") if isinstance(result, dict) else None,
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_create_list", operation="create")

    @server.tool(name="ae_update_list")
    async def ae_update_list(
        list_id: int,
        confirm: bool = False,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
        folder_id: int | None = None,
        fields: str = LIST_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Update a list (PATCH /api/v5/objects/lists/{id})."""
        try:
            runtime.guard_update(confirm=confirm, target=f"list id={list_id}")
            body = drop_none(
                {
                    "name": name,
                    "title": title,
                    "description": description,
                    "isPublic": is_public,
                    "folderId": folder_id,
                }
            )
            if not body:
                return {"error": "No fields provided to update.", "list_id": list_id}
            result = await runtime.client.update("lists", list_id, body, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_update_list",
                operation="update",
                record_type="list",
                record_id=list_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc, tool_name="ae_update_list", operation="update", record_id=list_id
            )

    @server.tool(name="ae_delete_list")
    async def ae_delete_list(
        list_id: int,
        confirm: bool = False,
        confirm_id: int | None = None,
    ) -> dict[str, Any]:
        """Delete a list. Requires AE_ALLOW_DELETE and confirm_id == list_id."""
        try:
            runtime.guard_delete(
                confirm=confirm,
                target=f"list id={list_id}",
                record_id=list_id,
                confirm_id=confirm_id,
            )
            result = await runtime.client.delete("lists", list_id)
            return runtime.ok(
                {"deleted": True, "list_id": list_id, **(result or {})},
                tool_name="ae_delete_list",
                operation="delete",
                record_type="list",
                record_id=list_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc, tool_name="ae_delete_list", operation="delete", record_id=list_id
            )
