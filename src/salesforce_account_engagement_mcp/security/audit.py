"""Audit logging for MCP tool operations (no secrets / full PII dumps)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """Append structured audit events to logger and optional file."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        tool_name: str,
        operation: str,
        record_type: str | None = None,
        record_id: int | str | None = None,
        success: bool,
        context: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "tool_name": tool_name,
            "operation": operation,
            "record_type": record_type,
            "record_id": record_id,
            "success": success,
            "context": _safe_context(context or {}),
        }
        line = json.dumps(event, default=str)
        level = logging.INFO if success else logging.WARNING
        logger.log(level, "AUDIT %s", line)
        if self.path:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def _safe_context(context: dict[str, Any]) -> dict[str, Any]:
    blocked = {
        "access_token",
        "refresh_token",
        "client_secret",
        "authorization",
        "password",
        "email",
        "ipAddress",
    }
    out: dict[str, Any] = {}
    for key, value in context.items():
        if key in blocked:
            out[key] = "[REDACTED]"
        else:
            out[key] = value
    return out
