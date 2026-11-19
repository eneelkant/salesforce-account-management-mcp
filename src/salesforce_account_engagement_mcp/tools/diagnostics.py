"""Diagnostic and security status tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import __version__

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_get_security_status")
    async def ae_get_security_status() -> dict[str, Any]:
        """Show current read-only / write / delete permission mode (no secrets)."""
        return runtime.ok(
            {
                "version": __version__,
                "permissions": runtime.permissions.status(),
                "max_records": runtime.settings.ae_max_records,
                "max_concurrent_requests": runtime.settings.ae_max_concurrent_requests,
                "transport": runtime.settings.mcp_transport,
            },
            tool_name="ae_get_security_status",
            operation="read",
        )

    @server.tool(name="ae_get_tool_catalogue")
    async def ae_get_tool_catalogue() -> dict[str, Any]:
        """List registered MCP tool names for this server instance."""
        tools = await server.list_tools()
        names = sorted(t.name for t in tools)
        return runtime.ok(
            {
                "tool_count": len(names),
                "tools": names,
                "data_source": "local_mcp_registry",
            },
            tool_name="ae_get_tool_catalogue",
            operation="read",
        )
