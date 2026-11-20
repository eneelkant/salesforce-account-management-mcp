"""OAuth Authorization Code + PKCE bootstrap tests."""

from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import httpx
import pytest
import respx

from salesforce_account_engagement_mcp.auth.bootstrap import (
    OAuthCallbackServer,
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
        "http://[::1]:8765/oauth/callback",
    ],
)
def test_validate_redirect_accepts_http_loopback(uri: str) -> None:
    host, port, path = validate_redirect_uri(uri)
    assert host in {"127.0.0.1", "::1"}
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
    with pytest.raises(OAuthError, match=r"username/password|credentials|authority"):
        validate_redirect_uri("http://user:pass@127.0.0.1:8765/oauth/callback")
    with pytest.raises(OAuthError, match=r"explicit port"):
        validate_redirect_uri("http://127.0.0.1/oauth/callback")


def test_validate_redirect_rejects_query_and_fragment() -> None:
    with pytest.raises(OAuthError, match=r"query string"):
        validate_redirect_uri("http://127.0.0.1:8765/oauth/callback?foo=1")
    with pytest.raises(OAuthError, match=r"fragment"):
        validate_redirect_uri("http://127.0.0.1:8765/oauth/callback#section")


def test_validate_redirect_rejects_malformed_port_and_authority() -> None:
    with pytest.raises(OAuthError, match=r"malformed port|authority|could not be parsed"):
        validate_redirect_uri("http://127.0.0.1:notaport/oauth/callback")
    with pytest.raises(OAuthError, match=r"out of range|malformed"):
        validate_redirect_uri("http://127.0.0.1:99999/oauth/callback")
    with pytest.raises(OAuthError, match=r"missing a hostname|malformed|authority"):
        validate_redirect_uri("http://:8765/oauth/callback")
    with pytest.raises(OAuthError, match=r"non-empty|malformed|Unsupported"):
        validate_redirect_uri("")


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


def test_callback_rejects_invalid_state_without_completing_auth() -> None:
    """Wrong CSRF state must not complete wait; a later valid callback can succeed."""
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8780, "/oauth/callback"

    def _hit() -> None:
        bad = f"http://{host}:{port}{path}?code=abc&state=WRONG"
        try:
            urlopen(bad, timeout=2)
        except HTTPError:
            pass
        # Valid follow-up after the incomplete/wrong-state reject.
        good = f"http://{host}:{port}{path}?code=goodcode&state={pkce.state}"
        urlopen(good, timeout=2)

    result = wait_for_oauth_callback(
        host=host,
        port=port,
        path=path,
        expected_state=pkce.state,
        timeout_seconds=5,
        on_ready=_hit,
    )
    assert result.code == "goodcode"
    assert result.state == pkce.state


def test_callback_incomplete_request_does_not_complete_auth() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8781, "/oauth/callback"

    def _hit() -> None:
        # Missing state — must not complete auth.
        try:
            urlopen(f"http://{host}:{port}{path}?code=onlycode", timeout=2)
        except HTTPError:
            pass
        # Missing code — still incomplete.
        try:
            urlopen(f"http://{host}:{port}{path}?state={pkce.state}", timeout=2)
        except HTTPError:
            pass
        urlopen(
            f"http://{host}:{port}{path}?code=final&state={pkce.state}",
            timeout=2,
        )

    result = wait_for_oauth_callback(
        host=host,
        port=port,
        path=path,
        expected_state=pkce.state,
        timeout_seconds=5,
        on_ready=_hit,
    )
    assert result.code == "final"


def test_callback_accepts_valid_state() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8782, "/oauth/callback"

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


