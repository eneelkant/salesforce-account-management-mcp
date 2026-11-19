"""Visitor activity models."""

from __future__ import annotations

from pydantic import BaseModel


class VisitorActivityFilters(BaseModel):
    prospectId: int | None = None
    visitorId: int | None = None
    type: int | None = None
    createdAtAfter: str | None = None
    createdAtBefore: str | None = None
    id: int | None = None
