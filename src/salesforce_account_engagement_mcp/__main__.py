"""CLI entrypoint: ``salesforce-account-engagement-mcp`` or ``python -m ...``."""

from __future__ import annotations

import argparse
import sys

from .config import get_settings
from .server import create_server
from .transports.http import run_http
from .transports.stdio import run_stdio


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Salesforce Account Engagement (Pardot) MCP server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=None,
        help="Override MCP_TRANSPORT (default: stdio)",
    )
    parser.add_argument("--host", default=None, help="HTTP bind host")
    parser.add_argument("--port", type=int, default=None, help="HTTP bind port")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.transport:
        object.__setattr__(settings, "mcp_transport", args.transport)
    if args.host:
        object.__setattr__(settings, "mcp_host", args.host)
    if args.port:
        object.__setattr__(settings, "mcp_port", args.port)

    server, _runtime = create_server(settings)
    if settings.mcp_transport == "streamable-http":
        run_http(server, settings)
    else:
        run_stdio(server)


if __name__ == "__main__":
    main(sys.argv[1:])
