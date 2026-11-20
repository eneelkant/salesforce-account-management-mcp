"""Pagination continuation and safety tests."""

from __future__ import annotations

import httpx
import pytest
import respx

from salesforce_account_engagement_mcp.client.errors import PaginationSafetyError
from salesforce_account_engagement_mcp.client.pagination import (
    extract_next_page_token,
    merge_pages,
    validate_next_page_url,
)
from salesforce_account_engagement_mcp.runtime import AppRuntime


def test_extract_token_from_url() -> None:
    page = {
        "nextPageToken": None,
        "nextPageUrl": "https://pi.pardot.com/api/v5/objects/prospects?fields=id&nextPageToken=abc123",
    }
    assert extract_next_page_token(page) == "abc123"


def test_merge_preserves_token_on_soft_truncation() -> None:
    pages = [
        {
            "values": [{"id": 1}, {"id": 2}, {"id": 3}],
            "nextPageToken": "more",
            "nextPageUrl": "https://pi.pardot.com/api/v5/objects/prospects?nextPageToken=more",
        }
    ]
    merged = merge_pages(pages, max_records=2)
    assert merged["truncated"] is True
    assert merged["count"] == 2
    assert merged["nextPageToken"] == "more"


def test_merge_clears_token_on_hard_ceiling() -> None:
    pages = [{"values": [{"id": 1}], "nextPageToken": "x"}]
    merged = merge_pages(pages, max_records=10, hit_hard_ceiling=True)
    assert merged["nextPageToken"] is None
    assert merged["truncated"] is True


def test_validate_rejects_http_and_foreign_host() -> None:
    with pytest.raises(PaginationSafetyError):
        validate_next_page_url(
            "http://pi.pardot.com/api/v5/objects/prospects", frozenset({"pi.pardot.com"})
        )
    with pytest.raises(PaginationSafetyError):
        validate_next_page_url(
            "https://evil.example/api/v5/objects/prospects",
            frozenset({"pi.pardot.com"}),
        )


def test_validate_rejects_userinfo_and_unexpected_port() -> None:
    allowed = frozenset({"pi.pardot.com"})
    with pytest.raises(PaginationSafetyError, match=r"username/password|userinfo"):
        validate_next_page_url(
            "https://user:pass@pi.pardot.com/api/v5/objects/prospects",
            allowed,
        )
    with pytest.raises(PaginationSafetyError, match=r"unexpected port"):
        validate_next_page_url(
            "https://pi.pardot.com:8443/api/v5/objects/prospects",
            allowed,
        )


def test_validate_requires_exact_v5_objects_path() -> None:
    allowed = frozenset({"pi.pardot.com"})
    with pytest.raises(PaginationSafetyError, match=r"exact Account Engagement"):
        validate_next_page_url("https://pi.pardot.com/api/v5/query", allowed)
    with pytest.raises(PaginationSafetyError, match=r"exact Account Engagement"):
        validate_next_page_url("https://pi.pardot.com/api/v4/objects/prospects", allowed)
    # Valid exact paths still accepted
    assert (
        validate_next_page_url(
            "https://pi.pardot.com/api/v5/objects/prospects?fields=id&nextPageToken=x",
            allowed,
        )
        is not None
    )
    assert (
        validate_next_page_url(
            "https://pi.demo.pardot.com/api/v5/objects/list-memberships/12",
            frozenset({"pi.demo.pardot.com"}),
        )
        is not None
    )


@pytest.mark.asyncio
async def test_auto_paginate_with_next_page_token(runtime: AppRuntime) -> None:
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "values": [{"id": 1}],
                        "nextPageToken": "tok2",
                        "nextPageUrl": (
                            "https://pi.pardot.com/api/v5/objects/prospects"
                            "?fields=id&nextPageToken=tok2"
                        ),
                    },
                ),
                httpx.Response(
                    200,
                    json={"values": [{"id": 2}], "nextPageToken": None, "nextPageUrl": None},
                ),
            ]
        )
        result = await runtime.client.query(
            "prospects",
            fields=["id"],
            limit=10,
            max_records=10,
            auto_paginate=True,
        )
    assert result["count"] == 2
    assert {v["id"] for v in result["values"]} == {1, 2}
    assert result.get("nextPageToken") in {None, ""}


@pytest.mark.asyncio
async def test_auto_paginate_follows_validated_next_page_url(runtime: AppRuntime) -> None:
    """When token is absent but a safe nextPageUrl is present, follow the URL."""
    next_url = "https://pi.pardot.com/api/v5/objects/prospects?fields=id&nextPageToken=embedded"
    with respx.mock:
        # Register the specific continuation URL first so it is not swallowed by the base route.
        second = respx.get(url__eq=next_url).mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 11}], "nextPageToken": None, "nextPageUrl": None},
            )
        )
        first = respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [{"id": 10}],
                    "nextPageToken": None,
                    "nextPageUrl": next_url,
                },
            )
        )
        result = await runtime.client.query(
            "prospects",
            fields=["id"],
            limit=10,
            max_records=10,
            auto_paginate=True,
        )
    assert first.called
    assert second.called
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_auto_paginate_refuses_malicious_next_page_url(runtime: AppRuntime) -> None:
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [{"id": 1}],
                    "nextPageToken": None,
                    "nextPageUrl": "https://attacker.test/steal",
                },
            )
        )
        with pytest.raises(PaginationSafetyError):
            await runtime.client.query(
                "prospects",
                fields=["id"],
                limit=10,
                max_records=10,
                auto_paginate=True,
            )


@pytest.mark.asyncio
async def test_page_token_omits_filters_on_continuation(runtime: AppRuntime) -> None:
    with respx.mock:
        route = respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "values": [{"id": 1}],
                        "nextPageToken": "page2",
                        "nextPageUrl": None,
                    },
                ),
                httpx.Response(
                    200,
                    json={"values": [{"id": 2}], "nextPageToken": None},
                ),
            ]
        )
        await runtime.client.query(
            "prospects",
            fields=["id", "email"],
            filters={"email": "a@example.com"},
            limit=1,
            max_records=10,
            order_by="id ASC",
            auto_paginate=True,
        )
    assert len(route.calls) == 2
    second_url = str(route.calls[1].request.url)
    assert "nextPageToken=page2" in second_url
    assert "email=" not in second_url
    assert "orderBy=" not in second_url
    assert "limit=" not in second_url
    assert "fields=" in second_url
