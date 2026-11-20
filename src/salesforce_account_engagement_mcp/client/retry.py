"""Retry helpers with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from .errors import AccountEngagementAPIError, RateLimitError

# Idempotent methods safe to retry automatically.
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def with_retries[T](
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    method: str = "GET",
    retry_non_idempotent: bool = False,
) -> T:
    """Retry transient failures with exponential backoff + jitter."""
    attempt = 0
    while True:
        try:
            return await operation()
        except RateLimitError:
            raise
        except AccountEngagementAPIError as exc:
            status = exc.status_code or 0
            retryable = status in {408, 425, 429, 500, 502, 503, 504}
            if not retryable:
                raise
            if method.upper() not in IDEMPOTENT_METHODS and not retry_non_idempotent:
                raise
            if attempt >= max_retries:
                raise
            delay = min(max_delay, base_delay * (2**attempt))
            delay = delay * (0.5 + random.random())  # noqa: S311 — jitter only
            await asyncio.sleep(delay)
            attempt += 1
