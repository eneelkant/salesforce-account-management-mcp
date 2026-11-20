"""Settings and Business Unit validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from salesforce_account_engagement_mcp.auth.business_unit import (
    BusinessUnitError,
    validate_business_unit_id,
)
from salesforce_account_engagement_mcp.config import Settings, reset_settings_cache


def test_valid_business_unit_id() -> None:
    assert validate_business_unit_id("0Uv000000000000001") == "0Uv000000000000001"


def test_invalid_business_unit_id() -> None:
    with pytest.raises(BusinessUnitError):
        validate_business_unit_id("bad")


def test_read_only_forces_write_flags_off(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("AE_READ_ONLY", "true")
    monkeypatch.setenv("AE_ALLOW_CREATE", "true")
    monkeypatch.setenv("AE_ALLOW_UPDATE", "true")
    monkeypatch.setenv("AE_ALLOW_DELETE", "true")
    monkeypatch.setenv("PARDOT_BUSINESS_UNIT_ID", "0Uv000000000000001")
    s = Settings()
    assert s.ae_read_only is True
    assert s.ae_allow_create is False
    assert s.ae_allow_update is False
    assert s.ae_allow_delete is False


def test_api_version_must_be_five(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("PARDOT_API_VERSION", "4")
    monkeypatch.setenv("PARDOT_BUSINESS_UNIT_ID", "0Uv000000000000001")
    with pytest.raises(ValidationError):
        Settings()


def test_https_required(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("PARDOT_API_BASE_URL", "http://pi.pardot.com")
    monkeypatch.setenv("PARDOT_BUSINESS_UNIT_ID", "0Uv000000000000001")
    with pytest.raises(ValidationError):
        Settings()
