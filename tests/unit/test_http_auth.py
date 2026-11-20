"""Streamable HTTP fail-closed authentication tests."""

from __future__ import annotations

import pytest

from salesforce_account_engagement_mcp.config import Settings, reset_settings_cache
from salesforce_account_engagement_mcp.server import create_server
from salesforce_account_engagement_mcp.transports.http_auth import (
    HttpAuthConfigurationError,
    SharedSecretTokenVerifier,
    build_http_auth,
)


def test_http_auth_fails_closed_without_mode(settings: Settings) -> None:
    object.__setattr__(settings, "mcp_http_auth_mode", "")
    with pytest.raises(HttpAuthConfigurationError, match="MCP_HTTP_AUTH_MODE"):
        build_http_auth(settings)


def test_http_auth_fails_closed_without_bearer_secret(settings: Settings) -> None:
    object.__setattr__(settings, "mcp_http_auth_mode", "bearer")
    object.__setattr__(settings, "mcp_http_bearer_token", "")
    with pytest.raises(HttpAuthConfigurationError, match="MCP_HTTP_BEARER_TOKEN"):
        build_http_auth(settings)


def test_http_auth_fails_closed_without_proxy_secret(settings: Settings) -> None:
    object.__setattr__(settings, "mcp_http_auth_mode", "proxy")
    object.__setattr__(settings, "mcp_http_proxy_shared_secret", "")
    with pytest.raises(HttpAuthConfigurationError, match="MCP_HTTP_PROXY_SHARED_SECRET"):
        build_http_auth(settings)


@pytest.mark.asyncio
async def test_shared_secret_verifier_accepts_and_rejects() -> None:
    verifier = SharedSecretTokenVerifier(
        expected_token="s3cret",
        client_id="ae-mcp-bearer",
        scopes=["ae_mcp:access"],
        resource=None,
    )
    ok = await verifier.verify_token("s3cret")
    bad = await verifier.verify_token("wrong")
    assert ok is not None
    assert ok.client_id == "ae-mcp-bearer"
    assert bad is None


def test_create_server_http_requires_auth(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    reset_settings_cache()
    monkeypatch.setenv("PARDOT_BUSINESS_UNIT_ID", "0Uv000000000000001")
    monkeypatch.setenv("SF_ACCESS_TOKEN", "t")
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HTTP_AUTH_MODE", "")
    monkeypatch.setenv("SF_TOKEN_STORE_PATH", str(tmp_path / "t.json"))
    settings = Settings()
    with pytest.raises(HttpAuthConfigurationError):
        create_server(settings, enable_http_auth=True)


def test_create_server_http_with_bearer(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    reset_settings_cache()
    monkeypatch.setenv("PARDOT_BUSINESS_UNIT_ID", "0Uv000000000000001")
    monkeypatch.setenv("SF_ACCESS_TOKEN", "t")
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HTTP_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_HTTP_BEARER_TOKEN", "mcp-shared-secret")
    monkeypatch.setenv("SF_TOKEN_STORE_PATH", str(tmp_path / "t.json"))
    settings = Settings()
    server, _ = create_server(settings, enable_http_auth=True)
    assert getattr(server, "_token_verifier", None) is not None


def test_stdio_does_not_require_http_auth(settings: Settings) -> None:
    object.__setattr__(settings, "mcp_transport", "stdio")
    server, _ = create_server(settings, enable_http_auth=False)
    assert getattr(server, "_token_verifier", None) is None
