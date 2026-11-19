"""Form asset tools (read/query; create/delete exist in API but stay behind write guards)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import FORM_DEFAULT_FIELDS

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_forms")
    async def ae_list_forms(
        fields: str = FORM_DEFAULT_FIELDS,
        limit: int = 50,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """List forms (GET /api/v5/objects/forms)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "forms",
                fields=fields,
                limit=limit,
                next_page_token=next_page_token,
            )
            return runtime.ok(
                result, tool_name="ae_list_forms", operation="read", record_type="form"
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_forms", operation="read")

    @server.tool(name="ae_get_form")
    async def ae_get_form(form_id: int, fields: str = FORM_DEFAULT_FIELDS) -> dict[str, Any]:
        """Get a form by ID."""
        try:
            runtime.guard_read()
            result = await runtime.client.read("forms", form_id, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_get_form",
                operation="read",
                record_type="form",
                record_id=form_id,
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_form", operation="read", record_id=form_id)
