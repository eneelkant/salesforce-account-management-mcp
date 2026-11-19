"""Salesforce OAuth 2.0 client (Authorization Code + PKCE and refresh)."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from ..logging_config import get_logger

logger = get_logger(__name__)

# Scopes required for Account Engagement API access
DEFAULT_SCOPES = "pardot_api refresh_token api"


class OAuthError(RuntimeError):
    """Raised when Salesforce OAuth fails."""


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str = ""
    instance_url: str = ""
    issued_at: float | None = None
    expires_in: int | None = None
    token_type: str = "Bearer"
    scope: str = ""


@dataclass
class PKCEChallenge:
    code_verifier: str
    code_challenge: str
    state: str


def generate_pkce() -> PKCEChallenge:
    """Generate PKCE code_verifier / S256 code_challenge and CSRF state."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(24)
    return PKCEChallenge(
        code_verifier=verifier,
        code_challenge=challenge,
        state=state,
    )


class SalesforceOAuthClient:
    """Salesforce OAuth helper for External Client Apps / Connected Apps."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str = "",
        redirect_uri: str,
        login_url: str = "https://login.salesforce.com",
        scopes: str = DEFAULT_SCOPES,
        timeout: float = 30.0,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.login_url = login_url.rstrip("/")
        self.scopes = scopes
        self.timeout = timeout

    @property
    def authorize_url(self) -> str:
        return f"{self.login_url}/services/oauth2/authorize"

    @property
    def token_url(self) -> str:
        return f"{self.login_url}/services/oauth2/token"

    def build_authorization_url(self, pkce: PKCEChallenge) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": pkce.state,
            "code_challenge": pkce.code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> OAuthTokens:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret
        return await self._token_request(data, http_client=http_client)

    async def refresh(
        self,
        refresh_token: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> OAuthTokens:
        if not refresh_token:
            raise OAuthError("No refresh token available.")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret
        tokens = await self._token_request(data, http_client=http_client)
        # Salesforce refresh responses may omit refresh_token; preserve prior.
        if not tokens.refresh_token:
            tokens.refresh_token = refresh_token
        return tokens

    async def _token_request(
        self,
        data: dict[str, str],
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> OAuthTokens:
        owns_client = http_client is None
        client = http_client or httpx.AsyncClient(timeout=self.timeout)
        try:
            logger.info("Requesting Salesforce OAuth token grant_type=%s", data.get("grant_type"))
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"},
            )
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code >= 400:
            detail = _safe_error_body(response)
            raise OAuthError(
                f"Salesforce OAuth token request failed ({response.status_code}): {detail}"
            )

        payload = response.json()
        return parse_token_response(payload)


def parse_token_response(payload: dict[str, Any]) -> OAuthTokens:
    """Validate and normalize a Salesforce OAuth token response."""
    access_token = payload.get("access_token")
    if not access_token or not isinstance(access_token, str):
        raise OAuthError("Salesforce OAuth response missing access_token.")

    issued_at: float | None = None
    raw_issued = payload.get("issued_at")
    if raw_issued is not None:
        try:
            # Salesforce returns milliseconds since epoch as a string.
            issued_at = float(raw_issued) / 1000.0
        except (TypeError, ValueError):
            issued_at = time.time()
    else:
        issued_at = time.time()

    expires_in: int | None = None
    if payload.get("expires_in") is not None:
        try:
            expires_in = int(payload["expires_in"])
        except (TypeError, ValueError):
            expires_in = None

    return OAuthTokens(
        access_token=access_token,
        refresh_token=str(payload.get("refresh_token") or ""),
        instance_url=str(payload.get("instance_url") or ""),
        issued_at=issued_at,
        expires_in=expires_in,
        token_type=str(payload.get("token_type") or "Bearer"),
        scope=str(payload.get("scope") or ""),
    )


def _safe_error_body(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            return str(body.get("error_description") or body.get("error") or body)
    except Exception:
        logger.debug("Unable to parse OAuth error body as JSON", exc_info=False)
    text = response.text[:200]
    return text or "unknown error"
