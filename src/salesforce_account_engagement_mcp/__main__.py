"""CLI entrypoint: ``salesforce-account-engagement-mcp`` or ``python -m ...``."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .config import get_settings
from .server import create_server
from .transports.http import run_http
from .transports.http_auth import HttpAuthConfigurationError
from .transports.stdio import run_stdio


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Salesforce Account Engagement (Pardot) MCP server",
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Run the MCP server (default)")
    serve.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=None,
        help="Override MCP_TRANSPORT (default: stdio)",
    )
    serve.add_argument("--host", default=None, help="HTTP bind host")
    serve.add_argument("--port", type=int, default=None, help="HTTP bind port")

    auth = sub.add_parser(
        "auth",
        help="Salesforce OAuth helpers",
    )
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    login = auth_sub.add_parser(
        "login",
        help="Run Authorization Code + PKCE bootstrap and persist tokens",
    )
    login.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a system browser; print the authorize URL only",
    )
    login.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for the local OAuth callback (default: 300)",
    )

    # Back-compat: allow top-level --transport without subcommand
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--host", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=None, help=argparse.SUPPRESS)
    return parser


def _run_serve(args: argparse.Namespace) -> None:
    settings = get_settings()
    transport = args.transport or settings.mcp_transport
    if args.host:
        object.__setattr__(settings, "mcp_host", args.host)
    if args.port:
        object.__setattr__(settings, "mcp_port", args.port)
    object.__setattr__(settings, "mcp_transport", transport)

    enable_http_auth = transport == "streamable-http"
    try:
        server, _runtime = create_server(settings, enable_http_auth=enable_http_auth)
    except HttpAuthConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if transport == "streamable-http":
        run_http(server, settings)
    else:
        run_stdio(server)


def _run_auth_login(args: argparse.Namespace) -> None:
    from .auth.bootstrap import run_authorization_code_bootstrap
    from .auth.oauth import OAuthError

    settings = get_settings()
    try:
        result = asyncio.run(
            run_authorization_code_bootstrap(
                settings,
                open_browser=not args.no_browser,
                timeout_seconds=args.timeout,
            )
        )
    except OAuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, indent=2, default=str))


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "auth":
        if args.auth_command == "login":
            _run_auth_login(args)
            return
        parser.error("Unknown auth command")

    # Default / serve
    if args.command in {None, "serve"}:
        _run_serve(args)
        return
    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main(sys.argv[1:])
