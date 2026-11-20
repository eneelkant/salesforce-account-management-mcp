"""OAuth Authorization Code + PKCE bootstrap tests."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import httpx
import pytest
import respx

from salesforce_account_engagement_mcp.auth.bootstrap import (
    PendingPKCE,
    PKCEStore,
    run_authorization_code_bootstrap,
    validate_redirect_uri,
    wait_for_oauth_callback,
)
from salesforce_account_engagement_mcp.auth.oauth import (
    DEFAULT_SCOPES,
    OAuthError,
    SalesforceOAuthClient,
    generate_pkce,
)
from salesforce_account_engagement_mcp.config import Settings


def test_default_scopes_are_least_privilege() -> None:
    assert "pardot_api" in DEFAULT_SCOPES
    assert "refresh_token" in DEFAULT_SCOPES
    assert " api" not in f" {DEFAULT_SCOPES} "


@pytest.mark.parametrize(
    "uri",
    [
        "http://127.0.0.1:8765/oauth/callback",
        "http://localhost:8765/oauth/callback",
    ],
)
def test_validate_redirect_accepts_http_loopback(uri: str) -> None:
    host, port, path = validate_redirect_uri(uri)
    assert host == "127.0.0.1"
    assert port == 8765
    assert path == "/oauth/callback"


def test_validate_redirect_rejects_https_without_local_tls() -> None:
    with pytest.raises(OAuthError, match=r"https://.*TLS|HTTP loopback"):
        validate_redirect_uri("https://127.0.0.1:8765/oauth/callback")


def test_validate_redirect_rejects_external_hosts() -> None:
    with pytest.raises(OAuthError, match=r"loopback|not a loopback"):
        validate_redirect_uri("http://example.com:8765/oauth/callback")
    with pytest.raises(OAuthError, match=r"loopback|not a loopback"):
        validate_redirect_uri("http://10.0.0.5:8765/oauth/callback")


def test_validate_redirect_rejects_credentials_and_missing_port() -> None:
    with pytest.raises(OAuthError, match=r"username/password|credentials"):
        validate_redirect_uri("http://user:pass@127.0.0.1:8765/oauth/callback")
    with pytest.raises(OAuthError, match=r"explicit port"):
        validate_redirect_uri("http://127.0.0.1/oauth/callback")


def test_pkce_store_roundtrip(tmp_path: Path) -> None:
    store = PKCEStore(tmp_path / "pkce_pending.json")
    pending = PendingPKCE(
        code_verifier="verifier",
        code_challenge="challenge",
        state="state123",
        redirect_uri="http://127.0.0.1:8765/oauth/callback",
        login_url="https://login.salesforce.com",
        client_id="cid",
    )
    store.save(pending)
    loaded = store.load()
    assert loaded is not None
    assert loaded.state == "state123"
    store.clear()
    assert store.load() is None


def test_callback_rejects_invalid_state() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8769, "/oauth/callback"

    def _hit() -> None:
        url = f"http://{host}:{port}{path}?code=abc&state=WRONG"
        try:
            urlopen(url, timeout=2)
        except Exception:
            pass

    with pytest.raises(OAuthError, match=r"state|invalid"):
        wait_for_oauth_callback(
            host=host,
            port=port,
            path=path,
            expected_state=pkce.state,
            timeout_seconds=5,
            on_ready=_hit,
        )


def test_callback_accepts_valid_state() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8770, "/oauth/callback"

    def _hit() -> None:
        url = f"http://{host}:{port}{path}?code=authcode&state={pkce.state}"
        urlopen(url, timeout=2)

    result = wait_for_oauth_callback(
        host=host,
        port=port,
        path=path,
        expected_state=pkce.state,
        timeout_seconds=5,
        on_ready=_hit,
    )
    assert result.code == "authcode"
    assert result.state == pkce.state


def test_callback_ready_before_immediate_browser_redirect() -> None:
    """Regression: listener must accept connections before on_ready (browser) runs."""
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8772, "/oauth/callback"
    order: list[str] = []

    def _immediate_redirect() -> None:
        order.append("browser")
        # No sleep — simulate Salesforce redirecting immediately after authorize.
        url = f"http://{host}:{port}{path}?code=fast&state={pkce.state}"
        urlopen(url, timeout=2)

    result = wait_for_oauth_callback(
        host=host,
        port=port,
        path=path,
        expected_state=pkce.state,
        timeout_seconds=5,
        on_ready=_immediate_redirect,
    )
    assert result.code == "fast"
    assert order == ["browser"]


@pytest.mark.asyncio
async def test_full_bootstrap_flow(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    object.__setattr__(settings, "sf_client_id", "cid")
    object.__setattr__(settings, "sf_client_secret", "sec")
    object.__setattr__(settings, "sf_redirect_uri", "http://127.0.0.1:8771/oauth/callback")
    object.__setattr__(settings, "sf_token_store_path", tmp_path / "tokens.json")
    object.__setattr__(settings, "sf_oauth_scopes", "pardot_api refresh_token")

    real_wait = wait_for_oauth_callback

    def _wait_and_inject(**kwargs: object) -> object:
        expected_state = str(kwargs["expected_state"])
        host = str(kwargs["host"])
        port = int(kwargs["port"])  # type: ignore[arg-type]
        path = str(kwargs["path"])

        def _hit() -> None:
            url = f"http://{host}:{port}{path}?code=from-sf&state={expected_state}"
            urlopen(url, timeout=2)

        # Preserve ready-before-browser contract from production code.
        kwargs = {**kwargs, "on_ready": _hit}
        return real_wait(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "salesforce_account_engagement_mcp.auth.bootstrap.wait_for_oauth_callback",
        _wait_and_inject,
    )
    monkeypatch.setattr(
        "salesforce_account_engagement_mcp.auth.bootstrap.webbrowser.open",
        lambda *_a, **_k: False,
    )

    with respx.mock:
        route = respx.post("https://login.salesforce.com/services/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "access-from-code",
                    "refresh_token": "refresh-from-code",
                    "instance_url": "https://example.my.salesforce.com",
                    "issued_at": "1700000000000",
                    "scope": "pardot_api refresh_token",
                },
            )
        )
        result = await run_authorization_code_bootstrap(
            settings,
            open_browser=True,
            timeout_seconds=5,
            pkce_store_path=tmp_path / "pkce_pending.json",
        )

    assert route.called
    body = route.calls[0].request.content.decode()
    assert "grant_type=authorization_code" in body
    assert "code=from-sf" in body
    assert "code_verifier=" in body
    assert result["ok"] is True
    assert (tmp_path / "tokens.json").exists()
    assert not (tmp_path / "pkce_pending.json").exists()
    client = SalesforceOAuthClient(
        client_id="cid",
        redirect_uri=settings.sf_redirect_uri,
        scopes=settings.sf_oauth_scopes,
    )
    pkce = generate_pkce()
    url = client.build_authorization_url(pkce)
    scopes = parse_qs(urlparse(url).query)["scope"][0]
    assert scopes == "pardot_api refresh_token"
