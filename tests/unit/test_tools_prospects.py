"""Prospect tool behaviour with mocked AE API."""

from __future__ import annotations

import httpx
import pytest
import respx

from salesforce_account_engagement_mcp.runtime import AppRuntime
from salesforce_account_engagement_mcp.server import create_server
from tests.helpers import call_tool as _call


@pytest.mark.asyncio
async def test_list_prospects_tool(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 1, "email": "a@example.com"}], "nextPageToken": None},
            )
        )
        out = await _call(server, "ae_list_prospects", {"limit": 10})
    assert out.get("count") == 1 or "values" in out


@pytest.mark.asyncio
async def test_create_blocked_in_read_only(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    out = await _call(
        server,
        "ae_create_prospect",
        {"email": "new@example.com", "confirm": True},
    )
    assert "error" in out
    assert out.get("operation") == "create"


@pytest.mark.asyncio
async def test_create_requires_confirm(write_settings, http_client) -> None:  # type: ignore[no-untyped-def]
    runtime = AppRuntime.from_settings(write_settings, http_client=http_client)
    server, _ = create_server(write_settings, runtime=runtime)
    out = await _call(server, "ae_create_prospect", {"email": "new@example.com", "confirm": False})
    assert "error" in out


@pytest.mark.asyncio
async def test_create_success(write_settings, http_client) -> None:  # type: ignore[no-untyped-def]
    runtime = AppRuntime.from_settings(write_settings, http_client=http_client)
    server, _ = create_server(write_settings, runtime=runtime)
    with respx.mock:
        respx.post("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                201,
                json={"id": 42, "email": "new@example.com"},
            )
        )
        out = await _call(
            server,
            "ae_create_prospect",
            {"email": "new@example.com", "confirm": True, "first_name": "Ada"},
        )
    assert out.get("id") == 42


@pytest.mark.asyncio
async def test_delete_requires_confirm_id(write_settings, http_client) -> None:  # type: ignore[no-untyped-def]
    runtime = AppRuntime.from_settings(write_settings, http_client=http_client)
    server, _ = create_server(write_settings, runtime=runtime)
    out = await _call(
        server,
        "ae_delete_prospect",
        {"prospect_id": 9, "confirm": True, "confirm_id": 8},
    )
    assert "error" in out
