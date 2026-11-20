"""Additional tool coverage for campaigns, lists, memberships, reports."""

from __future__ import annotations

import httpx
import pytest
import respx

from salesforce_account_engagement_mcp.runtime import AppRuntime
from salesforce_account_engagement_mcp.server import create_server
from tests.helpers import call_tool


@pytest.mark.asyncio
async def test_campaign_list_and_get(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/campaigns").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 5, "name": "Webinar"}], "nextPageToken": None},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/campaigns/5").mock(
            return_value=httpx.Response(200, json={"id": 5, "name": "Webinar"})
        )
        listed = await call_tool(server, "ae_list_campaigns", {"limit": 10})
        got = await call_tool(server, "ae_get_campaign", {"campaign_id": 5})
    assert listed["count"] == 1
    assert "Account Engagement" in listed.get("object_note", "")
    assert got["id"] == 5


@pytest.mark.asyncio
async def test_list_crud_guards(runtime: AppRuntime, write_settings, http_client) -> None:  # type: ignore[no-untyped-def]
    # read-only create fails
    server, _ = create_server(runtime.settings, runtime=runtime)
    blocked = await call_tool(server, "ae_create_list", {"name": "Nurture", "confirm": True})
    assert "error" in blocked

    write_runtime = AppRuntime.from_settings(write_settings, http_client=http_client)
    write_server, _ = create_server(write_settings, runtime=write_runtime)
    with respx.mock:
        respx.post("https://pi.pardot.com/api/v5/objects/lists").mock(
            return_value=httpx.Response(201, json={"id": 7, "name": "Nurture"})
        )
        created = await call_tool(
            write_server,
            "ae_create_list",
            {"name": "Nurture", "confirm": True},
        )
    assert created["id"] == 7


@pytest.mark.asyncio
async def test_membership_add(write_settings, http_client) -> None:  # type: ignore[no-untyped-def]
    runtime = AppRuntime.from_settings(write_settings, http_client=http_client)
    server, _ = create_server(write_settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/lists/1").mock(
            return_value=httpx.Response(200, json={"id": 1, "name": "L"})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/prospects/2").mock(
            return_value=httpx.Response(200, json={"id": 2, "email": "a@b.com"})
        )
        respx.post("https://pi.pardot.com/api/v5/objects/list-memberships").mock(
            return_value=httpx.Response(
                201,
                json={"id": 99, "listId": 1, "prospectId": 2},
            )
        )
        out = await call_tool(
            server,
            "ae_add_prospect_to_list",
            {"list_id": 1, "prospect_id": 2, "confirm": True},
        )
    assert out["id"] == 99


@pytest.mark.asyncio
async def test_visitor_activities_and_reports(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/visitor-activities").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [
                        {
                            "id": 1,
                            "prospectId": 9,
                            "type": 11,
                            "typeName": "Email",
                            "details": "Welcome",
                        }
                    ],
                    "nextPageToken": None,
                },
            )
        )
        summary = await call_tool(
            server,
            "ae_get_prospect_activity_summary",
            {"prospect_id": 9, "limit": 50},
        )
    assert summary["records_examined"] == 1
    assert summary["metrics_source"] == "calculated_from_visitor_activities"
    assert "Email" in summary["activity_type_counts"]


@pytest.mark.asyncio
async def test_engagement_studio_unsupported(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    out = await call_tool(server, "ae_engagement_studio_status", {})
    assert out["supported"] is False


@pytest.mark.asyncio
async def test_tool_catalogue(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    out = await call_tool(server, "ae_get_tool_catalogue", {})
    assert out["tool_count"] >= 40
    assert "ae_list_prospects" in out["tools"]


@pytest.mark.asyncio
async def test_check_connection(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 1}], "nextPageToken": None},
            )
        )
        out = await call_tool(server, "ae_check_connection", {})
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_find_duplicates(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [
                        {"id": 1, "email": "dup@example.com"},
                        {"id": 2, "email": "dup@example.com"},
                        {"id": 3, "email": "unique@example.com"},
                    ],
                    "nextPageToken": None,
                },
            )
        )
        out = await call_tool(server, "ae_find_duplicate_prospects", {"limit": 50})
    assert out["duplicate_group_count"] == 1
    assert out["calculated"] is True
