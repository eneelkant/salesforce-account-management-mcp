"""MCP tool registration for Account Engagement."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register_all_tools(server: MCPServer, runtime: AppRuntime) -> None:
    """Register every tool module against the shared MCP server."""
    from . import (
        account,
        campaigns,
        custom_fields,
        diagnostics,
        emails,
        forms,
        lists,
        memberships,
        prospects,
        reports,
        segments,
        tags,
        visitor_activities,
        visitors,
    )

    account.register(server, runtime)
    prospects.register(server, runtime)
    campaigns.register(server, runtime)
    lists.register(server, runtime)
    memberships.register(server, runtime)
    visitors.register(server, runtime)
    visitor_activities.register(server, runtime)
    custom_fields.register(server, runtime)
    emails.register(server, runtime)
    forms.register(server, runtime)
    tags.register(server, runtime)
    segments.register(server, runtime)
    reports.register(server, runtime)
    diagnostics.register(server, runtime)
