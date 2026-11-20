"""Test helpers."""

from __future__ import annotations

from typing import Any


async def call_tool(server: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await server.call_tool(name, arguments)
    if getattr(result, "structured_content", None) is not None:
        content = result.structured_content
        if isinstance(content, dict):
            return content
    # Fallback parse text content
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            import json

            return json.loads(text)
    return {"raw": str(result), "is_error": getattr(result, "is_error", None)}
