"""Structured Account Engagement API errors."""

from __future__ import annotations

from typing import Any


class AccountEngagementAPIError(Exception):
    """Raised for non-success AE API responses."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | int | None = None,
        details: Any = None,
        api_usage: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details
        self.api_usage = api_usage

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.message,
            "status_code": self.status_code,
            "code": self.code,
            "details": self.details,
            "api_usage": self.api_usage,
        }


class RateLimitError(AccountEngagementAPIError):
    """Raised when daily or concurrency limits are hit."""


class PaginationSafetyError(AccountEngagementAPIError):
    """Raised when a nextPageUrl fails hostname/scheme validation."""


class AuthenticationRequiredError(AccountEngagementAPIError):
    """Raised when credentials/BU are missing."""
