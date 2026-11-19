"""Logging setup with secret redaction."""

from __future__ import annotations

import logging
import re
from typing import Any

_SENSITIVE_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(
        r"(access_token|refresh_token|client_secret|authorization)"
        r"([\"'=\s:]+)([^\s\"'&,}]+)",
        re.IGNORECASE,
    ),
    re.compile(r"(Pardot-Business-Unit-Id:\s*)\S+", re.IGNORECASE),
]


class RedactingFilter(logging.Filter):
    """Strip tokens and secrets from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_redact(str(a)) for a in record.args)
        return True


def _redact(text: str) -> str:
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.groups >= 3:
            text = pattern.sub(r"\1\2[REDACTED]", text)
        elif pattern.groups == 1:
            text = pattern.sub(r"\1[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with redaction."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with sensitive keys redacted."""
    sensitive = {
        "access_token",
        "refresh_token",
        "client_secret",
        "authorization",
        "password",
        "token",
    }
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in sensitive:
            out[key] = "[REDACTED]"
        elif isinstance(value, dict):
            out[key] = redact_mapping(value)
        else:
            out[key] = value
    return out
