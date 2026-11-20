#!/usr/bin/env python3
"""Sandbox credential preflight — presence only, never prints secret values.

Does NOT contact Salesforce, open OAuth, or run live AE API calls.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EXPECTED_REDIRECT_URI = "http://127.0.0.1:8765/oauth/callback"
EXPECTED_SCOPES = "pardot_api refresh_token"
SANDBOX_LOGIN_URL = "https://test.salesforce.com"
SANDBOX_API_BASE = "https://pi.demo.pardot.com"

# Names only — values are never written to stdout/stderr.
REQUIRED_NONEMPTY = (
    "SF_CLIENT_ID",
    "SF_CLIENT_SECRET",
    "SF_REDIRECT_URI",
    "SF_LOGIN_URL",
    "PARDOT_BUSINESS_UNIT_ID",
    "PARDOT_API_BASE_URL",
)


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(path, override=False)


def _present(name: str) -> bool:
    value = os.environ.get(name)
    return bool(value and str(value).strip())


def run_preflight(*, env_file: Path | None = None) -> dict[str, object]:
    """Return a sanitized pass/fail report (no secret values)."""
    if env_file is not None:
        _load_dotenv(env_file)
    else:
        _load_dotenv(ROOT / ".env")

    missing = [name for name in REQUIRED_NONEMPTY if not _present(name)]
    checks: list[dict[str, object]] = []

    for name in REQUIRED_NONEMPTY:
        checks.append({"check": f"{name}_present", "ok": _present(name)})

    redirect = (os.environ.get("SF_REDIRECT_URI") or "").strip()
    checks.append(
        {
            "check": "SF_REDIRECT_URI_exact",
            "ok": redirect == EXPECTED_REDIRECT_URI,
            "expected": EXPECTED_REDIRECT_URI,
        }
    )

    scopes = " ".join((os.environ.get("SF_OAUTH_SCOPES") or EXPECTED_SCOPES).split())
    checks.append(
        {
            "check": "SF_OAUTH_SCOPES",
            "ok": scopes == EXPECTED_SCOPES,
            "expected": EXPECTED_SCOPES,
        }
    )

    login = (os.environ.get("SF_LOGIN_URL") or "").rstrip("/")
    checks.append(
        {
            "check": "SF_LOGIN_URL_sandbox",
            "ok": login == SANDBOX_LOGIN_URL,
            "expected": SANDBOX_LOGIN_URL,
        }
    )

    api_base = (os.environ.get("PARDOT_API_BASE_URL") or "").rstrip("/")
    checks.append(
        {
            "check": "PARDOT_API_BASE_URL_sandbox",
            "ok": api_base == SANDBOX_API_BASE,
            "expected": SANDBOX_API_BASE,
        }
    )

    # Enforce read-only via Settings so AE_READ_ONLY=true clears write flags.
    from salesforce_account_engagement_mcp.config import Settings, reset_settings_cache

    reset_settings_cache()
    settings = Settings()
    checks.append({"check": "AE_READ_ONLY", "ok": settings.ae_read_only is True})
    checks.append({"check": "AE_ALLOW_CREATE_disabled", "ok": settings.ae_allow_create is False})
    checks.append({"check": "AE_ALLOW_UPDATE_disabled", "ok": settings.ae_allow_update is False})
    checks.append({"check": "AE_ALLOW_DELETE_disabled", "ok": settings.ae_allow_delete is False})

    bu = (os.environ.get("PARDOT_BUSINESS_UNIT_ID") or "").strip()
    checks.append(
        {
            "check": "PARDOT_BUSINESS_UNIT_ID_shape",
            "ok": bool(bu) and bu.startswith("0Uv") and len(bu) == 18,
        }
    )

    ok = not missing and all(bool(item["ok"]) for item in checks)
    return {
        "ok": ok,
        "sandbox_only": True,
        "contacts_salesforce": False,
        "missing_required": missing,
        "checks": checks,
        "next": (
            "Fill missing values in local .env (never commit), then obtain Tanya's "
            "explicit go-ahead before Phase 3 (auth login / live smoke)."
            if not ok
            else "Preflight green. Wait for Tanya's explicit authorization before Phase 3."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sandbox env preflight (presence only; no Salesforce contact)"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional dotenv path (default: ./.env if present)",
    )
    args = parser.parse_args()
    report = run_preflight(env_file=args.env_file)
    # JSON report contains only booleans / var *names* / expected constants.
    import json

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
