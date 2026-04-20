"""Exponential-backoff retry for transient API errors."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

from gigiac_bot.utils.logger import logger

T = TypeVar("T")


class ApiError(Exception):
    """Raised when the Gigiac API returns an error response."""

    def __init__(self, status_code: int, message: str, body: object = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    @property
    def is_transient(self) -> bool:
        return self.status_code in (429, 503)


def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
) -> T:
    """Call *fn* with exponential backoff on transient ApiError."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except ApiError as exc:
            is_last = attempt == max_retries
            if is_last or not exc.is_transient:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "Retryable error (attempt %d/%d), retrying in %.1fs [%d]",
                attempt + 1,
                max_retries,
                delay,
                exc.status_code,
            )
            time.sleep(delay)

    raise RuntimeError("Retry loop exited unexpectedly")
