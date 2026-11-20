"""List email / form / tag model stubs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TagCreateInput(BaseModel):
    name: str = Field(min_length=1)
