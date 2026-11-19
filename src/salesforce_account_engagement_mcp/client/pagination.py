"""Safe pagination helpers for Account Engagement API v5."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .errors import PaginationSafetyError

# Official page-token expiry and hard record ceiling from Salesforce docs.
PAGE_TOKEN_TTL_HOURS = 4
MAX_PAGINATION_RECORDS = 100_000


def validate_next_page_url(url: str | None, allowed_hosts: frozenset[str]) -> str | None:
    """Validate nextPageUrl scheme/host before following it with OAuth credentials.

    Returns the URL if safe, None if empty, or raises PaginationSafetyError.
    """
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise PaginationSafetyError(
            f"Refusing non-HTTPS nextPageUrl scheme '{parsed.scheme}'.",
            status_code=400,
            code="unsafe_next_page_url",
        )
    host = parsed.hostname or ""
    if host not in allowed_hosts:
        raise PaginationSafetyError(
            f"Refusing nextPageUrl host '{host}'. Allowed: {sorted(allowed_hosts)}.",
            status_code=400,
            code="unsafe_next_page_url",
        )
    path = parsed.path or ""
    if "/api/v5/" not in path:
        raise PaginationSafetyError(
            "Refusing nextPageUrl that is not an Account Engagement API v5 path.",
            status_code=400,
            code="unsafe_next_page_url",
        )
    return url


def merge_pages(
    pages: list[dict[str, Any]],
    *,
    max_records: int,
) -> dict[str, Any]:
    """Combine paginated query responses into a single result envelope."""
    values: list[Any] = []
    warnings: list[str] = []
    next_page_token: str | None = None
    next_page_url: str | None = None
    truncated = False

    for page in pages:
        chunk = page.get("values") or []
        if not isinstance(chunk, list):
            continue
        remaining = max_records - len(values)
        if remaining <= 0:
            truncated = True
            break
        if len(chunk) > remaining:
            values.extend(chunk[:remaining])
            truncated = True
            next_page_token = page.get("nextPageToken")
            next_page_url = page.get("nextPageUrl")
            break
        values.extend(chunk)
        next_page_token = page.get("nextPageToken")
        next_page_url = page.get("nextPageUrl")
        warning = page.get("_pardot_warning")
        if warning:
            warnings.append(str(warning))

    if len(values) >= MAX_PAGINATION_RECORDS:
        truncated = True
        warnings.append("Reached Account Engagement 100,000-record pagination ceiling.")

    result: dict[str, Any] = {
        "values": values,
        "count": len(values),
        "nextPageToken": None if truncated else next_page_token,
        "nextPageUrl": None if truncated else next_page_url,
        "truncated": truncated,
        "data_source": "salesforce_account_engagement_api_v5",
    }
    if warnings:
        result["warnings"] = warnings
    return result
