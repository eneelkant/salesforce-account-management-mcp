"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest

from salesforce_account_engagement_mcp.client.account_engagement import AccountEngagementClient
from salesforce_account_engagement_mcp.config import Settings, reset_settings_cache
from salesforce_account_engagement_mcp.runtime import AppRuntime
from salesforce_account_engagement_mcp.server import create_server


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[None]:
    reset_settings_cache()
    monkeypatch.setenv("PARDOT_BUSINESS_UNIT_ID", "0Uv000000000000001")
    monkeypatch.setenv("SF_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setenv("SF_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SF_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("SF_REFRESH_TOKEN", "test-refresh-token")
    monkeypatch.setenv("PARDOT_API_BASE_URL", "https://pi.pardot.com")
    monkeypatch.setenv("SF_LOGIN_URL", "https://login.salesforce.com")
    monkeypatch.setenv("AE_READ_ONLY", "true")
    monkeypatch.setenv("AE_ALLOW_CREATE", "false")
    monkeypatch.setenv("AE_ALLOW_UPDATE", "false")
    monkeypatch.setenv("AE_ALLOW_DELETE", "false")
    monkeypatch.setenv("SF_TOKEN_STORE_PATH", str(tmp_path / "tokens.json"))
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    # Ensure no leaked integration flag
    monkeypatch.delenv("RUN_AE_INTEGRATION", raising=False)
    yield
    reset_settings_cache()


@pytest.fixture
def settings() -> Settings:
    reset_settings_cache()
    return Settings()


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def runtime(settings: Settings, http_client: httpx.AsyncClient) -> AppRuntime:
    return AppRuntime.from_settings(settings, http_client=http_client)


@pytest.fixture
def client(runtime: AppRuntime) -> AccountEngagementClient:
    return runtime.client


@pytest.fixture
def mcp_server(runtime: AppRuntime) -> Any:
    server, _ = create_server(runtime.settings, runtime=runtime)
    return server


@pytest.fixture
def write_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Settings:
    reset_settings_cache()
    monkeypatch.setenv("AE_READ_ONLY", "false")
    monkeypatch.setenv("AE_ALLOW_CREATE", "true")
    monkeypatch.setenv("AE_ALLOW_UPDATE", "true")
    monkeypatch.setenv("AE_ALLOW_DELETE", "true")
    monkeypatch.setenv("AE_REQUIRE_WRITE_CONFIRMATION", "true")
    monkeypatch.setenv("AE_REQUIRE_DELETE_CONFIRMATION", "true")
    monkeypatch.setenv("SF_TOKEN_STORE_PATH", str(tmp_path / "tokens-write.json"))
    return Settings()
