"""Optional live sandbox smoke — skipped unless RUN_AE_INTEGRATION=1.

Read-only only. Requires sandbox Salesforce / Account Engagement credentials.
Never prints tokens, emails, or other PII — assertions use sanitized shapes.

Do NOT enable this in CI without an explicit sandbox secret store + approval.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from salesforce_account_engagement_mcp.config import Settings, reset_settings_cache
from salesforce_account_engagement_mcp.runtime import AppRuntime

pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return os.getenv("RUN_AE_INTEGRATION") == "1"


def _sanitize_ok(label: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a pass/fail summary with counts only — no record bodies / PII."""
    return {
        "check": label,
        "ok": bool(payload.get("ok", True)),
        "count": int(payload.get("count") or payload.get("sample_count") or 0),
    }


@pytest.mark.asyncio
@pytest.mark.skipif(not _enabled(), reason="Set RUN_AE_INTEGRATION=1 for live sandbox tests")
async def test_live_connection() -> None:
    reset_settings_cache()
    settings = Settings()
    assert settings.pardot_business_unit_id
    assert settings.ae_read_only is True, "Sandbox smoke requires AE_READ_ONLY=true"
    runtime = AppRuntime.from_settings(settings)
    try:
        result = await runtime.client.check_connection()
        summary = _sanitize_ok("connection", result)
        assert summary["ok"] is True
    finally:
        await runtime.aclose()


@pytest.mark.asyncio
@pytest.mark.skipif(not _enabled(), reason="Set RUN_AE_INTEGRATION=1 for live sandbox tests")
async def test_sandbox_readonly_smoke() -> None:
    """Opt-in read-only smoke: health, one object each, token refresh.

    Workflow (documented in docs/DEPLOYMENT.md):
      1. salesforce-account-engagement-mcp auth login
      2. RUN_AE_INTEGRATION=1 AE_READ_ONLY=true pytest tests/integration -q
    """
    reset_settings_cache()
    settings = Settings()
    assert settings.pardot_business_unit_id
    assert settings.ae_read_only is True, "Sandbox smoke requires AE_READ_ONLY=true"
    # Refuse production-ish write flags if someone misconfigured the env.
    assert settings.ae_allow_create is False
    assert settings.ae_allow_update is False
    assert settings.ae_allow_delete is False

    runtime = AppRuntime.from_settings(settings)
    summaries: list[dict[str, Any]] = []
    try:
        conn = await runtime.client.check_connection()
        summaries.append(_sanitize_ok("connection", conn))

        for collection in ("prospects", "campaigns", "lists"):
            page = await runtime.client.query(
                collection,
                fields=["id"],
                limit=1,
                auto_paginate=False,
            )
            summaries.append(
                _sanitize_ok(
                    collection,
                    {"ok": True, "count": page.get("count", 0)},
                )
            )

        # Force a refresh round-trip without printing the token value.
        token = await runtime.token_manager.get_access_token(force_refresh=True)
        assert isinstance(token, str) and len(token) > 0
        summaries.append({"check": "token_refresh", "ok": True, "count": 0})

        assert all(item["ok"] for item in summaries)
        # Sanitized summary only — never dump raw Salesforce payloads.
        assert {item["check"] for item in summaries} >= {
            "connection",
            "prospects",
            "campaigns",
            "lists",
            "token_refresh",
        }
    finally:
        await runtime.aclose()
