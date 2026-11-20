"""Broader tool coverage to exercise remaining modules."""

from __future__ import annotations

import httpx
import pytest
import respx

from salesforce_account_engagement_mcp.runtime import AppRuntime
from salesforce_account_engagement_mcp.server import create_server
from tests.helpers import call_tool


@pytest.mark.asyncio
async def test_account_and_health_tools(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/account").mock(
            return_value=httpx.Response(200, json={"id": 1, "company": "Acme"})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 1}], "nextPageToken": None},
                headers={"x-api-usage": "1/25000"},
            )
        )
        account = await call_tool(server, "ae_get_account", {})
        bu = await call_tool(server, "ae_get_business_unit_info", {})
        health = await call_tool(server, "ae_get_api_health", {})
        usage = await call_tool(server, "ae_get_api_usage_status", {})
        sec = await call_tool(server, "ae_get_security_status", {})
    assert account["id"] == 1
    assert bu["business_unit_id"].startswith("0Uv")
    assert health["api_version"] == 5
    assert usage["api_usage"] == "1/25000"
    assert sec["permissions"]["read_only"] is True


@pytest.mark.asyncio
async def test_visitors_custom_fields_forms_tags_emails(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/visitors").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [{"id": 1, "ipAddress": "10.0.0.1"}],
                    "nextPageToken": None,
                },
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/visitors/1").mock(
            return_value=httpx.Response(
                200,
                json={"id": 1, "ipAddress": "10.0.0.1"},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/custom-fields").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 3, "name": "Industry"}], "nextPageToken": None},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/custom-fields/3").mock(
            return_value=httpx.Response(200, json={"id": 3, "name": "Industry", "type": "Text"})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/forms").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 8, "name": "Contact"}], "nextPageToken": None},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/forms/8").mock(
            return_value=httpx.Response(200, json={"id": 8, "name": "Contact"})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/tags").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 4, "name": "vip"}], "nextPageToken": None},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/list-emails").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 11, "name": "Newsletter"}], "nextPageToken": None},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/list-emails/11").mock(
            return_value=httpx.Response(200, json={"id": 11, "name": "Newsletter"})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/list-emails/11/stats").mock(
            return_value=httpx.Response(200, json={"sent": 100, "opens": 40})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/landing-pages").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 12, "name": "LP"}], "nextPageToken": None},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/landing-pages/12").mock(
            return_value=httpx.Response(200, json={"id": 12, "name": "LP"})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/lists").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [{"id": 1, "name": "Dynamic", "isDynamic": True}],
                    "nextPageToken": None,
                },
            )
        )

        visitors = await call_tool(server, "ae_list_visitors", {"limit": 5})
        visitor = await call_tool(server, "ae_get_visitor", {"visitor_id": 1})
        cfs = await call_tool(server, "ae_list_custom_fields", {})
        cf = await call_tool(server, "ae_get_custom_field", {"custom_field_id": 3})
        forms = await call_tool(server, "ae_list_forms", {})
        form = await call_tool(server, "ae_get_form", {"form_id": 8})
        tags = await call_tool(server, "ae_list_tags", {})
        emails = await call_tool(server, "ae_list_list_emails", {})
        email = await call_tool(server, "ae_get_list_email", {"list_email_id": 11})
        lps = await call_tool(server, "ae_list_landing_pages", {})
        lp = await call_tool(server, "ae_get_landing_page", {"landing_page_id": 12})
        dyn = await call_tool(server, "ae_list_dynamic_lists", {})
        ext = await call_tool(server, "ae_external_activities_status", {})

    assert visitors["values"][0]["ipAddress"] == "[REDACTED]"
    assert visitor["ipAddress"] == "[REDACTED]"
    assert cfs["count"] == 1
    assert cf["id"] == 3
    assert forms["count"] == 1
    assert form["id"] == 8
    assert tags["count"] == 1
    assert emails["count"] == 1
    assert email["stats"]["opens"] == 40
    assert lps["count"] == 1
    assert lp["id"] == 12
    assert "values" in dyn
    assert ext["supported"] is False


