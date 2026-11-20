"""Shared application runtime wired into MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .auth.token_manager import TokenManager
from .client.account_engagement import AccountEngagementClient
from .client.errors import AccountEngagementAPIError
from .config import Settings, get_settings
from .security.audit import AuditLogger
from .security.confirmation import require_confirmation
from .security.permissions import Operation, PermissionDenied, PermissionGate
from .security.redaction import redact_response


@dataclass
class AppRuntime:
    settings: Settings
    token_manager: TokenManager
    client: AccountEngagementClient
    permissions: PermissionGate
    audit: AuditLogger

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> AppRuntime:
        settings = settings or get_settings()
        token_manager = TokenManager(settings)
        client = AccountEngagementClient(settings, token_manager, http_client=http_client)
        return cls(
            settings=settings,
            token_manager=token_manager,
            client=client,
            permissions=PermissionGate(settings),
            audit=AuditLogger(settings.ae_audit_log_path or None),
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    def guard_read(self) -> None:
        self.permissions.assert_allowed(Operation.READ)

    def guard_create(self, *, confirm: bool, target: str) -> None:
        self.permissions.assert_allowed(Operation.CREATE)
        require_confirmation(
            operation=Operation.CREATE,
            confirm=confirm,
            required=self.settings.ae_require_write_confirmation,
            target_description=target,
        )

    def guard_update(self, *, confirm: bool, target: str) -> None:
        self.permissions.assert_allowed(Operation.UPDATE)
        require_confirmation(
            operation=Operation.UPDATE,
            confirm=confirm,
            required=self.settings.ae_require_write_confirmation,
            target_description=target,
        )

    def guard_delete(
        self,
        *,
        confirm: bool,
        target: str,
        record_id: int | str,
        confirm_id: int | str | None,
    ) -> None:
        self.permissions.assert_allowed(Operation.DELETE)
        require_confirmation(
            operation=Operation.DELETE,
            confirm=confirm,
            required=self.settings.ae_require_delete_confirmation,
            target_description=target,
            expected_id=record_id,
            confirm_id=confirm_id,
        )

    def ok(self, payload: Any, *, tool_name: str, operation: str, **audit: Any) -> dict[str, Any]:
        cleaned = redact_response(payload)
        self.audit.log(
            tool_name=tool_name,
            operation=operation,
            success=True,
            record_type=audit.get("record_type"),
            record_id=audit.get("record_id"),
            context=audit.get("context"),
        )
        if isinstance(cleaned, dict):
            return cleaned
        return {"result": cleaned}

    def fail(
        self,
        exc: Exception,
        *,
        tool_name: str,
        operation: str,
        **audit: Any,
    ) -> dict[str, Any]:
        self.audit.log(
            tool_name=tool_name,
            operation=operation,
            success=False,
            record_type=audit.get("record_type"),
            record_id=audit.get("record_id"),
            context={"error_type": type(exc).__name__, **(audit.get("context") or {})},
        )
        if isinstance(exc, PermissionDenied):
            return exc.to_dict()
        if isinstance(exc, AccountEngagementAPIError):
            return exc.to_dict()
        return {"error": str(exc), "error_type": type(exc).__name__}


def drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}
