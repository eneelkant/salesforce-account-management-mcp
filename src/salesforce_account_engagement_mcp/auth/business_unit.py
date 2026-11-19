"""Account Engagement Business Unit ID validation."""

from __future__ import annotations

import re

_BU_ID_RE = re.compile(r"^0Uv[A-Za-z0-9]{15}$")


class BusinessUnitError(ValueError):
    """Raised when a Business Unit ID is invalid."""


def validate_business_unit_id(business_unit_id: str) -> str:
    """Validate Salesforce Account Engagement Business Unit ID format.

    IDs begin with ``0Uv`` and are 18 characters long.
    """
    value = (business_unit_id or "").strip()
    if not value:
        raise BusinessUnitError(
            "PARDOT_BUSINESS_UNIT_ID is required. Find it in Salesforce Setup → "
            "Business Unit Setup (starts with 0Uv)."
        )
    if not _BU_ID_RE.match(value):
        raise BusinessUnitError(
            f"Invalid Business Unit ID '{value}'. Expected 18 characters starting with 0Uv."
        )
    return value


def business_unit_info(
    business_unit_id: str,
    *,
    api_base_url: str,
    login_url: str,
) -> dict[str, object]:
    """Return non-secret Business Unit / environment metadata."""
    validated = validate_business_unit_id(business_unit_id)
    is_sandbox = "demo.pardot" in api_base_url or "test.salesforce" in login_url
    return {
        "business_unit_id": validated,
        "api_base_url": api_base_url,
        "login_url": login_url,
        "environment": "sandbox_or_demo" if is_sandbox else "production",
        "api_version": "5",
        "header_name": "Pardot-Business-Unit-Id",
    }
