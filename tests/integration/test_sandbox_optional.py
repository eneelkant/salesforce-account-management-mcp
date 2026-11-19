"""Optional live sandbox tests — skipped unless RUN_AE_INTEGRATION=1."""

from __future__ import annotations

import os

import pytest

from salesforce_account_engagement_mcp.config import Settings, reset_settings_cache
from salesforce_account_engagement_mcp.runtime import AppRuntime

pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return os.getenv("RUN_AE_INTEGRATION") == "1"


@pytest.mark.asyncio
@pytest.mark.skipif(not _enabled(), reason="Set RUN_AE_INTEGRATION=1 for live sandbox tests")
async def test_live_connection() -> None:
    reset_settings_cache()
    settings = Settings()
    assert settings.pardot_business_unit_id
    runtime = AppRuntime.from_settings(settings)
    try:
        result = await runtime.client.check_connection()
        assert result["ok"] is True
    finally:
        await runtime.aclose()
