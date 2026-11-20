"""Sandbox preflight — presence checks without contacting Salesforce."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_preflight() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "sandbox_preflight.py"
    spec = importlib.util.spec_from_file_location("sandbox_preflight", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def preflight() -> ModuleType:
    return _load_preflight()


def test_preflight_fails_closed_when_credentials_missing(
    preflight: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in (
        "SF_CLIENT_ID",
        "SF_CLIENT_SECRET",
        "SF_REDIRECT_URI",
        "SF_LOGIN_URL",
        "PARDOT_BUSINESS_UNIT_ID",
        "PARDOT_API_BASE_URL",
        "SF_OAUTH_SCOPES",
        "AE_READ_ONLY",
        "AE_ALLOW_CREATE",
        "AE_ALLOW_UPDATE",
        "AE_ALLOW_DELETE",
    ):
        monkeypatch.delenv(name, raising=False)

    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    report = preflight.run_preflight(env_file=empty)
    assert report["ok"] is False
    assert report["contacts_salesforce"] is False
    assert "SF_CLIENT_ID" in report["missing_required"]
    blob = str(report)
    assert preflight.EXPECTED_REDIRECT_URI in blob


def test_preflight_passes_with_sandbox_shape(
    preflight: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SF_CLIENT_ID", "sandbox-client-id")
    monkeypatch.setenv("SF_CLIENT_SECRET", "sandbox-client-secret")
    monkeypatch.setenv("SF_REDIRECT_URI", preflight.EXPECTED_REDIRECT_URI)
    monkeypatch.setenv("SF_LOGIN_URL", "https://test.salesforce.com")
    monkeypatch.setenv("SF_OAUTH_SCOPES", "pardot_api refresh_token")
    monkeypatch.setenv("PARDOT_BUSINESS_UNIT_ID", "0Uv000000000000001")
    monkeypatch.setenv("PARDOT_API_BASE_URL", "https://pi.demo.pardot.com")
    monkeypatch.setenv("AE_READ_ONLY", "true")
    monkeypatch.setenv("AE_ALLOW_CREATE", "true")  # forced off when read-only
    monkeypatch.setenv("AE_ALLOW_UPDATE", "true")
    monkeypatch.setenv("AE_ALLOW_DELETE", "true")

    env_file = tmp_path / "noop.env"
    env_file.write_text("# unused; env already set\n", encoding="utf-8")
    report = preflight.run_preflight(env_file=env_file)
    assert report["ok"] is True
    assert report["missing_required"] == []
    by_name = {c["check"]: c["ok"] for c in report["checks"]}
    assert by_name["AE_READ_ONLY"] is True
    assert by_name["AE_ALLOW_CREATE_disabled"] is True
    assert by_name["AE_ALLOW_UPDATE_disabled"] is True
    assert by_name["AE_ALLOW_DELETE_disabled"] is True
    assert "sandbox-client-secret" not in str(report)
    assert "sandbox-client-id" not in str(report)
