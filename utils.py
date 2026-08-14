from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry_async(
    func: Callable[[], Awaitable[T]],
    attempts: int,
    logger: logging.Logger,
    *,
    delay_seconds: float = 2.0,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("Attempt %s/%s failed: %s", attempt, attempts, exc)
            if attempt < attempts:
                await asyncio.sleep(delay_seconds * attempt)
    assert last_error is not None
    raise last_error
