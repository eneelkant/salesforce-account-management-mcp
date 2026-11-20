"""Marketing intelligence / reporting tools with source-grounded metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..models.common import (
    LIST_MEMBERSHIP_DEFAULT_FIELDS,
    PROSPECT_DEFAULT_FIELDS,
    VISITOR_ACTIVITY_DEFAULT_FIELDS,
)

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def _period(days: int) -> dict[str, str]:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    return {
        "reporting_period_days": str(days),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
    }


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_get_prospect_engagement_summary")
    async def ae_get_prospect_engagement_summary(
        prospect_id: int,
        activity_limit: int = 200,
    ) -> dict[str, Any]:
        """Combine prospect fields with calculated activity engagement summary."""
        try:
            runtime.guard_read()
            prospect = await runtime.client.read(
                "prospects",
                prospect_id,
                fields=PROSPECT_DEFAULT_FIELDS,
            )
            activities = await runtime.client.query(
                "visitor-activities",
                fields=VISITOR_ACTIVITY_DEFAULT_FIELDS,
                filters={"prospectId": prospect_id},
                limit=activity_limit,
                order_by="createdAt DESC",
            )
            values = [v for v in (activities.get("values") or []) if isinstance(v, dict)]
            counts = Counter(str(v.get("typeName") or v.get("type") or "unknown") for v in values)
            payload = {
                "prospect": prospect,
                "records_examined": len(values),
                "activity_type_counts": dict(counts),
                "api_supplied": {
                    "score": prospect.get("score") if isinstance(prospect, dict) else None,
                    "grade": prospect.get("grade") if isinstance(prospect, dict) else None,
                    "lastActivityAt": (
                        prospect.get("lastActivityAt") if isinstance(prospect, dict) else None
                    ),
                },
                "calculated": {"activity_type_counts": dict(counts)},
                "metrics_source": "mixed_api_and_calculated",
                "data_source": "salesforce_account_engagement_api_v5",
                "limitations": [
                    f"Activity breakdown based on up to {activity_limit} recent activities.",
                    "Email delivery/bounce rates are not invented when stats are absent.",
                ],
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_prospect_engagement_summary",
                operation="read",
                record_type="prospect",
                record_id=prospect_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_prospect_engagement_summary",
                operation="read",
                record_id=prospect_id,
            )

    @server.tool(name="ae_get_campaign_performance_summary")
    async def ae_get_campaign_performance_summary(
        campaign_id: int,
        activity_limit: int = 200,
    ) -> dict[str, Any]:
        """Campaign performance summary grounded in campaign + visitor-activities data."""
        try:
            runtime.guard_read()
            # Reuse campaign performance logic via direct calls
            campaign = await runtime.client.read(
                "campaigns",
                campaign_id,
                fields="id,name,cost,createdAt,updatedAt,salesforceId",
            )
            activities = await runtime.client.query(
                "visitor-activities",
                fields=VISITOR_ACTIVITY_DEFAULT_FIELDS,
                filters={"campaignId": campaign_id},
                limit=activity_limit,
            )
            values = [v for v in (activities.get("values") or []) if isinstance(v, dict)]
            counts = Counter(str(v.get("typeName") or v.get("type") or "unknown") for v in values)
            payload = {
                "campaign": campaign,
                "records_examined": len(values),
                "activity_type_counts": dict(counts),
                "calculated": True,
                "metrics_source": "calculated_from_visitor_activities",
                "data_source": "salesforce_account_engagement_api_v5",
                "object_note": "Account Engagement campaign (not CRM Campaign).",
                "limitations": [
                    "No native AE v5 campaign ROI endpoint; values are sample-based counts.",
                ],
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_campaign_performance_summary",
                operation="read",
                record_type="campaign",
                record_id=campaign_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_campaign_performance_summary",
                operation="read",
                record_id=campaign_id,
            )

    @server.tool(name="ae_get_email_engagement_summary")
    async def ae_get_email_engagement_summary(
        list_email_id: int,
    ) -> dict[str, Any]:
        """Return list-email stats from the official /stats endpoint only (no invented metrics)."""
        try:
            runtime.guard_read()
            email = await runtime.client.read(
                "list-emails",
                list_email_id,
                fields="id,name,subject,campaignId,createdAt,updatedAt",
            )
            stats = await runtime.client.get_stats("list-emails", list_email_id)
            payload = {
                "list_email": email,
                "stats": stats,
                "metrics_source": "salesforce_api",
                "calculated": False,
                "data_source": "salesforce_account_engagement_api_v5",
                "limitations": [
                    "Only metrics returned by /list-emails/{id}/stats are included.",
                    "Missing keys mean the API did not supply them — they are not zero-filled.",
                ],
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_email_engagement_summary",
                operation="read",
                record_type="list_email",
                record_id=list_email_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_email_engagement_summary",
                operation="read",
                record_id=list_email_id,
            )

    @server.tool(name="ae_get_list_growth_summary")
    async def ae_get_list_growth_summary(
        list_id: int,
        membership_limit: int = 200,
        days: int = 30,
    ) -> dict[str, Any]:
        """Estimate recent list membership volume from a membership sample (calculated)."""
        try:
            runtime.guard_read()
            period = _period(days)
            await runtime.client.read("lists", list_id, fields="id,name,isDynamic")
            memberships = await runtime.client.query(
                "list-memberships",
                fields=LIST_MEMBERSHIP_DEFAULT_FIELDS,
                filters={"listId": list_id, "createdAtAfter": period["period_start"]},
                limit=membership_limit,
            )
            values = memberships.get("values") or []
            payload = {
                "list_id": list_id,
                **period,
                "filters_applied": {"listId": list_id, "createdAtAfter": period["period_start"]},
                "records_examined": len(values),
                "memberships_in_sample": len(values),
                "truncated": bool(memberships.get("nextPageToken")),
                "calculated": True,
                "metrics_source": "calculated_from_list_memberships_sample",
                "data_source": "salesforce_account_engagement_api_v5",
                "limitations": [
                    f"Sample capped at {membership_limit} memberships.",
                    "Not a complete historical growth curve.",
                ],
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_list_growth_summary",
                operation="read",
                record_type="list",
                record_id=list_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_list_growth_summary",
                operation="read",
                record_id=list_id,
            )

    @server.tool(name="ae_get_visitor_activity_summary")
    async def ae_get_visitor_activity_summary(
        days: int = 7,
        limit: int = 200,
        campaign_id: int | None = None,
    ) -> dict[str, Any]:
        """Summarize recent visitor activities across the BU (sample-based, calculated)."""
        try:
            runtime.guard_read()
            period = _period(days)
            filters: dict[str, Any] = {"createdAtAfter": period["period_start"]}
            if campaign_id is not None:
                filters["campaignId"] = campaign_id
            result = await runtime.client.query(
                "visitor-activities",
                fields=VISITOR_ACTIVITY_DEFAULT_FIELDS,
                filters=filters,
                limit=limit,
                order_by="createdAt DESC",
            )
            values = [v for v in (result.get("values") or []) if isinstance(v, dict)]
            counts = Counter(str(v.get("typeName") or v.get("type") or "unknown") for v in values)
            payload = {
                **period,
                "filters_applied": filters,
                "records_examined": len(values),
                "activity_type_counts": dict(counts),
                "calculated": True,
                "metrics_source": "calculated_from_visitor_activities",
                "data_source": "salesforce_account_engagement_api_v5",
                "limitations": [f"Based on up to {limit} activities in the period."],
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_visitor_activity_summary",
                operation="read",
                record_type="visitor_activity",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_visitor_activity_summary", operation="read")

    @server.tool(name="ae_get_top_engaged_prospects")
    async def ae_get_top_engaged_prospects(
        limit: int = 25,
        min_score: int | None = 50,
    ) -> dict[str, Any]:
        """Return prospects ordered by score (API-supplied score; not invented engagement)."""
        try:
            runtime.guard_read()
            # scoreGreaterThan is not a documented v5 query filter; fetch then filter client-side.
            result = await runtime.client.query(
                "prospects",
                fields=PROSPECT_DEFAULT_FIELDS,
                limit=max(limit, 100),
                order_by="score DESC",
            )
            values = [v for v in (result.get("values") or []) if isinstance(v, dict)]
            if min_score is not None:
                values = [
                    v for v in values if isinstance(v.get("score"), int) and v["score"] >= min_score
                ]
            values = values[:limit]
            result["values"] = values
            result["count"] = len(values)
            result["metrics_source"] = "salesforce_api_score_field_with_client_filter"
            result["calculated"] = True
            result["filters_applied"] = {"min_score": min_score}
            result["limitations"] = [
                "Ranking uses the Account Engagement score field.",
                "min_score is applied client-side (not a documented v5 query parameter).",
            ]
            return runtime.ok(
                result,
                tool_name="ae_get_top_engaged_prospects",
                operation="read",
                record_type="prospect",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_top_engaged_prospects", operation="read")

    @server.tool(name="ae_get_inactive_prospects")
    async def ae_get_inactive_prospects(
        days_inactive: int = 90,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Find prospects whose lastActivityAt is before the inactivity threshold."""
        try:
            runtime.guard_read()
            period = _period(days_inactive)
            cutoff = period["period_start"]
            result = await runtime.client.query(
                "prospects",
                fields=PROSPECT_DEFAULT_FIELDS,
                filters={"lastActivityAtBefore": cutoff},
                limit=limit,
                order_by="lastActivityAt ASC",
            )
            result["filters_applied"] = {
                "lastActivityAtBefore": cutoff,
                "days_inactive": days_inactive,
            }
            result["reporting_period"] = period
            result["metrics_source"] = "salesforce_api_lastActivityAt"
            result["calculated"] = False
            return runtime.ok(
                result,
                tool_name="ae_get_inactive_prospects",
                operation="read",
                record_type="prospect",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_inactive_prospects", operation="read")

    @server.tool(name="ae_find_duplicate_prospects")
    async def ae_find_duplicate_prospects(
        limit: int = 200,
    ) -> dict[str, Any]:
        """Detect duplicate emails within a prospect sample (calculated; AMPSEA-aware note)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "prospects",
                fields="id,email,firstName,lastName,company,updatedAt,score",
                limit=limit,
                order_by="email ASC",
            )
            values = [v for v in (result.get("values") or []) if isinstance(v, dict)]
            by_email: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in values:
                email = (row.get("email") or "").strip().lower()
                if email:
                    by_email[email].append(row)
            duplicates = [
                {"email": email, "count": len(rows), "prospects": rows}
                for email, rows in by_email.items()
                if len(rows) > 1
            ]
            payload = {
                "records_examined": len(values),
                "duplicate_email_groups": duplicates,
                "duplicate_group_count": len(duplicates),
                "calculated": True,
                "metrics_source": "calculated_from_prospect_sample",
                "data_source": "salesforce_account_engagement_api_v5",
                "limitations": [
                    f"Only examines first {limit} prospects from query.",
                    "AMPSEA orgs intentionally allow multiple prospects per email.",
                ],
            }
            return runtime.ok(
                payload,
                tool_name="ae_find_duplicate_prospects",
                operation="read",
                record_type="prospect",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_find_duplicate_prospects", operation="read")

    @server.tool(name="ae_get_prospect_lifecycle_summary")
    async def ae_get_prospect_lifecycle_summary(
        limit: int = 200,
    ) -> dict[str, Any]:
        """Summarize assignment / opt-out / score bands from a prospect sample (calculated)."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "prospects",
                fields=PROSPECT_DEFAULT_FIELDS,
                limit=limit,
            )
            values = [v for v in (result.get("values") or []) if isinstance(v, dict)]
            assigned = sum(1 for v in values if v.get("assignedToId"))
            unassigned = len(values) - assigned
            opted_out = sum(1 for v in values if v.get("optedOut") is True)
            high_score = sum(
                1 for v in values if isinstance(v.get("score"), int) and v["score"] >= 100
            )
            payload = {
                "records_examined": len(values),
                "total_prospects_in_sample": len(values),
                "assigned_prospects": assigned,
                "unassigned_prospects": unassigned,
                "opted_out_prospects": opted_out,
                "high_score_prospects_gte_100": high_score,
                "calculated": True,
                "metrics_source": "calculated_from_prospect_sample",
                "data_source": "salesforce_account_engagement_api_v5",
                "limitations": [
                    f"Sample capped at {limit}; not the full Business Unit population.",
                    "lifecycleStageId counts require field availability on returned records.",
                ],
            }
            return runtime.ok(
                payload,
                tool_name="ae_get_prospect_lifecycle_summary",
                operation="read",
                record_type="prospect",
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_prospect_lifecycle_summary",
                operation="read",
            )
