"""Shared response envelopes and common field sets."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolMeta(BaseModel):
    data_source: str = "salesforce_account_engagement_api_v5"
    calculated: bool = False
    limitations: list[str] = Field(default_factory=list)


class ToolError(BaseModel):
    error: str
    code: str | int | None = None
    status_code: int | None = None


class PaginatedResult(BaseModel):
    values: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0
    nextPageToken: str | None = None
    nextPageUrl: str | None = None
    truncated: bool = False
    data_source: str = "salesforce_account_engagement_api_v5"


# Default field selections (never include password)
PROSPECT_DEFAULT_FIELDS = (
    "id,email,firstName,lastName,company,jobTitle,score,grade,"
    "campaignId,campaign.id,campaign.name,assignedToId,assignedTo.id,"
    "assignedTo.firstName,assignedTo.lastName,createdAt,updatedAt,"
    "lastActivityAt,optedOut,isDoNotEmail,lifecycleStageId,source"
)

CAMPAIGN_DEFAULT_FIELDS = (
    "id,name,cost,folderId,folder.id,folder.name,parentCampaignId,"
    "salesforceId,isDeleted,createdAt,updatedAt"
)

LIST_DEFAULT_FIELDS = (
    "id,name,description,title,isPublic,isDynamic,folderId,folder.id,"
    "folder.name,createdAt,updatedAt,isDeleted"
)

LIST_MEMBERSHIP_DEFAULT_FIELDS = (
    "id,listId,prospectId,optedOut,createdAt,updatedAt,"
    "list.id,list.name,prospect.id,prospect.email,prospect.firstName,prospect.lastName"
)

VISITOR_DEFAULT_FIELDS = (
    "id,prospectId,hostname,pageViewCount,campaignId,createdAt,updatedAt,isIdentified,doNotSell"
)

VISITOR_ACTIVITY_DEFAULT_FIELDS = (
    "id,prospectId,visitorId,campaignId,type,typeName,details,"
    "createdAt,updatedAt,emailId,listEmailId,formId,landingPageId"
)

CUSTOM_FIELD_DEFAULT_FIELDS = (
    "id,name,fieldId,type,isRequired,isRecordMultipleResponses,"
    "isUseValues,salesforceId,createdAt,updatedAt"
)

FORM_DEFAULT_FIELDS = "id,name,campaignId,campaign.id,campaign.name,createdAt,updatedAt"

LIST_EMAIL_DEFAULT_FIELDS = "id,name,campaignId,subject,createdAt,updatedAt,isDeleted"

TAG_DEFAULT_FIELDS = "id,name,objectCount,createdAt,updatedAt"

LANDING_PAGE_DEFAULT_FIELDS = "id,name,campaignId,campaign.id,campaign.name,createdAt,updatedAt"