@pytest.mark.asyncio
async def test_search_and_report_tools(runtime: AppRuntime) -> None:
    server, _ = create_server(runtime.settings, runtime=runtime)
    with respx.mock:
        respx.get("https://pi.pardot.com/api/v5/objects/prospects").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [
                        {
                            "id": 1,
                            "email": "a@example.com",
                            "firstName": "Ada",
                            "company": "Analytical",
                            "score": 120,
                            "assignedToId": None,
                            "optedOut": False,
                            "grade": "A",
                            "campaignId": 5,
                        },
                        {
                            "id": 2,
                            "email": "b@example.com",
                            "firstName": "Bob",
                            "company": "Other",
                            "score": 10,
                            "assignedToId": 9,
                            "optedOut": True,
                            "grade": "C",
                            "campaignId": 6,
                        },
                    ],
                    "nextPageToken": None,
                },
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/prospects/1").mock(
            return_value=httpx.Response(
                200,
                json={"id": 1, "email": "a@example.com", "score": 120, "grade": "A"},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/visitor-activities").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [
                        {"id": 1, "type": 11, "typeName": "Email", "prospectId": 1},
                        {"id": 2, "type": 2, "typeName": "Form", "prospectId": 1},
                    ],
                    "nextPageToken": None,
                },
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/campaigns/5").mock(
            return_value=httpx.Response(200, json={"id": 5, "name": "Camp"})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/lists/1").mock(
            return_value=httpx.Response(200, json={"id": 1, "name": "L", "isDynamic": False})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/list-memberships").mock(
            return_value=httpx.Response(
                200,
                json={
                    "values": [{"id": 1, "listId": 1, "prospectId": 1}],
                    "nextPageToken": None,
                },
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/list-emails/11").mock(
            return_value=httpx.Response(200, json={"id": 11, "name": "N"})
        )
        respx.get("https://pi.pardot.com/api/v5/objects/list-emails/11/stats").mock(
            return_value=httpx.Response(200, json={"sent": 10})
        )

        searched = await call_tool(
            server,
            "ae_search_prospects",
            {"first_name": "Ada", "score_greater_than": 50, "limit": 50},
        )
        eng = await call_tool(server, "ae_get_prospect_engagement_summary", {"prospect_id": 1})
        camp = await call_tool(server, "ae_get_campaign_performance_summary", {"campaign_id": 5})
        top = await call_tool(
            server, "ae_get_top_engaged_prospects", {"limit": 10, "min_score": 50}
        )
        inactive = await call_tool(server, "ae_get_inactive_prospects", {"days_inactive": 30})
        life = await call_tool(server, "ae_get_prospect_lifecycle_summary", {"limit": 50})
        growth = await call_tool(server, "ae_get_list_growth_summary", {"list_id": 1})
        email = await call_tool(server, "ae_get_email_engagement_summary", {"list_email_id": 11})
        vis = await call_tool(server, "ae_get_visitor_activity_summary", {"days": 7})
        acts = await call_tool(server, "ae_list_visitor_activities", {"prospect_id": 1})
        csum = await call_tool(server, "ae_get_campaign_activity_summary", {"campaign_id": 5})
        perf = await call_tool(server, "ae_get_campaign_performance", {"campaign_id": 5})

    assert searched["count"] == 1
    assert searched["client_side_filters_applied"]["firstName"] == "Ada"
    assert eng["calculated"]["activity_type_counts"]["Email"] == 1
    assert camp["campaign"]["id"] == 5
    assert top["count"] >= 1
    assert "values" in inactive
    assert life["total_prospects_in_sample"] == 2
    assert growth["list_id"] == 1
    assert email["stats"]["sent"] == 10
    assert vis["records_examined"] == 2
    assert acts["count"] == 2
    assert csum["campaign_id"] == 5
    assert perf["metrics_source"] == "calculated_from_visitor_activities"


@pytest.mark.asyncio
async def test_write_custom_field_and_tag(write_settings, http_client) -> None:  # type: ignore[no-untyped-def]
    runtime = AppRuntime.from_settings(write_settings, http_client=http_client)
    server, _ = create_server(write_settings, runtime=runtime)
    with respx.mock:
        respx.post("https://pi.pardot.com/api/v5/objects/custom-fields").mock(
            return_value=httpx.Response(
                201,
                json={"id": 20, "name": "Region", "fieldId": "Region"},
            )
        )
        respx.patch("https://pi.pardot.com/api/v5/objects/custom-fields/20").mock(
            return_value=httpx.Response(200, json={"id": 20, "name": "Region2"})
        )
        respx.delete("https://pi.pardot.com/api/v5/objects/custom-fields/20").mock(
            return_value=httpx.Response(204)
        )
        respx.post("https://pi.pardot.com/api/v5/objects/tags").mock(
            return_value=httpx.Response(201, json={"id": 4, "name": "priority"})
        )
        created = await call_tool(
            server,
            "ae_create_custom_field",
            {
                "name": "Region",
                "field_id": "Region",
                "field_type": "Text",
                "confirm": True,
            },
        )
        updated = await call_tool(
            server,
            "ae_update_custom_field",
            {"custom_field_id": 20, "name": "Region2", "confirm": True},
        )
        deleted = await call_tool(
            server,
            "ae_delete_custom_field",
            {"custom_field_id": 20, "confirm": True, "confirm_id": 20},
        )
        tag = await call_tool(server, "ae_create_tag", {"name": "priority", "confirm": True})
    assert created["id"] == 20
    assert "Region2" in str(updated["name"])
    assert deleted["deleted"] is True
    assert tag["id"] == 4


@pytest.mark.asyncio
async def test_list_update_delete_and_membership_query(
    write_settings,
    http_client,
) -> None:  # type: ignore[no-untyped-def]
    runtime = AppRuntime.from_settings(write_settings, http_client=http_client)
    server, _ = create_server(write_settings, runtime=runtime)
    with respx.mock:
        respx.patch("https://pi.pardot.com/api/v5/objects/lists/7").mock(
            return_value=httpx.Response(200, json={"id": 7, "name": "Updated"})
        )
        respx.delete("https://pi.pardot.com/api/v5/objects/lists/7").mock(
            return_value=httpx.Response(204)
        )
        respx.get("https://pi.pardot.com/api/v5/objects/list-memberships").mock(
            return_value=httpx.Response(
                200,
                json={"values": [{"id": 1, "listId": 7, "prospectId": 2}], "nextPageToken": None},
            )
        )
        respx.get("https://pi.pardot.com/api/v5/objects/lists/7").mock(
            return_value=httpx.Response(200, json={"id": 7, "name": "Updated"})
        )
        respx.delete("https://pi.pardot.com/api/v5/objects/list-memberships/1").mock(
            return_value=httpx.Response(204)
        )
        updated = await call_tool(
            server,
            "ae_update_list",
            {"list_id": 7, "name": "Updated", "confirm": True},
        )
        members = await call_tool(server, "ae_get_list_members", {"list_id": 7})
        removed = await call_tool(
            server,
            "ae_remove_prospect_from_list",
            {"membership_id": 1, "confirm": True, "confirm_id": 1},
        )
        deleted = await call_tool(
            server,
            "ae_delete_list",
            {"list_id": 7, "confirm": True, "confirm_id": 7},
        )
    assert "Updated" in str(updated["name"])
    assert members["count"] == 1
    assert removed["deleted"] is True
    assert deleted["deleted"] is True