def test_repeated_callback_does_not_overwrite_accepted_result() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8783, "/oauth/callback"
    server = OAuthCallbackServer(host=host, port=port, path=path, expected_state=pkce.state)
    server.start()
    try:
        assert server.ready.is_set()
        first = urlopen(
            f"http://{host}:{port}{path}?code=first-valid&state={pkce.state}",
            timeout=2,
        )
        assert first.status == 200
        # Second (attacker / duplicate) must not replace the accepted code.
        second = urlopen(
            f"http://{host}:{port}{path}?code=attacker-code&state={pkce.state}",
            timeout=2,
        )
        assert second.status == 200
        result = server.wait(timeout_seconds=2)
        assert result.code == "first-valid"
        assert result.state == pkce.state
    finally:
        server.stop()


def test_idp_error_with_valid_state_terminates_auth() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8784, "/oauth/callback"

    def _hit() -> None:
        url = (
            f"http://{host}:{port}{path}"
            f"?error=access_denied&error_description=nope&state={pkce.state}"
        )
        try:
            urlopen(url, timeout=2)
        except HTTPError:
            pass

    with pytest.raises(OAuthError, match=r"access_denied") as exc_info:
        wait_for_oauth_callback(
            host=host,
            port=port,
            path=path,
            expected_state=pkce.state,
            timeout_seconds=5,
            on_ready=_hit,
        )
    assert "nope" not in str(exc_info.value)


def test_idp_error_description_never_raised_even_with_secrets() -> None:
    """Regression: wait()/CLI must never surface raw IdP error_description."""
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8791, "/oauth/callback"
    leak = (
        "access_token=ATOKEN refresh_token=RTOKEN client_secret=CSECRET "
        "authorization code=AUTHCODE code_verifier=VERIFIER"
    )

    def _hit() -> None:
        from urllib.parse import quote

        url = (
            f"http://{host}:{port}{path}"
            f"?error=access_denied&error_description={quote(leak)}"
            f"&state={pkce.state}"
        )
        try:
            urlopen(url, timeout=2)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            for needle in (
                "ATOKEN",
                "RTOKEN",
                "CSECRET",
                "AUTHCODE",
                "VERIFIER",
                "access_token",
                "refresh_token",
                "client_secret",
                leak,
            ):
                assert needle not in body

    with pytest.raises(OAuthError) as exc_info:
        wait_for_oauth_callback(
            host=host,
            port=port,
            path=path,
            expected_state=pkce.state,
            timeout_seconds=5,
            on_ready=_hit,
        )
    message = str(exc_info.value)
    assert "access_denied" in message
    for needle in (
        "ATOKEN",
        "RTOKEN",
        "CSECRET",
        "AUTHCODE",
        "VERIFIER",
        "access_token",
        "refresh_token",
        "client_secret",
        "error_description",
        leak,
    ):
        assert needle not in message


def test_idp_error_missing_state_does_not_terminate_session() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8788, "/oauth/callback"

    def _hit() -> None:
        bad = f"http://{host}:{port}{path}?error=access_denied&error_description=nope"
        try:
            urlopen(bad, timeout=2)
        except HTTPError:
            pass
        urlopen(
            f"http://{host}:{port}{path}?code=after-bad-error&state={pkce.state}",
            timeout=2,
        )

    result = wait_for_oauth_callback(
        host=host,
        port=port,
        path=path,
        expected_state=pkce.state,
        timeout_seconds=5,
        on_ready=_hit,
    )
    assert result.code == "after-bad-error"


def test_idp_error_incorrect_state_does_not_terminate_session() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8789, "/oauth/callback"

    def _hit() -> None:
        bad = f"http://{host}:{port}{path}?error=access_denied&state=WRONG_STATE"
        try:
            urlopen(bad, timeout=2)
        except HTTPError:
            pass
        urlopen(
            f"http://{host}:{port}{path}?code=recovered&state={pkce.state}",
            timeout=2,
        )

    result = wait_for_oauth_callback(
        host=host,
        port=port,
        path=path,
        expected_state=pkce.state,
        timeout_seconds=5,
        on_ready=_hit,
    )
    assert result.code == "recovered"


