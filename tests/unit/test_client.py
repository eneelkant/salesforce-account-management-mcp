"""API client, pagination, retry, and header tests."""

from __future__ import annotations

import httpx
import pytest
import respx

from salesforce_account_engagement_mcp.client.base import build_ae_headers
from salesforce_account_engagement_mcp.client.errors import (
    AccountEngagementAPIError,
    PaginationSafetyError,
    RateLimitError,
)
from salesforce_account_engagement_mcp.client.pagination import (
    merge_pages,
    validate_next_page_url,
)
from salesforce_account_engagement_mcp.config import Settings
from salesforce_account_engagement_mcp.runtime import AppRuntime


def test_build_headers() -> None:
    headers = build_ae_headers(access_token="tok", business_unit_id="0Uv000000000000001")
    assert headers["Authorization"] == "Bearer tok"
    assert headers["Pardot-Business-Unit-Id"] == "0Uv000000000000001"
    assert headers["Accept"] == "application/json"
    assert headers["X-Return-Api-Usage"] == "true"


def test_validate_next_page_url_rejects_bad_host() -> None:
    with pytest.raises(PaginationSafetyError):
        validate_next_page_url(
            "https://evil.example/api/v5/objects/prospects",
            frozenset({"pi.pardot.com"}),
        )


def test_validate_next_page_url_accepts_pi() -> None:
    url = validate_next_page_url(
        "https://pi.pardot.com/api/v5/objects/prospects?fields=id&nextPageToken=abc",
        frozenset({"pi.pardot.com"}),
    )
    assert url is not None


def test_merge_pages_respects_max_records() -> None:
    pages = [
        {"values": [{"id": 1}, {"id": 2}], "nextPageToken": "t"},
        {"values": [{"id": 3}], "nextPageToken": None},
    ]
    merged = merge_pages(pages, max_records=2)
    assert merged["count"] == 2
    assert merged["truncated"] is True


@pytest.mark.asyncio
async def test_query_prospects(runtime: AppRuntime) -> None:
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [{"id": 1, "email": "a@example.com", "password": "secret"}],
                    "nextPageToken": None,
                },
                headers={"x-api-usage": "10/1000"},
            )
        )
        result = await runtime.client.query("prospects", fields=["id", "email"], limit=10)
    assert result["count"] == 1
    assert runtime.client.last_api_usage == "10/1000"


@pytest.mark.asyncio
async def test_rate_limit_error(runtime: AppRuntime) -> None:
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                429,
                json={"code": 66, "message": "Daily API limit reached"},
            )
        )
        with pytest.raises(RateLimitError):
            await runtime.client.query("prospects", fields=["id"], limit=1)


@pytest.mark.asyncio
async def test_api_error_mapping(runtime: AppRuntime) -> None:
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects/99").mock(
            return_value=httpx.Response(
                404,
                json={"code": 3, "message": "Not found"},
            )
        )
        with pytest.raises(AccountEngagementAPIError) as exc:
            await runtime.client.read("prospects", 99, fields=["id"])
    assert exc.value.status_code == 404
    assert exc.value.code == 3


@pytest.mark.asyncio
async def test_create_not_retried_on_500(settings: Settings) -> None:
    runtime = AppRuntime.from_settings(settings)
    calls = {"n": 0}

    def _responder(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"code": 1, "message": "boom"})

    with respx.mock:
        respx.post("https://pi.pardot.com/api/v5/objects/prospects").mock(side_effect=_responder)
        with pytest.raises(AccountEngagementAPIError):
            await runtime.client.create("prospects", {"email": "x@y.com"}, fields="id")
    assert calls["n"] == 1
