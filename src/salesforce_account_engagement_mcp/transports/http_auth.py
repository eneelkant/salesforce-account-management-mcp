"""Fail-closed authentication for Streamable HTTP MCP transport.

Salesforce credentials never leave the process. Remote MCP clients must present
a separate MCP access credential (bearer token) or an authenticated reverse-proxy
must inject that credential. STDIO transport does not use this module.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Literal

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

from ..config import Settings
from ..logging_config import get_logger

logger = get_logger(__name__)

HttpAuthMode = Literal["bearer", "proxy"]


class HttpAuthConfigurationError(RuntimeError):
    """Raised when Streamable HTTP is requested without a complete auth config."""


@dataclass(frozen=True)
class HttpAuthBundle:
    """Auth objects required by MCPServer for streamable-http."""

    mode: HttpAuthMode
    token_verifier: TokenVerifier
    auth_settings: AuthSettings


class SharedSecretTokenVerifier:
    """Constant-time comparison against a configured shared MCP bearer secret.

    This credential authenticates the *MCP client / reverse proxy*, not Salesforce.
    """

    def __init__(
        self,
        *,
        expected_token: str,
        client_id: str,
        scopes: list[str],
        resource: str | None,
    ) -> None:
        if not expected_token:
            raise HttpAuthConfigurationError("HTTP shared secret token must be non-empty.")
        self._expected = expected_token
        self._client_id = client_id
        self._scopes = scopes
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not hmac.compare_digest(token, self._expected):
            return None
        return AccessToken(
            token=token,
            client_id=self._client_id,
            scopes=list(self._scopes),
            resource=self._resource,
        )


def build_http_auth(settings: Settings) -> HttpAuthBundle:
    """Build HTTP auth or raise — Streamable HTTP must fail closed."""
    mode = settings.mcp_http_auth_mode
    if mode not in {"bearer", "proxy"}:
        raise HttpAuthConfigurationError(
            "Streamable HTTP requires MCP_HTTP_AUTH_MODE=bearer or MCP_HTTP_AUTH_MODE=proxy. "
            "Refusing to start an unauthenticated remote MCP endpoint that could expose "
            "Salesforce Account Engagement access."
        )

    secret = (
        settings.mcp_http_bearer_token
        if mode == "bearer"
        else settings.mcp_http_proxy_shared_secret
    )
    if not secret:
        env_name = "MCP_HTTP_BEARER_TOKEN" if mode == "bearer" else "MCP_HTTP_PROXY_SHARED_SECRET"
        raise HttpAuthConfigurationError(
            f"Streamable HTTP auth mode '{mode}' requires {env_name}. "
            "Failing closed: Salesforce credentials will not be exposed over an "
            "unauthenticated MCP HTTP endpoint."
        )

    resource = settings.mcp_http_resource_url or None
    scopes = ["ae_mcp:access"]
    verifier: TokenVerifier = SharedSecretTokenVerifier(
        expected_token=secret,
        client_id=f"ae-mcp-{mode}",
        scopes=scopes,
        resource=resource,
    )

    # issuer_url is echoed into protected-resource metadata when resource_server_url is set.
    # For shared-secret / reverse-proxy deployments we disable discovery by default.
    issuer = settings.mcp_http_issuer_url or "https://localhost/ae-mcp-local-issuer"
    auth_settings = AuthSettings(
        issuer_url=AnyHttpUrl(issuer),
        resource_server_url=AnyHttpUrl(resource) if resource else None,
        required_scopes=scopes,
        validate_token_resource=bool(resource),
    )

    logger.info(
        "Streamable HTTP auth enabled mode=%s resource_metadata=%s",
        mode,
        bool(resource),
    )
    return HttpAuthBundle(mode=mode, token_verifier=verifier, auth_settings=auth_settings)


def require_http_auth_or_raise(settings: Settings) -> HttpAuthBundle:
    """Public entry used by the HTTP transport runner."""
    return build_http_auth(settings)
