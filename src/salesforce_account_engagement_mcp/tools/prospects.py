"""Prospect management tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.common import PROSPECT_DEFAULT_FIELDS
from ..runtime import drop_none

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ..runtime import AppRuntime


def register(server: MCPServer, runtime: AppRuntime) -> None:
    @server.tool(name="ae_list_prospects")
    async def ae_list_prospects(
        fields: str = PROSPECT_DEFAULT_FIELDS,
        limit: int = 50,
        order_by: str = "id ASC",
        next_page_token: str | None = None,
        email: str | None = None,
        assigned_to_id: int | None = None,
        created_at_after: str | None = None,
        updated_at_after: str | None = None,
        last_activity_at_before: str | None = None,
        deleted: str | None = None,
    ) -> dict[str, Any]:
        """List Account Engagement prospects with documented v5 query filters.

        Uses GET /api/v5/objects/prospects. Supported API filters include email,
        assignedToId, createdAt*, updatedAt*, lastActivityAt*, userId, deleted.
        Never returns password fields.
        """
        try:
            runtime.guard_read()
            filters = drop_none(
                {
                    "email": email,
                    "assignedToId": assigned_to_id,
                    "createdAtAfter": created_at_after,
                    "updatedAtAfter": updated_at_after,
                    "lastActivityAtBefore": last_activity_at_before,
                    "deleted": deleted,
                }
            )
            result = await runtime.client.query(
                "prospects",
                fields=fields,
                filters=filters,
                limit=limit,
                order_by=order_by,
                next_page_token=next_page_token,
            )
            result["filters_applied"] = filters
            return runtime.ok(
                result,
                tool_name="ae_list_prospects",
                operation="read",
                record_type="prospect",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_list_prospects", operation="read")

    @server.tool(name="ae_get_prospect")
    async def ae_get_prospect(
        prospect_id: int,
        fields: str = PROSPECT_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Get a single prospect by Account Engagement ID."""
        try:
            runtime.guard_read()
            result = await runtime.client.read("prospects", prospect_id, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_get_prospect",
                operation="read",
                record_type="prospect",
                record_id=prospect_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_get_prospect",
                operation="read",
                record_id=prospect_id,
            )

    @server.tool(name="ae_get_prospect_by_email")
    async def ae_get_prospect_by_email(
        email: str,
        fields: str = PROSPECT_DEFAULT_FIELDS,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Find prospects by email. With AMPSEA enabled, multiple prospects may share an email."""
        try:
            runtime.guard_read()
            result = await runtime.client.query(
                "prospects",
                fields=fields,
                filters={"email": email},
                limit=limit,
            )
            result["query"] = {"email": email}
            result["note"] = (
                "AMPSEA orgs may return multiple prospects for one email. "
                "Prefer id-based operations for updates/deletes."
            )
            return runtime.ok(
                result,
                tool_name="ae_get_prospect_by_email",
                operation="read",
                record_type="prospect",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_get_prospect_by_email", operation="read")

    @server.tool(name="ae_search_prospects")
    async def ae_search_prospects(
        fields: str = PROSPECT_DEFAULT_FIELDS,
        limit: int = 100,
        order_by: str = "updatedAt DESC",
        email: str | None = None,
        assigned_to_id: int | None = None,
        user_id: int | None = None,
        created_at_after: str | None = None,
        created_at_before: str | None = None,
        updated_at_after: str | None = None,
        updated_at_before: str | None = None,
        last_activity_at_after: str | None = None,
        last_activity_at_before: str | None = None,
        # Client-side filters (not documented as v5 query params)
        first_name: str | None = None,
        last_name: str | None = None,
        company: str | None = None,
        campaign_id: int | None = None,
        grade: str | None = None,
        score_greater_than: int | None = None,
        score_less_than: int | None = None,
    ) -> dict[str, Any]:
        """Search prospects using documented v5 API filters plus optional client-side filters.

        API filters (server-side): email, assignedToId, userId, createdAt*, updatedAt*,
        lastActivityAt*, id*. Client-side filters (first/last name, company, campaignId,
        grade, score bands) are applied after fetch and labeled as calculated filtering.
        """
        try:
            runtime.guard_read()
            api_filters = drop_none(
                {
                    "email": email,
                    "assignedToId": assigned_to_id,
                    "userId": user_id,
                    "createdAtAfter": created_at_after,
                    "createdAtBefore": created_at_before,
                    "updatedAtAfter": updated_at_after,
                    "updatedAtBefore": updated_at_before,
                    "lastActivityAtAfter": last_activity_at_after,
                    "lastActivityAtBefore": last_activity_at_before,
                }
            )
            result = await runtime.client.query(
                "prospects",
                fields=fields,
                filters=api_filters,
                limit=limit,
                order_by=order_by,
            )
            values = [v for v in (result.get("values") or []) if isinstance(v, dict)]
            client_filters = drop_none(
                {
                    "firstName": first_name,
                    "lastName": last_name,
                    "company": company,
                    "campaignId": campaign_id,
                    "grade": grade,
                    "scoreGreaterThan": score_greater_than,
                    "scoreLessThan": score_less_than,
                }
            )
            filtered = values
            if first_name:
                filtered = [
                    v
                    for v in filtered
                    if str(v.get("firstName") or "").lower() == first_name.lower()
                ]
            if last_name:
                filtered = [
                    v for v in filtered if str(v.get("lastName") or "").lower() == last_name.lower()
                ]
            if company:
                filtered = [
                    v for v in filtered if company.lower() in str(v.get("company") or "").lower()
                ]
            if campaign_id is not None:
                filtered = [v for v in filtered if v.get("campaignId") == campaign_id]
            if grade:
                filtered = [v for v in filtered if str(v.get("grade") or "") == grade]
            if score_greater_than is not None:
                filtered = [
                    v
                    for v in filtered
                    if isinstance(v.get("score"), int) and v["score"] > score_greater_than
                ]
            if score_less_than is not None:
                filtered = [
                    v
                    for v in filtered
                    if isinstance(v.get("score"), int) and v["score"] < score_less_than
                ]
            result["values"] = filtered
            result["count"] = len(filtered)
            result["api_filters_applied"] = api_filters
            result["client_side_filters_applied"] = client_filters
            result["records_examined"] = len(values)
            if client_filters:
                result["filter_note"] = (
                    "Name/company/campaign/grade/score filters are applied client-side "
                    "on the API result sample because they are not documented v5 query params."
                )
            return runtime.ok(
                result,
                tool_name="ae_search_prospects",
                operation="read",
                record_type="prospect",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_search_prospects", operation="read")

    @server.tool(name="ae_create_prospect")
    async def ae_create_prospect(
        email: str,
        confirm: bool = False,
        first_name: str | None = None,
        last_name: str | None = None,
        company: str | None = None,
        job_title: str | None = None,
        phone: str | None = None,
        website: str | None = None,
        campaign_id: int | None = None,
        score: int | None = None,
        source: str | None = None,
        user_id: int | None = None,
        fields: str = PROSPECT_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Create a prospect (POST /api/v5/objects/prospects). Requires write permissions + confirm."""
        try:
            runtime.guard_create(confirm=confirm, target=f"prospect email={email}")
            body = drop_none(
                {
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "company": company,
                    "jobTitle": job_title,
                    "phone": phone,
                    "website": website,
                    "campaignId": campaign_id,
                    "score": score,
                    "source": source,
                    "userId": user_id,
                }
            )
            result = await runtime.client.create("prospects", body, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_create_prospect",
                operation="create",
                record_type="prospect",
                record_id=(result or {}).get("id") if isinstance(result, dict) else None,
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_create_prospect", operation="create")

    @server.tool(name="ae_update_prospect")
    async def ae_update_prospect(
        prospect_id: int,
        confirm: bool = False,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        company: str | None = None,
        job_title: str | None = None,
        phone: str | None = None,
        website: str | None = None,
        campaign_id: int | None = None,
        score: int | None = None,
        source: str | None = None,
        user_id: int | None = None,
        opted_out: bool | None = None,
        is_do_not_email: bool | None = None,
        fields: str = PROSPECT_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Update a prospect by ID (PATCH). Requires write permissions + confirm."""
        try:
            runtime.guard_update(confirm=confirm, target=f"prospect id={prospect_id}")
            body = drop_none(
                {
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "company": company,
                    "jobTitle": job_title,
                    "phone": phone,
                    "website": website,
                    "campaignId": campaign_id,
                    "score": score,
                    "source": source,
                    "userId": user_id,
                    "optedOut": opted_out,
                    "isDoNotEmail": is_do_not_email,
                }
            )
            if not body:
                return {"error": "No fields provided to update.", "prospect_id": prospect_id}
            result = await runtime.client.update("prospects", prospect_id, body, fields=fields)
            return runtime.ok(
                result,
                tool_name="ae_update_prospect",
                operation="update",
                record_type="prospect",
                record_id=prospect_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_update_prospect",
                operation="update",
                record_id=prospect_id,
            )

    @server.tool(name="ae_upsert_prospect")
    async def ae_upsert_prospect(
        email: str,
        confirm: bool = False,
        first_name: str | None = None,
        last_name: str | None = None,
        company: str | None = None,
        campaign_id: int | None = None,
        score: int | None = None,
        fields: str = PROSPECT_DEFAULT_FIELDS,
    ) -> dict[str, Any]:
        """Upsert the most recently active prospect by email (POST .../do/upsertLatestByEmail)."""
        try:
            runtime.guard_create(confirm=confirm, target=f"prospect upsert email={email}")
            prospect_body = drop_none(
                {
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "company": company,
                    "campaignId": campaign_id,
                    "score": score,
                }
            )
            # Official upsertLatestByEmail body: MatchEmail + Prospect (+ Fields)
            body = {
                "MatchEmail": email,
                "Prospect": prospect_body,
                "Fields": fields,
            }
            result = await runtime.client.action(
                "prospects",
                "upsertLatestByEmail",
                body=body,
                fields=fields,
            )
            return runtime.ok(
                result,
                tool_name="ae_upsert_prospect",
                operation="upsert",
                record_type="prospect",
            )
        except Exception as exc:
            return runtime.fail(exc, tool_name="ae_upsert_prospect", operation="upsert")

    @server.tool(name="ae_delete_prospect")
    async def ae_delete_prospect(
        prospect_id: int,
        confirm: bool = False,
        confirm_id: int | None = None,
    ) -> dict[str, Any]:
        """Delete a prospect by ID. Requires AE_ALLOW_DELETE and confirm_id == prospect_id."""
        try:
            runtime.guard_delete(
                confirm=confirm,
                target=f"prospect id={prospect_id}",
                record_id=prospect_id,
                confirm_id=confirm_id,
            )
            result = await runtime.client.delete("prospects", prospect_id)
            return runtime.ok(
                {"deleted": True, "prospect_id": prospect_id, **(result or {})},
                tool_name="ae_delete_prospect",
                operation="delete",
                record_type="prospect",
                record_id=prospect_id,
            )
        except Exception as exc:
            return runtime.fail(
                exc,
                tool_name="ae_delete_prospect",
                operation="delete",
                record_id=prospect_id,
            )
