"""Interactive Salesforce OAuth Authorization Code + PKCE bootstrap."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import threading
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import Settings
from ..logging_config import get_logger
from .oauth import OAuthError, SalesforceOAuthClient, generate_pkce, oauth_error_category
from .token_manager import TokenManager
from .token_store import TokenStore

logger = get_logger(__name__)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


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


def validate_redirect_uri(redirect_uri: str) -> tuple[str, int, str]:
    """Validate SF_REDIRECT_URI for the local bootstrap callback server.

    Only plain HTTP loopback URIs are supported. HTTPS is rejected unless a
    local TLS certificate/key pair is configured (not implemented in bootstrap —
    use HTTP loopback instead). Query strings and fragments are rejected.
    """
    if not isinstance(redirect_uri, str) or not redirect_uri.strip():
        raise OAuthError("SF_REDIRECT_URI must be a non-empty HTTP loopback URL.")

    try:
        parsed = urlparse(redirect_uri)
    except ValueError as exc:
        raise OAuthError(f"SF_REDIRECT_URI is malformed and could not be parsed: {exc}") from exc

    if parsed.scheme == "https":
        raise OAuthError(
            "SF_REDIRECT_URI uses https://, but the local OAuth bootstrap callback "
            "server does not ship with TLS certificates. Use an HTTP loopback URI "
            "such as http://127.0.0.1:8765/oauth/callback (or http://localhost:8765/...)."
        )
    if parsed.scheme != "http":
        raise OAuthError(
            f"Unsupported SF_REDIRECT_URI scheme '{parsed.scheme or '(empty)'}'. "
            "Only http://127.0.0.1 or http://localhost loopback URIs are supported."
        )
    if parsed.query:
        raise OAuthError(
            "SF_REDIRECT_URI must not include a query string. "
            "Use a bare path such as http://127.0.0.1:8765/oauth/callback."
        )
    if parsed.fragment:
        raise OAuthError(
            "SF_REDIRECT_URI must not include a URL fragment (#...). "
            "Use a bare path such as http://127.0.0.1:8765/oauth/callback."
        )

    netloc = parsed.netloc or ""
    if "@" in netloc or parsed.username is not None or parsed.password is not None:
        raise OAuthError(
            "SF_REDIRECT_URI must not include username/password credentials "
            "or a malformed authority containing '@'."
        )

    # Hostname / port: urlparse raises ValueError for non-numeric ports; also
    # catch incomplete authorities (missing host).
    try:
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError as exc:
        raise OAuthError(f"SF_REDIRECT_URI has a malformed port or authority: {exc}") from exc

    if not host:
        raise OAuthError(
            "SF_REDIRECT_URI is missing a hostname. "
            "Expected http://127.0.0.1:<port>/oauth/callback."
        )
    if host not in _LOOPBACK_HOSTS:
        raise OAuthError(
            f"SF_REDIRECT_URI host '{host}' is not a loopback address. "
            "Only localhost, 127.0.0.1, or ::1 are allowed for the local callback server."
        )
    if port is None:
        raise OAuthError(
            "SF_REDIRECT_URI must include an explicit port "
            "(for example http://127.0.0.1:8765/oauth/callback)."
        )
    if not (1 <= int(port) <= 65535):
        raise OAuthError(
            f"SF_REDIRECT_URI port {port} is out of range. Use a port between 1 and 65535."
        )

    path = parsed.path or "/oauth/callback"
    if not path.startswith("/"):
        raise OAuthError("SF_REDIRECT_URI path must start with '/'.")

    # Bind address: map localhost to 127.0.0.1 for IPv4 listener predictability.
    bind_host = "127.0.0.1" if host in {"localhost", "127.0.0.1"} else host
    return bind_host, int(port), path


# Backwards-compatible alias used by older call sites / tests.
_parse_redirect = validate_redirect_uri


class OAuthCallbackServer:
    """Thread-safe one-shot localhost OAuth callback listener.

    Lifecycle:
    1. ``start()`` binds the socket and begins serving in a background thread.
    2. Callers wait on ``ready`` before opening the browser (eliminates race).
    3. ``wait()`` blocks until a terminal callback is handled or timeout.
    4. ``stop()`` shuts the server down.

    Only a valid (code + matching CSRF state) or an IdP ``error=`` response
    that also carries the matching CSRF ``state`` is terminal. Incomplete,
    malformed, duplicate, or wrong-state requests (including error callbacks
    without valid state) are rejected without completing auth. A previously
    accepted valid callback is never overwritten.
    """

    def __init__(self, *, host: str, port: int, path: str, expected_state: str) -> None:
        self.host = host
        self.port = port
        self.path = path
        self.expected_state = expected_state
        self.ready = threading.Event()
        self._done = threading.Event()
        self._lock = threading.Lock()
        self._result = CallbackResult()
        self._accepted = False  # True once a valid code+state is locked in
        self._terminal_error = False  # True once an IdP error= is locked in
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path != outer.path:
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

                code = _first("code")
                state = _first("state")
                error = _first("error")
                # IdP error_description is intentionally ignored — never store,
                # log, raise, or print provider description text (may contain
                # secrets or sensitive strings).

                signal_done = False
                status = 400
                body = b"Invalid OAuth callback"

                with outer._lock:
                    # Never overwrite a previously accepted valid callback.
                    if outer._accepted:
                        status = 200
                        body = b"Authentication already completed. You can close this window."
                    elif outer._terminal_error:
                        status = 400
                        body = b"OAuth already failed. Restart login."
                    elif error:
                        # IdP error is terminal only when CSRF state matches.
                        # Missing/incorrect state must not kill the login session.
                        if not state or state != outer.expected_state:
                            status = 400
                            body = b"Invalid OAuth error callback (missing or mismatched state)"
                        else:
                            category = oauth_error_category(error)
                            outer._result = CallbackResult(
                                code=None,
                                state=state,
                                error=category,
                                error_description=None,
                            )
                            outer._terminal_error = True
                            signal_done = True
                            status = 400
                            body = f"OAuth error: {category}".encode()
                    elif not code or not state:
                        # Incomplete — reject without completing the wait so a
                        # later valid redirect can still succeed.
                        status = 400
                        body = b"Incomplete OAuth callback (missing code or state)"
                    elif state != outer.expected_state:
                        # CSRF mismatch — reject without completing auth / wait.
                        status = 400
                        body = b"Invalid OAuth state (CSRF check failed)"
                    else:
                        # Valid authorization code + CSRF state.
                        outer._result = CallbackResult(
                            code=code,
                            state=state,
                            error=None,
                            error_description=None,
                        )
                        outer._accepted = True
                        signal_done = True
                        status = 200
                        body = b"Authentication complete. You can close this window."

                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                if signal_done:
                    outer._done.set()

            def log_message(self, format: str, *args: object) -> None:
                # Never log the request line/query — it may contain auth codes.
                logger.debug("oauth-callback: request handled")

        # Bind before marking ready so an immediate browser redirect cannot race.
        try:
            server = HTTPServer((self.host, self.port), Handler)
        except OSError as exc:
            raise OAuthError(
                f"Unable to bind OAuth callback server on {self.host}:{self.port}: {exc}"
            ) from exc
        self._server = server

        def _serve() -> None:
            assert self._server is not None
            # Socket is already bound by HTTPServer.__init__; signal readiness
            # before entering the accept loop so callers may open the browser.
            self.ready.set()
            self._server.serve_forever(poll_interval=0.2)

        self._thread = threading.Thread(target=_serve, name="ae-oauth-callback", daemon=True)
        self._thread.start()
        if not self.ready.wait(timeout=5.0):
            self.stop()
            raise OAuthError("OAuth callback server failed to become ready.")

    def wait(self, timeout_seconds: float) -> CallbackResult:
        finished = self._done.wait(timeout=timeout_seconds)
        if not finished:
            raise OAuthError(
                f"Timed out after {timeout_seconds:.0f}s waiting for OAuth callback on "
                f"{self.host}:{self.port}{self.path}."
            )
        with self._lock:
            result = CallbackResult(
                code=self._result.code,
                state=self._result.state,
                error=self._result.error,
                error_description=self._result.error_description,
            )
            accepted = self._accepted
            terminal_error = self._terminal_error
        if result.error or terminal_error:
            # Category only — never raise raw IdP error_description / secrets.
            category = oauth_error_category(result.error)
            raise OAuthError(f"OAuth callback error: {category}")
        if not accepted or not result.code or result.state != self.expected_state:
            raise OAuthError("OAuth callback failed state/code validation.")
        return result

    def stop(self) -> None:
        self._done.set()
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                logger.debug("OAuth callback server shutdown raised", exc_info=False)
            try:
                self._server.server_close()
            except Exception:
                logger.debug("OAuth callback server close raised", exc_info=False)
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None


def wait_for_oauth_callback(
    *,
    host: str,
    port: int,
    path: str,
    expected_state: str,
    timeout_seconds: float = 300.0,
    on_ready: Any | None = None,
) -> CallbackResult:
    """Start a ready-gated localhost callback server, then wait for the redirect.

    ``on_ready`` is invoked only after the listener is accepting connections —
    use it to open the browser so an immediate redirect cannot race the bind.
    """
    server = OAuthCallbackServer(
        host=host,
        port=port,
        path=path,
        expected_state=expected_state,
    )
    try:
        server.start()
        if on_ready is not None:
            on_ready()
        return server.wait(timeout_seconds)
    finally:
        server.stop()


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

    host, port, path = validate_redirect_uri(settings.sf_redirect_uri)
    auth_url = oauth.build_authorization_url(pkce)
    logger.info("Starting local OAuth callback server on %s:%s%s", host, port, path)
    print("Open this URL to authorize Salesforce Account Engagement access:\n")
    print(auth_url)
    print()

    def _open_browser() -> None:
        if not open_browser:
            return
        try:
            webbrowser.open(auth_url)
        except Exception:
            logger.debug("Unable to open system browser", exc_info=False)

    # Listener is started and verified ready *before* on_ready opens the browser.
    try:
        callback = await asyncio.to_thread(
            wait_for_oauth_callback,
            host=host,
            port=port,
            path=path,
            expected_state=pkce.state,
            timeout_seconds=timeout_seconds,
            on_ready=_open_browser,
        )

        loaded = pkce_store.load()
        if loaded is None or loaded.state != pkce.state:
            raise OAuthError("Pending PKCE state missing or mismatched after callback.")
        if not hmac_compare(loaded.code_verifier, pkce.code_verifier):
            raise OAuthError("Pending PKCE verifier mismatch.")

        assert callback.code is not None
        tokens = await oauth.exchange_code(
            code=callback.code,
            code_verifier=loaded.code_verifier,
        )
    except Exception:
        # Always scrub pending verifier/state on any failure path.
        pkce_store.clear()
        raise
    else:
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
    return hmac.compare_digest(a, b)
