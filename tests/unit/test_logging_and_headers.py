"""Logging redaction and request header generation."""

from __future__ import annotations

from salesforce_account_engagement_mcp.client.base import build_ae_headers
from salesforce_account_engagement_mcp.logging_config import redact_mapping


def test_redact_mapping() -> None:
    data = redact_mapping({"access_token": "x", "ok": 1, "nested": {"refresh_token": "y"}})
    assert data["access_token"] == "[REDACTED]"
    assert data["nested"]["refresh_token"] == "[REDACTED]"
    assert data["ok"] == 1


def test_headers_include_bu() -> None:
    h = build_ae_headers(
        access_token="t", business_unit_id="0Uv000000000000001", return_api_usage=False
    )
    assert "X-Return-Api-Usage" not in h
    assert h["Pardot-Business-Unit-Id"].startswith("0Uv")
