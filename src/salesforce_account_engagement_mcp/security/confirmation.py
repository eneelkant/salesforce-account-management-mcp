"""Explicit confirmation checks for write/delete tools."""

from __future__ import annotations

from .permissions import Operation, PermissionDenied


def require_confirmation(
    *,
    operation: Operation,
    confirm: bool,
    required: bool,
    target_description: str,
    expected_id: int | str | None = None,
    confirm_id: int | str | None = None,
) -> None:
    """Require confirm=True (and matching ID for deletes) when policy demands it."""
    if not required:
        return
    if not confirm:
        raise PermissionDenied(
            f"{operation.value.capitalize()} of {target_description} requires "
            f"confirm=true. Re-invoke with confirm=true after verifying the target.",
            operation=operation,
        )
    if operation == Operation.DELETE and expected_id is not None:
        if confirm_id is None or str(confirm_id) != str(expected_id):
            raise PermissionDenied(
                f"Delete confirmation failed for {target_description}. "
                f"Pass confirm_id matching the target id ({expected_id}).",
                operation=operation,
            )
