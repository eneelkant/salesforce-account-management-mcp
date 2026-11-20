"""Interactive Salesforce OAuth Authorization Code + PKCE bootstrap."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import Settings
from ..logging_config import get_logger
from .oauth import OAuthError, SalesforceOAuthClient, generate_pkce
from .token_manager import TokenManager
from .token_store import TokenStore

logger = get_logger(__name__)


@dataclass
class PendingPKCE:
    """Persisted PKCE + CSRF state for an in-flight auth code flow."""

    code_verifier: str
    code_challenge: str
    state: str
    redirect_uri: str
    login_url: str
    client_id: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PendingPKCE:
        return cls(
            code_verifier=str(data["code_verifier"]),
            code_challenge=str(data["code_challenge"]),
            state=str(data["state"]),
            redirect_uri=str(data["redirect_uri"]),
            login_url=str(data["login_url"]),
            client_id=str(data["client_id"]),
        )


class PKCEStore:
    """Atomic, permission-restricted pending PKCE store (deleted after exchange)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def save(self, pending: PendingPKCE) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(pending.to_dict(), indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def load(self) -> PendingPKCE | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return PendingPKCE.from_dict(data)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


@dataclass
class CallbackResult:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


def _parse_redirect(redirect_uri: str) -> tuple[str, int, str]:
    parsed = urlparse(redirect_uri)
    if parsed.scheme not in {"http", "https"}:
        raise OAuthError(f"Unsupported redirect URI scheme: {parsed.scheme}")
    host = parsed.hostname or "127.0.0.1"
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise OAuthError(
            f"OAuth bootstrap callback server only binds to localhost/127.0.0.1. Got host '{host}'."
        )
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/oauth/callback"
    return host, port, path


def wait_for_oauth_callback(
    *,
    host: str,
    port: int,
    path: str,
    expected_state: str,
    timeout_seconds: float = 300.0,
) -> CallbackResult:
    """Run a one-shot local HTTP callback server and validate CSRF state."""
    result = CallbackResult()
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != path:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return
            params = parse_qs(parsed.query)

            def _first(name: str) -> str | None:
                values = params.get(name)
                if not values:
                    return None
                return values[0]

            result.code = _first("code")
            result.state = _first("state")
            result.error = _first("error")
            result.error_description = _first("error_description")

            if result.error:
                body = f"OAuth error: {result.error} {result.error_description or ''}".encode()
                self.send_response(400)
            elif not result.code:
                body = b"Missing authorization code"
                self.send_response(400)
            elif result.state != expected_state:
                body = b"Invalid OAuth state (CSRF check failed)"
                self.send_response(400)
                result.error = "invalid_state"
                result.error_description = "state mismatch"
            else:
                body = b"Authentication complete. You can close this window."
                self.send_response(200)

            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            done.set()

        def log_message(self, format: str, *args: object) -> None:
            logger.debug("oauth-callback: " + format, *args)

    server = HTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    finished = done.wait(timeout=timeout_seconds)
    server.server_close()
    thread.join(timeout=5)
    if not finished:
        raise OAuthError(
            f"Timed out after {timeout_seconds:.0f}s waiting for OAuth callback on "
            f"{host}:{port}{path}."
        )
    if result.error:
        raise OAuthError(f"OAuth callback error: {result.error} ({result.error_description or ''})")
    if not result.code or result.state != expected_state:
        raise OAuthError("OAuth callback failed state/code validation.")
    return result


async def run_authorization_code_bootstrap(
    settings: Settings,
    *,
    open_browser: bool = True,
    timeout_seconds: float = 300.0,
    pkce_store_path: Path | None = None,
) -> dict[str, object]:
    """Complete Authorization Code + PKCE login and persist tokens."""
    if not settings.sf_client_id:
        raise OAuthError("SF_CLIENT_ID is required for OAuth bootstrap.")

    oauth = SalesforceOAuthClient(
        client_id=settings.sf_client_id,
        client_secret=settings.sf_client_secret,
        redirect_uri=settings.sf_redirect_uri,
        login_url=settings.sf_login_url,
        scopes=settings.sf_oauth_scopes,
    )
    pkce = generate_pkce()
    # Extra entropy binding for local pending file identity
    _ = secrets.token_hex(8)

    store_path = pkce_store_path or (
        Path(settings.sf_token_store_path).parent / "pkce_pending.json"
    )
    pkce_store = PKCEStore(store_path)
    pending = PendingPKCE(
        code_verifier=pkce.code_verifier,
        code_challenge=pkce.code_challenge,
        state=pkce.state,
        redirect_uri=settings.sf_redirect_uri,
        login_url=settings.sf_login_url,
        client_id=settings.sf_client_id,
    )
    pkce_store.save(pending)

    host, port, path = _parse_redirect(settings.sf_redirect_uri)
    auth_url = oauth.build_authorization_url(pkce)
    logger.info("Starting local OAuth callback server on %s:%s%s", host, port, path)
    print("Open this URL to authorize Salesforce Account Engagement access:\n")
    print(auth_url)
    print()
    if open_browser:
        try:
            webbrowser.open(auth_url)
        except Exception:
            logger.debug("Unable to open system browser", exc_info=False)

    # Blocking callback wait in a worker thread so this coroutine stays async-friendly.
    callback = await asyncio.to_thread(
        wait_for_oauth_callback,
        host=host,
        port=port,
        path=path,
        expected_state=pkce.state,
        timeout_seconds=timeout_seconds,
    )

    loaded = pkce_store.load()
    if loaded is None or loaded.state != pkce.state:
        pkce_store.clear()
        raise OAuthError("Pending PKCE state missing or mismatched after callback.")
    if not hmac_compare(loaded.code_verifier, pkce.code_verifier):
        pkce_store.clear()
        raise OAuthError("Pending PKCE verifier mismatch.")

    assert callback.code is not None
    tokens = await oauth.exchange_code(
        code=callback.code,
        code_verifier=loaded.code_verifier,
    )
    pkce_store.clear()

    manager = TokenManager(
        settings,
        oauth_client=oauth,
        store=TokenStore(settings.sf_token_store_path),
    )
    manager.update_from_oauth(tokens)
    snapshot = manager.snapshot()
    return {
        "ok": True,
        "message": "Salesforce OAuth tokens persisted.",
        "token_store": str(settings.sf_token_store_path),
        "auth": snapshot,
        "scopes_requested": settings.sf_oauth_scopes,
        "note": "Refresh/access tokens are stored locally; never commit this file.",
    }


def hmac_compare(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a, b)
