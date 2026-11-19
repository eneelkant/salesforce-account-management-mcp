"""OAuth and token manager tests."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
import respx

from salesforce_account_engagement_mcp.auth.oauth import (
    OAuthError,
    SalesforceOAuthClient,
    generate_pkce,
    parse_token_response,
)
from salesforce_account_engagement_mcp.auth.token_manager import TokenManager
from salesforce_account_engagement_mcp.auth.token_store import StoredTokens, TokenStore
from salesforce_account_engagement_mcp.config import Settings


def test_pkce_generates_s256_challenge() -> None:
    pkce = generate_pkce()
    assert pkce.code_verifier
    assert pkce.code_challenge
    assert pkce.state
    assert pkce.code_challenge != pkce.code_verifier


def test_parse_token_response_requires_access_token() -> None:
    with pytest.raises(OAuthError):
        parse_token_response({})


def test_parse_token_response_ok() -> None:
    tokens = parse_token_response(
        {
            "access_token": "abc",
            "refresh_token": "r",
            "instance_url": "https://example.my.salesforce.com",
            "issued_at": str(int(time.time() * 1000)),
            "expires_in": 3600,
        }
    )
    assert tokens.access_token == "abc"
    assert tokens.refresh_token == "r"


def test_token_store_atomic_roundtrip(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    store.save(StoredTokens(access_token="a", refresh_token="b"))
    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "a"
    assert loaded.refresh_token == "b"


@pytest.mark.asyncio
async def test_token_manager_refresh(settings: Settings, tmp_path: Path) -> None:
    settings = settings.model_copy(
        update={
            "sf_access_token": "expired",
            "sf_refresh_token": "refresh-me",
            "sf_token_store_path": tmp_path / "t.json",
        }
    )
    manager = TokenManager(settings)
    # Force expiry
    assert manager._tokens is not None
    manager._tokens.issued_at = time.time() - 10_000
    manager._tokens.expires_in = 60

    with respx.mock:
        route = respx.post("https://login.salesforce.com/services/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "instance_url": "https://example.my.salesforce.com",
                    "issued_at": str(int(time.time() * 1000)),
                    "expires_in": 7200,
                },
            )
        )
        token = await manager.get_access_token()
    assert route.called
    assert token == "new-access"
    assert manager.snapshot()["has_access_token"] is True


@pytest.mark.asyncio
async def test_oauth_refresh_preserves_refresh_token() -> None:
    client = SalesforceOAuthClient(
        client_id="cid",
        client_secret="sec",
        redirect_uri="http://localhost:8765/oauth/callback",
    )
    with respx.mock:
        respx.post("https://login.salesforce.com/services/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "a2", "issued_at": str(int(time.time() * 1000))},
            )
        )
        tokens = await client.refresh("old-refresh")
    assert tokens.access_token == "a2"
    assert tokens.refresh_token == "old-refresh"
