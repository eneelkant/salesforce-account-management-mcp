"""Application settings loaded from environment variables."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BU_ID_RE = re.compile(r"^0Uv[A-Za-z0-9]{15}$")


class Settings(BaseSettings):
    """Runtime configuration for the Account Engagement MCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Salesforce OAuth
    sf_client_id: str = Field(default="", alias="SF_CLIENT_ID")
    sf_client_secret: str = Field(default="", alias="SF_CLIENT_SECRET")
    sf_redirect_uri: str = Field(
        default="http://localhost:8765/oauth/callback",
        alias="SF_REDIRECT_URI",
    )
    sf_login_url: str = Field(default="https://login.salesforce.com", alias="SF_LOGIN_URL")
    sf_access_token: str = Field(default="", alias="SF_ACCESS_TOKEN")
    sf_refresh_token: str = Field(default="", alias="SF_REFRESH_TOKEN")
    sf_token_store_path: Path = Field(
        default=Path(".ae_tokens/tokens.json"),
        alias="SF_TOKEN_STORE_PATH",
    )

    # Account Engagement
    pardot_business_unit_id: str = Field(default="", alias="PARDOT_BUSINESS_UNIT_ID")
    pardot_api_version: int = Field(default=5, alias="PARDOT_API_VERSION")
    pardot_api_base_url: str = Field(
        default="https://pi.pardot.com",
        alias="PARDOT_API_BASE_URL",
    )

    # MCP transport
    mcp_transport: Literal["stdio", "streamable-http"] = Field(
        default="stdio",
        alias="MCP_TRANSPORT",
    )
    mcp_host: str = Field(default="127.0.0.1", alias="MCP_HOST")
    mcp_port: int = Field(default=8000, alias="MCP_PORT")

    # Security
    ae_read_only: bool = Field(default=True, alias="AE_READ_ONLY")
    ae_allow_create: bool = Field(default=False, alias="AE_ALLOW_CREATE")
    ae_allow_update: bool = Field(default=False, alias="AE_ALLOW_UPDATE")
    ae_allow_delete: bool = Field(default=False, alias="AE_ALLOW_DELETE")
    ae_require_write_confirmation: bool = Field(
        default=True,
        alias="AE_REQUIRE_WRITE_CONFIRMATION",
    )
    ae_require_delete_confirmation: bool = Field(
        default=True,
        alias="AE_REQUIRE_DELETE_CONFIRMATION",
    )
    ae_max_records: int = Field(default=200, ge=1, le=1000, alias="AE_MAX_RECORDS")
    ae_max_concurrent_requests: int = Field(
        default=5,
        ge=1,
        le=5,
        alias="AE_MAX_CONCURRENT_REQUESTS",
    )

    # HTTP
    ae_http_timeout_seconds: float = Field(default=30.0, alias="AE_HTTP_TIMEOUT_SECONDS")
    ae_http_max_retries: int = Field(default=3, ge=0, le=10, alias="AE_HTTP_MAX_RETRIES")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    ae_audit_log_path: str = Field(default="", alias="AE_AUDIT_LOG_PATH")

    @field_validator("pardot_business_unit_id")
    @classmethod
    def validate_business_unit_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        if not _BU_ID_RE.match(value):
            raise ValueError(
                "PARDOT_BUSINESS_UNIT_ID must start with '0Uv' and be 18 characters "
                "(Salesforce Setup → Business Unit Setup)."
            )
        return value

    @field_validator("pardot_api_version")
    @classmethod
    def validate_api_version(cls, value: int) -> int:
        if value != 5:
            raise ValueError("Only Account Engagement API v5 is supported.")
        return value

    @field_validator("pardot_api_base_url", "sf_login_url")
    @classmethod
    def validate_https_url(cls, value: str) -> str:
        value = value.rstrip("/")
        if not value.startswith("https://"):
            raise ValueError("URLs must use https://")
        return value

    @model_validator(mode="after")
    def enforce_read_only_defaults(self) -> Settings:
        if self.ae_read_only:
            object.__setattr__(self, "ae_allow_create", False)
            object.__setattr__(self, "ae_allow_update", False)
            object.__setattr__(self, "ae_allow_delete", False)
        return self

    @property
    def api_objects_base(self) -> str:
        return f"{self.pardot_api_base_url}/api/v{self.pardot_api_version}/objects"

    @property
    def allowed_api_hosts(self) -> frozenset[str]:
        from urllib.parse import urlparse

        host = urlparse(self.pardot_api_base_url).hostname
        return frozenset(
            h
            for h in (
                host,
                "pi.pardot.com",
                "pi.demo.pardot.com",
            )
            if h
        )

    def has_oauth_client(self) -> bool:
        return bool(self.sf_client_id)

    def has_refresh_token(self) -> bool:
        return bool(self.sf_refresh_token)

    def has_access_token(self) -> bool:
        return bool(self.sf_access_token)

    def auth_ready(self) -> bool:
        return bool(self.pardot_business_unit_id) and (
            self.has_access_token() or (self.has_oauth_client() and self.has_refresh_token())
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear settings cache (tests)."""
    get_settings.cache_clear()
