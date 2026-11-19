"""Official Account Engagement API v5 async client."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from ..auth.business_unit import validate_business_unit_id
from ..auth.token_manager import TokenManager
from ..config import Settings
from ..logging_config import get_logger
from .base import build_ae_headers, extract_api_usage, raise_for_ae_response
from .errors import AuthenticationRequiredError
from .pagination import MAX_PAGINATION_RECORDS, merge_pages, validate_next_page_url
from .retry import with_retries

logger = get_logger(__name__)


class AccountEngagementClient:
    """Async client for https://pi.pardot.com/api/v5/objects/."""

    def __init__(
        self,
        settings: Settings,
        token_manager: TokenManager,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.token_manager = token_manager
        self._client = http_client
        self._owns_client = http_client is None
        self._semaphore = __import__("asyncio").Semaphore(settings.ae_max_concurrent_requests)
        self._last_api_usage: str | None = None

    @property
    def last_api_usage(self) -> str | None:
        return self._last_api_usage

    async def __aenter__(self) -> AccountEngagementClient:
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.settings.ae_http_timeout_seconds,
                follow_redirects=False,
            )
        return self._client

    def _require_bu(self) -> str:
        try:
            return validate_business_unit_id(self.settings.pardot_business_unit_id)
        except ValueError as exc:
            raise AuthenticationRequiredError(str(exc), status_code=401) from exc

    def object_url(self, collection: str, object_id: int | str | None = None) -> str:
        base = f"{self.settings.api_objects_base}/{collection.strip('/')}"
        if object_id is None:
            return base
        return f"{base}/{object_id}"

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        retry_non_idempotent: bool = False,
    ) -> dict[str, Any] | list[Any] | None:
        bu = self._require_bu()

        async def _do() -> dict[str, Any] | list[Any] | None:
            token = await self.token_manager.get_access_token()
            client = await self._ensure_client()
            headers = build_ae_headers(
                access_token=token,
                business_unit_id=bu,
            )
            async with self._semaphore:
                logger.debug("AE API %s %s", method.upper(), url)
                response = await client.request(
                    method.upper(),
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
            self._last_api_usage = extract_api_usage(response)
            if response.status_code in {401, 403}:
                # One forced refresh then retry once at this layer via exception path.
                await self.token_manager.get_access_token(force_refresh=True)
                token = await self.token_manager.get_access_token()
                headers = build_ae_headers(access_token=token, business_unit_id=bu)
                async with self._semaphore:
                    response = await client.request(
                        method.upper(),
                        url,
                        params=params,
                        json=json_body,
                        headers=headers,
                    )
                self._last_api_usage = extract_api_usage(response)

            raise_for_ae_response(response)
            warning = response.headers.get("Pardot-Warning")
            if response.status_code == 204 or not response.content:
                result: dict[str, Any] = {"ok": True, "status_code": 204}
                if warning:
                    result["_pardot_warning"] = warning
                if self._last_api_usage:
                    result["api_usage"] = self._last_api_usage
                return result
            try:
                payload: dict[str, Any] | list[Any] | None = response.json()
            except Exception:
                return {
                    "ok": True,
                    "status_code": response.status_code,
                    "raw": response.text[:1000],
                }
            if isinstance(payload, dict):
                if warning:
                    payload = {**payload, "_pardot_warning": warning}
                if self._last_api_usage:
                    payload = {**payload, "api_usage": self._last_api_usage}
                return payload
            if isinstance(payload, list):
                return payload
            return None

        return await with_retries(
            _do,
            max_retries=self.settings.ae_http_max_retries,
            method=method,
            retry_non_idempotent=retry_non_idempotent,
        )

    async def query(
        self,
        collection: str,
        *,
        fields: str | list[str],
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        next_page_token: str | None = None,
        max_records: int | None = None,
        auto_paginate: bool = False,
    ) -> dict[str, Any]:
        field_str = fields if isinstance(fields, str) else ",".join(fields)
        limit = min(limit or self.settings.ae_max_records, self.settings.ae_max_records)
        max_records = min(
            max_records or limit,
            self.settings.ae_max_records,
            MAX_PAGINATION_RECORDS,
        )

        pages: list[dict[str, Any]] = []
        token = next_page_token
        fetched = 0

        while True:
            params: dict[str, Any] = {"fields": field_str}
            if token:
                # With page tokens only `fields` (+ token) are valid.
                params["nextPageToken"] = token
            else:
                params["limit"] = min(limit, max_records - fetched or limit)
                if order_by:
                    params["orderBy"] = order_by
                if filters:
                    for key, value in filters.items():
                        if value is not None:
                            params[key] = value

            url = self.object_url(collection)
            raw = await self.request("GET", url, params=params)
            page = raw if isinstance(raw, dict) else {"values": raw or []}
            pages.append(page)
            values = page.get("values") or []
            fetched += len(values) if isinstance(values, list) else 0

            if not auto_paginate:
                break
            if fetched >= max_records:
                break
            next_token = page.get("nextPageToken")
            next_url = page.get("nextPageUrl")
            if not next_token and not next_url:
                break
            if next_url:
                validate_next_page_url(str(next_url), self.settings.allowed_api_hosts)
            token = str(next_token) if next_token else None
            if not token:
                break

        if auto_paginate and len(pages) > 1:
            return merge_pages(pages, max_records=max_records)
        if len(pages) == 1:
            page = pages[0]
            values = page.get("values") or []
            return {
                **page,
                "count": len(values) if isinstance(values, list) else 0,
                "data_source": "salesforce_account_engagement_api_v5",
            }
        return merge_pages(pages, max_records=max_records)

    async def read(
        self,
        collection: str,
        object_id: int | str,
        *,
        fields: str | list[str],
    ) -> dict[str, Any]:
        field_str = fields if isinstance(fields, str) else ",".join(fields)
        raw = await self.request(
            "GET",
            self.object_url(collection, object_id),
            params={"fields": field_str},
        )
        return raw if isinstance(raw, dict) else {"value": raw}

    async def create(
        self,
        collection: str,
        body: dict[str, Any],
        *,
        fields: str | list[str] | None = None,
    ) -> dict[str, Any]:
        params = None
        if fields:
            params = {"fields": fields if isinstance(fields, str) else ",".join(fields)}
        raw = await self.request(
            "POST",
            self.object_url(collection),
            params=params,
            json_body=body,
        )
        return raw if isinstance(raw, dict) else {"value": raw}

    async def update(
        self,
        collection: str,
        object_id: int | str,
        body: dict[str, Any],
        *,
        fields: str | list[str] | None = None,
    ) -> dict[str, Any]:
        params = None
        if fields:
            params = {"fields": fields if isinstance(fields, str) else ",".join(fields)}
        raw = await self.request(
            "PATCH",
            self.object_url(collection, object_id),
            params=params,
            json_body=body,
        )
        return raw if isinstance(raw, dict) else {"value": raw}

    async def delete(self, collection: str, object_id: int | str) -> dict[str, Any]:
        raw = await self.request("DELETE", self.object_url(collection, object_id))
        return raw if isinstance(raw, dict) else {"ok": True}

    async def action(
        self,
        collection: str,
        action_name: str,
        *,
        object_id: int | str | None = None,
        body: dict[str, Any] | None = None,
        fields: str | list[str] | None = None,
    ) -> dict[str, Any]:
        """Call a documented `/do/<action>` endpoint."""
        if object_id is None:
            url = f"{self.object_url(collection)}/do/{action_name}"
        else:
            url = f"{self.object_url(collection, object_id)}/do/{action_name}"
        params = None
        if fields:
            params = {"fields": fields if isinstance(fields, str) else ",".join(fields)}
        raw = await self.request("POST", url, params=params, json_body=body or {})
        return raw if isinstance(raw, dict) else {"value": raw}

    async def get_stats(self, collection: str, object_id: int | str) -> dict[str, Any]:
        url = f"{self.object_url(collection, object_id)}/stats"
        raw = await self.request("GET", url)
        return raw if isinstance(raw, dict) else {"value": raw}

    async def check_connection(self) -> dict[str, Any]:
        """Lightweight connectivity check via prospects query limit=1."""
        result = await self.query(
            "prospects",
            fields=["id"],
            limit=1,
            auto_paginate=False,
        )
        return {
            "ok": True,
            "business_unit_id": self.settings.pardot_business_unit_id,
            "api_base_url": self.settings.pardot_api_base_url,
            "api_usage": self._last_api_usage,
            "sample_count": result.get("count", 0),
            "data_source": "salesforce_account_engagement_api_v5",
        }

    def absolute_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("https://"):
            return path_or_url
        return urljoin(self.settings.pardot_api_base_url + "/", path_or_url.lstrip("/"))
