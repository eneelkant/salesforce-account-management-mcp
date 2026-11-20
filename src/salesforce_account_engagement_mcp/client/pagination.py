"""Safe pagination helpers for Account Engagement API v5."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from .errors import PaginationSafetyError

# Official page-token expiry and hard record ceiling from Salesforce docs.
PAGE_TOKEN_TTL_HOURS = 4
MAX_PAGINATION_RECORDS = 100_000

# Exact AE API v5 objects collection path (optional object id / do-action suffix).
_AE_V5_OBJECTS_PATH = re.compile(
    r"^/api/v5/objects/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+(?:/do/[A-Za-z0-9_-]+)?)?/?$"
)


def validate_next_page_url(url: str | None, allowed_hosts: frozenset[str]) -> str | None:
    """Validate nextPageUrl before following it with OAuth credentials.

    Requires HTTPS, allowlisted host, default HTTPS port only, no userinfo, and an
    exact Account Engagement API v5 objects path.
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
    if parsed.username is not None or parsed.password is not None:
        raise PaginationSafetyError(
            "Refusing nextPageUrl that embeds username/password credentials.",
            status_code=400,
            code="unsafe_next_page_url",
        )
    # Also catch userinfo forms that urlparse may leave in netloc for odd inputs.
    netloc = parsed.netloc or ""
    if "@" in netloc:
        raise PaginationSafetyError(
            "Refusing nextPageUrl with userinfo ('@') in the authority.",
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
    # HTTPS must use the default port (443) or omit the port — no unexpected ports.
    if parsed.port is not None and parsed.port != 443:
        raise PaginationSafetyError(
            f"Refusing nextPageUrl with unexpected port {parsed.port} "
            "(HTTPS default port 443 only).",
            status_code=400,
            code="unsafe_next_page_url",
        )
    path = parsed.path or ""
    if not _AE_V5_OBJECTS_PATH.match(path):
        raise PaginationSafetyError(
            "Refusing nextPageUrl that is not an exact Account Engagement "
            "API v5 objects path (/api/v5/objects/...).",
            status_code=400,
            code="unsafe_next_page_url",
        )
    return url


def extract_next_page_token(page: dict[str, Any]) -> str | None:
    """Prefer explicit nextPageToken; fall back to token embedded in nextPageUrl."""
    token = page.get("nextPageToken")
    if token:
        return str(token)
    url = page.get("nextPageUrl")
    if not url:
        return None
    parsed = urlparse(str(url))
    values = parse_qs(parsed.query).get("nextPageToken") or []
    return values[0] if values else None


def merge_pages(
    pages: list[dict[str, Any]],
    *,
    max_records: int,
    hit_hard_ceiling: bool = False,
) -> dict[str, Any]:
    """Combine paginated query responses into a single result envelope.

    When truncated due to a caller max_records bound, the continuation token is
    preserved so clients can resume. The AE 100k hard ceiling clears continuation.
    """
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
            # Keep continuation so callers can resume after a soft max_records cut.
            next_page_token = extract_next_page_token(page)
            next_page_url = page.get("nextPageUrl")
            break
        values.extend(chunk)
        next_page_token = extract_next_page_token(page)
        next_page_url = page.get("nextPageUrl")
        warning = page.get("_pardot_warning")
        if warning:
            warnings.append(str(warning))

    if hit_hard_ceiling or len(values) >= MAX_PAGINATION_RECORDS:
        truncated = True
        next_page_token = None
        next_page_url = None
        warnings.append("Reached Account Engagement 100,000-record pagination ceiling.")

    result: dict[str, Any] = {
        "values": values,
        "count": len(values),
        "nextPageToken": next_page_token,
        "nextPageUrl": next_page_url,
        "truncated": truncated,
        "data_source": "salesforce_account_engagement_api_v5",
    }
    if warnings:
        result["warnings"] = warnings
    return result
