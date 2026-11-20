"""Environment-controlled read/write/delete permission gate."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Settings


class Operation(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class PermissionDenied(PermissionError):
    """Raised when a tool operation is blocked by security policy."""

    def __init__(self, message: str, *, operation: Operation) -> None:
        super().__init__(message)
        self.operation = operation

    def to_dict(self) -> dict[str, str]:
        return {
            "error": str(self),
            "operation": self.operation.value,
            "hint": (
                "Default mode is read-only. Set AE_READ_ONLY=false and enable "
                "AE_ALLOW_CREATE / AE_ALLOW_UPDATE / AE_ALLOW_DELETE as needed."
            ),
        }


class PermissionGate:
    """Enforce AE_READ_ONLY and granular write/delete flags."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def assert_allowed(self, operation: Operation) -> None:
        if operation == Operation.READ:
            return
        if self.settings.ae_read_only:
            raise PermissionDenied(
                f"Operation '{operation}' blocked: AE_READ_ONLY=true.",
                operation=operation,
            )
        if operation == Operation.CREATE and not self.settings.ae_allow_create:
            raise PermissionDenied(
                "Create blocked: set AE_ALLOW_CREATE=true.",
                operation=operation,
            )
        if operation == Operation.UPDATE and not self.settings.ae_allow_update:
            raise PermissionDenied(
                "Update blocked: set AE_ALLOW_UPDATE=true.",
                operation=operation,
            )
        if operation == Operation.DELETE and not self.settings.ae_allow_delete:
            raise PermissionDenied(
                "Delete blocked: set AE_ALLOW_DELETE=true (separate opt-in from create/update).",
                operation=operation,
            )

    def status(self) -> dict[str, bool | str]:
        return {
            "read_only": self.settings.ae_read_only,
            "allow_create": self.settings.ae_allow_create and not self.settings.ae_read_only,
            "allow_update": self.settings.ae_allow_update and not self.settings.ae_read_only,
            "allow_delete": self.settings.ae_allow_delete and not self.settings.ae_read_only,
            "require_write_confirmation": self.settings.ae_require_write_confirmation,
            "require_delete_confirmation": self.settings.ae_require_delete_confirmation,
            "mode": "read_only" if self.settings.ae_read_only else "read_write",
        }
