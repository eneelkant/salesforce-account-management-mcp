"""Campaign-related models."""

from __future__ import annotations

from pydantic import BaseModel


class CampaignFilters(BaseModel):
    id: int | None = None
    idList: str | None = None
    name: str | None = None
    updatedAtAfter: str | None = None
    updatedAtBefore: str | None = None
    createdAtAfter: str | None = None
    createdAtBefore: str | None = None
    deleted: str | None = None
