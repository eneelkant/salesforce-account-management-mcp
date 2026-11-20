"""Visitor activity analytics tools."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from ..models.common import VISITOR_ACTIVITY_DEFAULT_FIELDS
from ..runtime import drop_none

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_visitor_activities")
    async def ae_list_visitor_activities(
        fields: str = VISITOR_ACTIVITY_DEFAULT_FIELDS,
        limit: int = 50,
        prospect_id: int | None = None,
        visitor_id: int | None = None,
        activity_type: int | None = None,
        created_at_after: str | None = None,
        created_at_before: str | None = None,
        next_page_token: str | None = None,
    ) -> dict[str, Any]:
        """List visitor activities (page views, form submits, email opens/clicks, etc.)."""
        try:
            runtime.guard_read()
            filters = drop_none(
                {
                    "prospectId": prospect_id,
                    "visitorId": visitor_id,
                    "type": activity_type,
                    "createdAtAfter": created_at_after,
                    "createdAtBefore": created_at_before,
                }
            )
            result = await runtime.client.query(
                "visitor-activities",
                fields=fields,
                filters=filters,
                limit=limit,
                order_by="createdAt DESC",
                next_page_token=next_page_token,
            )
            return runtime.ok(
                result,
                tool_name="ae_list_visitor_activities",
                operation="read",
                record_type="visitor_activity",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_visitor_activities", operation="read")

    @server.tool(name="ae_get_prospect_activities")
    async def ae_get_prospect_activities(
        prospect_id: int,
        fields: str = VISITOR_ACTIVITY_DEFAULT_FIELDS,
        limit: int = 100,
        created_at_after: str | None = None,
    ) -> dict[str, Any]:
        """Get visitor activities for a specific prospect."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "visitor-activities",
                fields=fields,
                filters=drop_none({"prospectId": prospect_id, "createdAtAfter": created_at_after}),
                limit=limit,
                order_by="createdAt DESC",
            )
            result["prospect_id"] = prospect_id
            return runtime.ok(
                result,
                tool_name="ae_get_prospect_activities",
                operation="read",
                record_type="visitor_activity",
                record_id=prospect_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_prospect_activities",
                operation="read",
                record_id=prospect_id,
            )

    @server.tool(name="ae_get_prospect_activity_summary")
    async def ae_get_prospect_activity_summary(
        prospect_id: int,
        limit: int = 200,
    ) -> dict[str, Any]:
        """Calculate an activity-type summary for a prospect from visitor-activities samples."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "visitor-activities",
                fields=VISITOR_ACTIVITY_DEFAULT_FIELDS,
                filters={"prospectId": prospect_id},
                limit=limit,
                order_by="createdAt DESC",
            )
            values = [v for v in (result.get("values") or []) if isinstance(v, dict)]
            counts = Counter(str(v.get("typeName") or v.get("type") or "unknown") for v in values)
            payload = {
                "prospect_id": prospect_id,
                "records_examined": len(values),
                "activity_type_counts": dict(counts),
                "latest_activity_at": values[0].get("createdAt") if values else None,
                "metrics_source": "calculated_from_visitor_activities",
                "data_source": "salesforce_account_engagement_api_v5",
                "limitations": [
                    f"Summary based on up to {limit} most recent activities.",
                    "Not a complete historical export.",
                ],
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_prospect_activity_summary",
                operation="read",
                record_type="visitor_activity",
                record_id=prospect_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_prospect_activity_summary",
                operation="read",
                record_id=prospect_id,
            )

    @server.tool(name="ae_get_campaign_activity_summary")
    async def ae_get_campaign_activity_summary(
        campaign_id: int,
        limit: int = 200,
    ) -> dict[str, Any]:
        """Calculate visitor-activity type counts for an Account Engagement campaign."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "visitor-activities",
                fields=VISITOR_ACTIVITY_DEFAULT_FIELDS,
                filters={"campaignId": campaign_id},
                limit=limit,
                order_by="createdAt DESC",
            )
            values = [v for v in (result.get("values") or []) if isinstance(v, dict)]
            counts = Counter(str(v.get("typeName") or v.get("type") or "unknown") for v in values)
            payload = {
                "campaign_id": campaign_id,
                "records_examined": len(values),
                "activity_type_counts": dict(counts),
                "metrics_source": "calculated_from_visitor_activities",
                "data_source": "salesforce_account_engagement_api_v5",
                "object_note": "Account Engagement campaign, not Salesforce CRM Campaign.",
                "limitations": [f"Based on up to {limit} recent visitor-activities."],
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_campaign_activity_summary",
                operation="read",
                record_type="campaign",
                record_id=campaign_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_campaign_activity_summary",
                operation="read",
                record_id=campaign_id,
            )
