"""List email and landing page asset tools (verified v5 read/query operations)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import LANDING_PAGE_DEFAULT_FIELDS, LIST_EMAIL_DEFAULT_FIELDS

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_list_emails")
    async def ae_list_list_emails(
        fields: str = LIST_EMAIL_DEFAULT_FIELDS,
        limit: int = 50,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """List list-emails (GET /api/v5/objects/list-emails). Does not send email."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "list-emails",
                fields=fields,
                limit=limit,
                next_page_token=next_page_token,
            )
            result["safety_note"] = (
                "This tool only reads list-email metadata; it cannot send email."
            )
            return runtime.ok(
                result,
                tool_name="ae_list_list_emails",
                operation="read",
                record_type="list_email",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_list_emails", operation="read")

    @server.tool(name="ae_get_list_email")
    async def ae_get_list_email(
        list_email_id: int,
        fields: str = LIST_EMAIL_DEFAULT_FIELDS,
        include_stats: bool = True,
    ) -> dict[str, Any]:
        """Get a list-email and optionally its /stats report (API-supplied metrics only)."""
        try:
            runtime.guard_read()
            result = await runtime.client.read("list-emails", list_email_id, fields=fields)
            payload: dict[str, Any] = {
                "list_email": result,
                "metrics_source": "salesforce_api",
            }
            if include_stats:
                try:
                    stats = await runtime.client.get_stats("list-emails", list_email_id)
                    payload["stats"] = stats
                    payload["stats_note"] = (
                        "Stats come from GET /api/v5/objects/list-emails/{id}/stats."
                    )
                except Exception as stats_exc:
                    payload["stats"] = None
                    payload["stats_error"] = str(stats_exc)
                    payload["limitations"] = [
                        "Stats endpoint unavailable for this record or user permission."
                    ]
            return runtime.ok(
                payload,
                tool_name="ae_get_list_email",
                operation="read",
                record_type="list_email",
                record_id=list_email_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_list_email",
                operation="read",
                record_id=list_email_id,
            )

    @server.tool(name="ae_list_landing_pages")
    async def ae_list_landing_pages(
        fields: str = LANDING_PAGE_DEFAULT_FIELDS,
        limit: int = 50,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """List landing pages (GET /api/v5/objects/landing-pages)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "landing-pages",
                fields=fields,
                limit=limit,
                next_page_token=next_page_token,
            )
            return runtime.ok(
                result,
                tool_name="ae_list_landing_pages",
                operation="read",
                record_type="landing_page",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_landing_pages", operation="read")

    @server.tool(name="ae_get_landing_page")
    async def ae_get_landing_page(
        landing_page_id: int,
        fields: str = LANDING_PAGE_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Get a landing page by ID."""
        try:
            runtime.guard_read()
            result = await runtime.client.read("landing-pages", landing_page_id, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_get_landing_page",
                operation="read",
                record_type="landing_page",
                record_id=landing_page_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_landing_page",
                operation="read",
                record_id=landing_page_id,
            )
