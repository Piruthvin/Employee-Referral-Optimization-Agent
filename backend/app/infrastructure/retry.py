"""
Retry utilities with exponential backoff for external API calls (Zoho, Graph, iGentic).
"""

import asyncio
import logging
from typing import Callable, Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    func: Callable[..., Any],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Executes an async callable with exponential backoff on transient errors or HTTP status codes.
    """
    delay = initial_delay
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exception = exc
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            is_retryable = False

            if status_code and status_code in retryable_status_codes:
                is_retryable = True
            elif isinstance(exc, (ConnectionError, TimeoutError, OSError)):
                is_retryable = True

            if is_retryable and attempt < max_retries:
                logger.warning(
                    "Retryable error on attempt %d/%d: %s. Retrying in %.2fs...",
                    attempt,
                    max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                raise last_exception

    if last_exception:
        raise last_exception
