"""STDIO transport for Cursor, Claude Desktop, and local MCP hosts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

logger = get_logger(__name__)


def run_stdio(server: MCPServer) -> None:
    """Run the shared MCP server over stdio (default for desktop clients)."""
    logger.info("Starting Account Engagement MCP on stdio transport")
    server.run(transport="stdio")
