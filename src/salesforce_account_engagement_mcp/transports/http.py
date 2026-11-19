"""Streamable HTTP transport for remote MCP clients (ChatGPT, Gemini hosts, etc.)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..config import Settings

logger = get_logger(__name__)


def run_http(server: MCPServer, settings: Settings) -> None:
    """Run Streamable HTTP transport.

    Clients connect to ``http://{host}:{port}/mcp`` (SDK default path).
    Deploy behind HTTPS termination for ChatGPT / remote Gemini connectors.
    """
    logger.info(
        "Starting Account Engagement MCP on streamable-http at %s:%s",
        settings.mcp_host,
        settings.mcp_port,
    )
    # MCPServer.run accepts host/port kwargs for streamable-http in mcp 2.x
    server.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )
