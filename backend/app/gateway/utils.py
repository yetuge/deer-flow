"""Shared utility helpers for the Gateway layer."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from fastapi import HTTPException

from deerflow.utils.file_io import await_drained


def sanitize_log_param(value: str) -> str:
    """Strip control characters to prevent log injection."""
    return value.replace("\n", "").replace("\r", "").replace("\x00", "")


async def run_drained_write[**P, T](
    logger: logging.Logger,
    label: str,
    func: Callable[P, T],
    /,
    *args: P.args,
    expected_errors: tuple[type[Exception], ...] = (),
    **kwargs: P.kwargs,
) -> T:
    """Finish an offloaded write before propagating caller cancellation.

    Log failures inside the worker so cancellation cannot hide them. Error
    details may contain secrets: log only exception types or HTTP 5xx status.
    Expected domain errors and HTTP 4xx responses remain unlogged.
    """

    def _logged() -> T:
        try:
            return func(*args, **kwargs)
        except HTTPException as exc:
            if exc.status_code >= 500:
                logger.error("%s failed (HTTP %d)", label, exc.status_code)
            raise
        except expected_errors:
            raise
        except Exception as exc:
            logger.error("%s failed (%s)", label, type(exc).__name__)
            raise

    return await await_drained(asyncio.to_thread(_logged))
