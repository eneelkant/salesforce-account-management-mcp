"""List and membership models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ListCreateInput(BaseModel):
    name: str = Field(min_length=1)
    title: str | None = None
    description: str | None = None
    isPublic: bool | None = None
    folderId: int | None = None


class ListUpdateInput(BaseModel):
    name: str | None = None
    title: str | None = None
    description: str | None = None
    isPublic: bool | None = None
    folderId: int | None = None


class ListMembershipCreateInput(BaseModel):
    listId: int
    prospectId: int
    optedOut: bool | None = False
