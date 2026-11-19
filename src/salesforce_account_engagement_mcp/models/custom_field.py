"""Custom field models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CustomFieldCreateInput(BaseModel):
    name: str = Field(min_length=1)
    fieldId: str = Field(min_length=1)
    type: str = Field(
        description=(
            "Text | Radio Button | Checkbox | Dropdown | Textarea | "
            "Multi-Select | Hidden | Number | Date | CRM User"
        )
    )
    isRequired: bool | None = None
    isRecordMultipleResponses: bool | None = None
    isUseValues: bool | None = None
    salesforceId: str | None = None


class CustomFieldUpdateInput(BaseModel):
    name: str | None = None
    isRequired: bool | None = None
    isRecordMultipleResponses: bool | None = None
    isUseValues: bool | None = None
    salesforceId: str | None = None
