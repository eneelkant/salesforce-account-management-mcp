"""Streamable HTTP transport for remote MCP clients (ChatGPT, Gemini hosts, etc.)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .http_auth import HttpAuthConfigurationError, require_http_auth_or_raise

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..config import Settings

logger = get_logger(__name__)


def run_http(server: MCPServer, settings: Settings) -> None:
    """Run Streamable HTTP transport with fail-closed authentication.

    Clients connect to ``http://{host}:{port}/mcp`` and must present a valid
    ``Authorization: Bearer`` credential configured via MCP_HTTP_AUTH_MODE.

    Salesforce tokens stay server-side; they are never accepted from MCP clients.
    """
    # Defense in depth: refuse to bind if auth is incomplete even if the server
    # was constructed without auth (e.g. miswired caller).
    try:
        require_http_auth_or_raise(settings)
    except HttpAuthConfigurationError:
        raise

    if getattr(server, "_token_verifier", None) is None:
        raise HttpAuthConfigurationError(
            "Streamable HTTP server was created without a token_verifier. "
            "Refusing to expose an unauthenticated MCP endpoint."
        )

    logger.info(
        "Starting Account Engagement MCP on streamable-http at %s:%s (auth required)",
        settings.mcp_host,
        settings.mcp_port,
    )
    server.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )
