"""Custom field tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import CUSTOM_FIELD_DEFAULT_FIELDS
from ..runtime import drop_none

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_custom_fields")
    async def ae_list_custom_fields(
        fields: str = CUSTOM_FIELD_DEFAULT_FIELDS,
        limit: int = 100,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """List custom fields (GET /api/v5/objects/custom-fields)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "custom-fields",
                fields=fields,
                limit=limit,
                next_page_token=next_page_token,
            )
            return runtime.ok(
                result,
                tool_name="ae_list_custom_fields",
                operation="read",
                record_type="custom_field",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_custom_fields", operation="read")

    @server.tool(name="ae_get_custom_field")
    async def ae_get_custom_field(
        custom_field_id: int,
        fields: str = CUSTOM_FIELD_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Get a custom field by ID."""
        try:
            runtime.guard_read()
            result = await runtime.client.read("custom-fields", custom_field_id, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_get_custom_field",
                operation="read",
                record_type="custom_field",
                record_id=custom_field_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_custom_field",
                operation="read",
                record_id=custom_field_id,
            )

    @server.tool(name="ae_create_custom_field")
    async def ae_create_custom_field(
        name: str,
        field_id: str,
        field_type: str,
        confirm: bool = False,
        is_required: bool | None = None,
        is_record_multiple_responses: bool | None = None,
        is_use_values: bool | None = None,
        fields: str = CUSTOM_FIELD_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Create a custom field. field_type must be a documented AE type string."""
        try:
            runtime.guard_create(confirm=confirm, target=f"custom-field {field_id}")
            body = drop_none(
                {
                    "name": name,
                    "fieldId": field_id,
                    "type": field_type,
                    "isRequired": is_required,
                    "isRecordMultipleResponses": is_record_multiple_responses,
                    "isUseValues": is_use_values,
                }
            )
            result = await runtime.client.create("custom-fields", body, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_create_custom_field",
                operation="create",
                record_type="custom_field",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_create_custom_field", operation="create")

    @server.tool(name="ae_update_custom_field")
    async def ae_update_custom_field(
        custom_field_id: int,
        confirm: bool = False,
        name: str | None = None,
        is_required: bool | None = None,
        is_record_multiple_responses: bool | None = None,
        is_use_values: bool | None = None,
        fields: str = CUSTOM_FIELD_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Update a custom field (PATCH)."""
        try:
            runtime.guard_update(confirm=confirm, target=f"custom-field id={custom_field_id}")
            body = drop_none(
                {
                    "name": name,
                    "isRequired": is_required,
                    "isRecordMultipleResponses": is_record_multiple_responses,
                    "isUseValues": is_use_values,
                }
            )
            if not body:
                return {
                    "error": "No fields provided to update.",
                    "custom_field_id": custom_field_id,
                }
            result = await runtime.client.update(
                "custom-fields",
                custom_field_id,
                body,
                fields=fields,
            )
            return runtime.ok(
                result,
                tool_name="ae_update_custom_field",
                operation="update",
                record_type="custom_field",
                record_id=custom_field_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_update_custom_field",
                operation="update",
                record_id=custom_field_id,
            )

    @server.tool(name="ae_delete_custom_field")
    async def ae_delete_custom_field(
        custom_field_id: int,
        confirm: bool = False,
        confirm_id: int | None = None,
    ) -> dict[str, Any]:
        """Delete a custom field. Requires AE_ALLOW_DELETE and confirm_id match."""
        try:
            runtime.guard_delete(
                confirm=confirm,
                target=f"custom-field id={custom_field_id}",
                record_id=custom_field_id,
                confirm_id=confirm_id,
            )
            result = await runtime.client.delete("custom-fields", custom_field_id)
            return runtime.ok(
                {"deleted": True, "custom_field_id": custom_field_id, **(result or {})},
                tool_name="ae_delete_custom_field",
                operation="delete",
                record_type="custom_field",
                record_id=custom_field_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_delete_custom_field",
                operation="delete",
                record_id=custom_field_id,
            )
