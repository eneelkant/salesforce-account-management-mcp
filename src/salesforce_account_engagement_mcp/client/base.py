"""Low-level async HTTP helpers shared by AE clients."""

from __future__ import annotations

from typing import Any

import httpx

from .errors import AccountEngagementAPIError, RateLimitError


def build_ae_headers(
    *,
    access_token: str,
    business_unit_id: str,
    return_api_usage: bool = True,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Pardot-Business-Unit-Id": business_unit_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if return_api_usage:
        headers["X-Return-Api-Usage"] = "true"
    return headers


def raise_for_ae_response(response: httpx.Response) -> None:
    """Map AE/Salesforce HTTP errors to structured exceptions."""
    if response.status_code < 400:
        return

    api_usage = response.headers.get("x-api-usage")
    code: str | int | None = None
    message = response.text[:500] or response.reason_phrase
    details: Any = None

    try:
        payload = response.json()
        if isinstance(payload, dict):
            details = payload
            code = payload.get("code")
            message = str(payload.get("message") or message)
    except Exception:
        details = None

    if response.status_code == 429 or (
        isinstance(message, str) and "limit" in message.lower() and response.status_code >= 400
    ):
        raise RateLimitError(
            "Account Engagement API rate or daily limit reached. "
            f"Details: {message}. Usage header: {api_usage or 'n/a'}.",
            status_code=response.status_code,
            code=code,
            details=details,
            api_usage=api_usage,
        )

    raise AccountEngagementAPIError(
        message,
        status_code=response.status_code,
        code=code,
        details=details,
        api_usage=api_usage,
    )


def extract_api_usage(response: httpx.Response) -> str | None:
    value = response.headers.get("x-api-usage") or response.headers.get("X-Api-Usage")
    return str(value) if value is not None else None
