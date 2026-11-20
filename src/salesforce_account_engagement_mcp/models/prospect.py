"""Prospect input models."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ProspectCreateInput(BaseModel):
    email: str
    firstName: str | None = None
    lastName: str | None = None
    company: str | None = None
    jobTitle: str | None = None
    phone: str | None = None
    website: str | None = None
    campaignId: int | None = None
    score: int | None = None
    source: str | None = None
    userId: int | None = None
    notes: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email address")
        return value


class ProspectUpdateInput(BaseModel):
    firstName: str | None = None
    lastName: str | None = None
    company: str | None = None
    jobTitle: str | None = None
    phone: str | None = None
    website: str | None = None
    campaignId: int | None = None
    score: int | None = None
    source: str | None = None
    userId: int | None = None
    notes: str | None = None
    email: str | None = None
    optedOut: bool | None = None
    isDoNotEmail: bool | None = None


class ProspectFilters(BaseModel):
    email: str | None = None
    id: int | None = None
    firstName: str | None = None
    lastName: str | None = None
    company: str | None = None
    campaignId: int | None = None
    assignedToId: int | None = None
    scoreGreaterThan: int | None = None
    scoreLessThan: int | None = None
    grade: str | None = None
    createdAtAfter: str | None = None
    createdAtBefore: str | None = None
    updatedAtAfter: str | None = None
    updatedAtBefore: str | None = None
    lastActivityAtBefore: str | None = None
    lastActivityAtAfter: str | None = None
    deleted: str | None = Field(default=None, description="false|true|all")
