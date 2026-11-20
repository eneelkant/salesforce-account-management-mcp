"""List membership tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import LIST_MEMBERSHIP_DEFAULT_FIELDS

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_memberships")
    async def ae_list_memberships(
        fields: str = LIST_MEMBERSHIP_DEFAULT_FIELDS,
        limit: int = 50,
        list_id: int | None = None,
        prospect_id: int | None = None,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """Query list memberships, optionally filtered by listId or prospectId."""
        try:
            runtime.guard_read()
            filters: dict[str, Any] = {}
            if list_id is not None:
                filters["listId"] = list_id
            if prospect_id is not None:
                filters["prospectId"] = prospect_id
            result = await runtime.client.query(
                "list-memberships",
                fields=fields,
                filters=filters or None,
                limit=limit,
                next_page_token=next_page_token,
            )
            return runtime.ok(
                result,
                tool_name="ae_list_memberships",
                operation="read",
                record_type="list_membership",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_memberships", operation="read")

    @server.tool(name="ae_get_list_members")
    async def ae_get_list_members(
        list_id: int,
        fields: str = LIST_MEMBERSHIP_DEFAULT_FIELDS,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return memberships for a specific list (prospect members)."""
        try:
            runtime.guard_read()
            # Validate list exists first
            await runtime.client.read("lists", list_id, fields="id,name")
            result = await runtime.client.query(
                "list-memberships",
                fields=fields,
                filters={"listId": list_id},
                limit=limit,
            )
            result["list_id"] = list_id
            return runtime.ok(
                result,
                tool_name="ae_get_list_members",
                operation="read",
                record_type="list_membership",
                record_id=list_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_list_members",
                operation="read",
                record_id=list_id,
            )

    @server.tool(name="ae_add_prospect_to_list")
    async def ae_add_prospect_to_list(
        list_id: int,
        prospect_id: int,
        confirm: bool = False,
        opted_out: bool = False,
        fields: str = LIST_MEMBERSHIP_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Add a prospect to a static list (POST list-memberships). Validates both IDs first."""
        try:
            runtime.guard_create(
                confirm=confirm,
                target=f"list-membership list={list_id} prospect={prospect_id}",
            )
            await runtime.client.read("lists", list_id, fields="id,name")
            await runtime.client.read("prospects", prospect_id, fields="id,email")
            body = {"listId": list_id, "prospectId": prospect_id, "optedOut": opted_out}
            result = await runtime.client.create("list-memberships", body, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_add_prospect_to_list",
                operation="create",
                record_type="list_membership",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_add_prospect_to_list", operation="create")

    @server.tool(name="ae_remove_prospect_from_list")
    async def ae_remove_prospect_from_list(
        membership_id: int,
        confirm: bool = False,
        confirm_id: int | None = None,
        list_id: int | None = None,
        prospect_id: int | None = None,
    ) -> dict[str, Any]:
        """Remove a list membership by membership ID (DELETE).

        Optionally pass list_id/prospect_id for audit context. Destructive; requires
        AE_ALLOW_DELETE and confirm_id == membership_id.
        """
        try:
            runtime.guard_delete(
                confirm=confirm,
                target=f"list-membership id={membership_id}",
                record_id=membership_id,
                confirm_id=confirm_id,
            )
            result = await runtime.client.delete("list-memberships", membership_id)
            payload = {
                "deleted": True,
                "membership_id": membership_id,
                "list_id": list_id,
                "prospect_id": prospect_id,
                **(result or {}),
            }
            return runtime.ok(
                payload,
                tool_name="ae_remove_prospect_from_list",
                operation="delete",
                record_type="list_membership",
                record_id=membership_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_remove_prospect_from_list",
                operation="delete",
                record_id=membership_id,
            )
