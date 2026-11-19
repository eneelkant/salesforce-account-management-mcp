"""Secure file-backed token storage with atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class StoredTokens:
    """Persisted Salesforce OAuth tokens."""

    access_token: str = ""
    refresh_token: str = ""
    instance_url: str = ""
    issued_at: float | None = None
    expires_in: int | None = None
    token_type: str = "Bearer"
    scope: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredTokens:
        return cls(
            access_token=str(data.get("access_token") or ""),
            refresh_token=str(data.get("refresh_token") or ""),
            instance_url=str(data.get("instance_url") or ""),
            issued_at=_as_float(data.get("issued_at")),
            expires_in=_as_int(data.get("expires_in")),
            token_type=str(data.get("token_type") or "Bearer"),
            scope=str(data.get("scope") or ""),
        )


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


class TokenStore:
    """Atomic JSON token store. Never logs token values."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> StoredTokens | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return StoredTokens.from_dict(data)

    def save(self, tokens: StoredTokens) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(tokens.to_dict(), indent=2, sort_keys=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent),
            prefix=".tokens.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
