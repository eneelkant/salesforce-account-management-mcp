"""Account Engagement campaign tools (read/query; not Salesforce CRM Campaigns)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import CAMPAIGN_DEFAULT_FIELDS, VISITOR_ACTIVITY_DEFAULT_FIELDS
from ..runtime import drop_none

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    note = (
        "These are Account Engagement campaigns (first-touch marketing tracking), "
        "not Salesforce CRM Campaign records."
    )

    @server.tool(name="ae_list_campaigns")
    async def ae_list_campaigns(
        fields: str = CAMPAIGN_DEFAULT_FIELDS,
        limit: int = 50,
        order_by: str = "id ASC",
        next_page_token: str | None = None,
        deleted: str | None = None,
    ) -> dict[str, Any]:
        """List Account Engagement campaigns (GET /api/v5/objects/campaigns)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "campaigns",
                fields=fields,
                filters=drop_none({"deleted": deleted}),
                limit=limit,
                order_by=order_by,
                next_page_token=next_page_token,
            )
            result["object_note"] = note
            return runtime.ok(
                result, tool_name="ae_list_campaigns", operation="read", record_type="campaign"
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_campaigns", operation="read")

    @server.tool(name="ae_get_campaign")
    async def ae_get_campaign(
        campaign_id: int,
        fields: str = CAMPAIGN_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Get one Account Engagement campaign by ID."""
        try:
            runtime.guard_read()
            result = await runtime.client.read("campaigns", campaign_id, fields=fields)
            result["object_note"] = note
            return runtime.ok(
                result,
                tool_name="ae_get_campaign",
                operation="read",
                record_type="campaign",
                record_id=campaign_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc, tool_name="ae_get_campaign", operation="read", record_id=campaign_id
            )

    @server.tool(name="ae_search_campaigns")
    async def ae_search_campaigns(
        fields: str = CAMPAIGN_DEFAULT_FIELDS,
        limit: int = 50,
        order_by: str = "updatedAt DESC",
        name: str | None = None,
        id_list: str | None = None,
        updated_at_after: str | None = None,
        created_at_after: str | None = None,
    ) -> dict[str, Any]:
        """Search Account Engagement campaigns with documented filters."""
        try:
            runtime.guard_read()
            filters = drop_none(
                {
                    "name": name,
                    "idList": id_list,
                    "updatedAtAfter": updated_at_after,
                    "createdAtAfter": created_at_after,
                }
            )
            result = await runtime.client.query(
                "campaigns",
                fields=fields,
                filters=filters,
                limit=limit,
                order_by=order_by,
            )
            result["object_note"] = note
            result["filters_applied"] = filters
            return runtime.ok(
                result, tool_name="ae_search_campaigns", operation="read", record_type="campaign"
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_search_campaigns", operation="read")

    @server.tool(name="ae_get_campaign_performance")
    async def ae_get_campaign_performance(
        campaign_id: int,
        activity_limit: int = 100,
    ) -> dict[str, Any]:
        """Summarize campaign-linked visitor activities (calculated from visitor-activities).

        Campaigns are read-only in API v5 (no native performance endpoint). Metrics are
        calculated from visitor-activities filtered by campaignId and clearly labeled.
        """
        try:
            runtime.guard_read()
            campaign = await runtime.client.read(
                "campaigns",
                campaign_id,
                fields=CAMPAIGN_DEFAULT_FIELDS,
            )
            activities = await runtime.client.query(
                "visitor-activities",
                fields=VISITOR_ACTIVITY_DEFAULT_FIELDS,
                filters={"campaignId": campaign_id},
                limit=activity_limit,
                order_by="createdAt DESC",
            )
            values = activities.get("values") or []
            type_counts: dict[str, int] = {}
            for item in values:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("typeName") or item.get("type") or "unknown")
                type_counts[key] = type_counts.get(key, 0) + 1
            payload = {
                "campaign": campaign,
                "object_note": note,
                "activity_sample_size": len(values),
                "activity_type_counts": type_counts,
                "metrics_source": "calculated_from_visitor_activities",
                "api_supplied_fields": list(campaign.keys()) if isinstance(campaign, dict) else [],
                "limitations": [
                    "No native campaign performance endpoint in API v5.",
                    f"Activity summary based on up to {activity_limit} recent visitor-activities.",
                    "Not a substitute for Account Engagement UI reports or email send stats.",
                ],
                "data_source": "salesforce_account_engagement_api_v5",
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_campaign_performance",
                operation="read",
                record_type="campaign",
                record_id=campaign_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_campaign_performance",
                operation="read",
                record_id=campaign_id,
            )