def test_cli_error_path_only_surfaces_category() -> None:
    """Simulate auth login stderr: print(f'error: {exc}') must stay category-only."""
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8792, "/oauth/callback"
    leak = "refresh_token=SECRET access_token=TOK client_secret=CS"

    def _hit() -> None:
        from urllib.parse import quote

        try:
            urlopen(
                f"http://{host}:{port}{path}?error=access_denied"
                f"&error_description={quote(leak)}&state={pkce.state}",
                timeout=2,
            )
        except HTTPError:
            pass

    with pytest.raises(OAuthError) as exc_info:
        wait_for_oauth_callback(
            host=host,
            port=port,
            path=path,
            expected_state=pkce.state,
            timeout_seconds=5,
            on_ready=_hit,
        )
    cli_line = f"error: {exc_info.value}"
    assert cli_line == "error: OAuth callback error: access_denied"
    assert "SECRET" not in cli_line
    assert "TOK" not in cli_line
    assert "CS" not in cli_line


@pytest.mark.asyncio
async def test_pkce_pending_cleared_on_callback_failure(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    object.__setattr__(settings, "sf_client_id", "cid")
    object.__setattr__(settings, "sf_redirect_uri", "http://127.0.0.1:8793/oauth/callback")
    object.__setattr__(settings, "sf_token_store_path", tmp_path / "tokens.json")
    pkce_path = tmp_path / "pkce_pending.json"

    def _failing_wait(**_kwargs: object) -> object:
        raise OAuthError("OAuth callback error: access_denied")

    monkeypatch.setattr(
        "salesforce_account_engagement_mcp.auth.bootstrap.wait_for_oauth_callback",
        _failing_wait,
    )
    monkeypatch.setattr(
        "salesforce_account_engagement_mcp.auth.bootstrap.webbrowser.open",
        lambda *_a, **_k: False,
    )
    with pytest.raises(OAuthError, match=r"access_denied"):
        await run_authorization_code_bootstrap(
            settings,
            open_browser=False,
            timeout_seconds=1,
            pkce_store_path=pkce_path,
        )
    assert not pkce_path.exists()


def test_valid_callback_after_invalid_error_callback() -> None:
    """Regression: invalid error= must not block a later valid success."""
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8790, "/oauth/callback"
    server = OAuthCallbackServer(host=host, port=port, path=path, expected_state=pkce.state)
    server.start()
    try:
        try:
            urlopen(
                f"http://{host}:{port}{path}?error=access_denied",
                timeout=2,
            )
        except HTTPError:
            pass
        assert not server._done.is_set()
        urlopen(
            f"http://{host}:{port}{path}?code=ok-after-error&state={pkce.state}",
            timeout=2,
        )
        result = server.wait(timeout_seconds=2)
        assert result.code == "ok-after-error"
    finally:
        server.stop()


def test_callback_ready_before_immediate_browser_redirect() -> None:
    """Regression: listener must accept connections before on_ready (browser) runs."""
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8785, "/oauth/callback"
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


def test_wrong_path_does_not_complete_auth() -> None:
    pkce = generate_pkce()
    host, port, path = "127.0.0.1", 8786, "/oauth/callback"
    server = OAuthCallbackServer(host=host, port=port, path=path, expected_state=pkce.state)
    server.start()
    try:
        try:
            urlopen(f"http://{host}:{port}/wrong?code=x&state={pkce.state}", timeout=2)
        except HTTPError as exc:
            assert exc.code == 404
        # Wait briefly — wrong path must not set done.
        assert not server._done.wait(timeout=0.3)
        urlopen(
            f"http://{host}:{port}{path}?code=ok&state={pkce.state}",
            timeout=2,
        )
        result = server.wait(timeout_seconds=2)
        assert result.code == "ok"
    finally:
        server.stop()


@pytest.mark.asyncio
async def test_full_bootstrap_flow(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    object.__setattr__(settings, "sf_client_id", "cid")
    object.__setattr__(settings, "sf_client_secret", "sec")
    object.__setattr__(settings, "sf_redirect_uri", "http://127.0.0.1:8787/oauth/callback")
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
