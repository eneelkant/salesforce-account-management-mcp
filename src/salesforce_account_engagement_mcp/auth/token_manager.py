"""Token manager with expiry tracking and refresh locking."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .oauth import OAuthError, OAuthTokens, SalesforceOAuthClient
from .token_store import StoredTokens, TokenStore

if TYPE_CHECKING:
    from ..config import Settings

logger = get_logger(__name__)

# Refresh this many seconds before expiry when expires_in is known.
_REFRESH_SKEW_SECONDS = 60
# If Salesforce omits expires_in, refresh after this many seconds.
_DEFAULT_ACCESS_TOKEN_TTL = 3600


class TokenManager:
    """Provide valid access tokens, refreshing under an asyncio lock."""

    def __init__(
        self,
        settings: Settings,
        *,
        oauth_client: SalesforceOAuthClient | None = None,
        store: TokenStore | None = None,
    ) -> None:
        self.settings = settings
        self.store = store or TokenStore(settings.sf_token_store_path)
        self.oauth = oauth_client or (
            SalesforceOAuthClient(
                client_id=settings.sf_client_id,
                client_secret=settings.sf_client_secret,
                redirect_uri=settings.sf_redirect_uri,
                login_url=settings.sf_login_url,
            )
            if settings.has_oauth_client()
            else None
        )
        self._lock = asyncio.Lock()
        self._tokens = self._bootstrap_tokens()

    def _bootstrap_tokens(self) -> OAuthTokens | None:
        stored = self.store.load()
        if stored and stored.access_token:
            return OAuthTokens(
                access_token=stored.access_token,
                refresh_token=stored.refresh_token or self.settings.sf_refresh_token,
                instance_url=stored.instance_url,
                issued_at=stored.issued_at,
                expires_in=stored.expires_in,
                token_type=stored.token_type,
                scope=stored.scope,
            )
        if self.settings.sf_access_token or self.settings.sf_refresh_token:
            return OAuthTokens(
                access_token=self.settings.sf_access_token,
                refresh_token=self.settings.sf_refresh_token,
                issued_at=time.time() if self.settings.sf_access_token else None,
            )
        return None

    def _persist(self, tokens: OAuthTokens) -> None:
        self._tokens = tokens
        self.store.save(
            StoredTokens(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                instance_url=tokens.instance_url,
                issued_at=tokens.issued_at,
                expires_in=tokens.expires_in,
                token_type=tokens.token_type,
                scope=tokens.scope,
            )
        )

    def is_expired(self, tokens: OAuthTokens | None = None, *, now: float | None = None) -> bool:
        tokens = tokens or self._tokens
        if tokens is None or not tokens.access_token:
            return True
        now = time.time() if now is None else now
        issued = tokens.issued_at or 0.0
        ttl = tokens.expires_in if tokens.expires_in is not None else _DEFAULT_ACCESS_TOKEN_TTL
        return now >= (issued + ttl - _REFRESH_SKEW_SECONDS)

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        async with self._lock:
            if (
                not force_refresh
                and self._tokens
                and self._tokens.access_token
                and not self.is_expired(self._tokens)
            ):
                return self._tokens.access_token
            await self._refresh_locked()
            if not self._tokens or not self._tokens.access_token:
                raise OAuthError(
                    "No Salesforce access token available. Configure SF_ACCESS_TOKEN "
                    "or SF_REFRESH_TOKEN + SF_CLIENT_ID, or complete the OAuth flow."
                )
            return self._tokens.access_token

    async def _refresh_locked(self) -> None:
        refresh_token = ""
        if self._tokens and self._tokens.refresh_token:
            refresh_token = self._tokens.refresh_token
        elif self.settings.sf_refresh_token:
            refresh_token = self.settings.sf_refresh_token

        if not refresh_token:
            if self._tokens and self._tokens.access_token and not self.is_expired(self._tokens):
                return
            if self._tokens and self._tokens.access_token:
                # Access token present but expired, and no refresh token.
                raise OAuthError("Access token expired and no refresh token is configured.")
            raise OAuthError("No refresh token available for Salesforce OAuth.")

        if self.oauth is None:
            raise OAuthError("SF_CLIENT_ID is required to refresh Salesforce OAuth tokens.")

        logger.info("Refreshing Salesforce access token")
        tokens = await self.oauth.refresh(refresh_token)
        self._persist(tokens)

    def update_from_oauth(self, tokens: OAuthTokens) -> None:
        """Persist tokens obtained outside the refresh path (e.g. auth code)."""
        self._persist(tokens)

    def snapshot(self) -> dict[str, str | bool | None]:
        """Non-secret auth status for diagnostics."""
        tokens = self._tokens
        return {
            "has_access_token": bool(tokens and tokens.access_token),
            "has_refresh_token": bool(
                (tokens and tokens.refresh_token) or self.settings.sf_refresh_token
            ),
            "has_oauth_client": self.settings.has_oauth_client(),
            "is_expired": self.is_expired(tokens) if tokens else True,
            "instance_url": tokens.instance_url if tokens else None,
            "scope": tokens.scope if tokens else None,
        }
