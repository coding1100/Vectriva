"""Retry logic and error handling utilities."""

import asyncio
from typing import Any, Callable, TypeVar

import structlog

from .errors import RETRYABLE_ERRORS, CalendarAPIError, EmbeddingServiceError, VectrivaError

logger = structlog.get_logger()

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int,
        backoff_strategy: Literal["exponential", "linear"],
        base_delay_seconds: float = 1.0,
    ):
        self.max_retries = max_retries
        self.backoff_strategy = backoff_strategy
        self.base_delay_seconds = base_delay_seconds

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        if self.backoff_strategy == "exponential":
            return self.base_delay_seconds * (2**attempt)
        return self.base_delay_seconds * (attempt + 1)


RETRY_POLICIES: dict[type[VectrivaError], RetryConfig] = {
    CalendarAPIError: RetryConfig(max_retries=3, backoff_strategy="exponential"),
    EmbeddingServiceError: RetryConfig(max_retries=2, backoff_strategy="linear"),
}


async def retry_with_backoff(
    func: Callable[..., T],
    *args: Any,
    error_types: tuple[type[Exception], ...] = tuple(RETRYABLE_ERRORS),
    **kwargs: Any,
) -> T:
    """
    Execute function with retry logic.

    Raises:
        The original exception if max retries exceeded or error is non-retryable.
    """
    last_exception: Exception | None = None

    for error_type in error_types:
        if error_type in RETRY_POLICIES:
            retry_config = RETRY_POLICIES[error_type]
            for attempt in range(retry_config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except error_type as e:
                    last_exception = e
                    if attempt < retry_config.max_retries:
                        delay = retry_config.get_delay(attempt)
                        logger.warning(
                            "retrying_after_error",
                            error_type=error_type.__name__,
                            attempt=attempt + 1,
                            max_retries=retry_config.max_retries,
                            delay_seconds=delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "max_retries_exceeded",
                            error_type=error_type.__name__,
                            max_retries=retry_config.max_retries,
                        )
                        raise

    # If no retry policy or different error
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error("non_retryable_error", error=str(e), error_type=type(e).__name__)
        raise


def should_escalate(context: Any, error: Exception | None = None) -> bool:
    """
    Determine if conversation should be escalated.

    Auto-escalate when:
    - consecutive_errors >= 3
    - Tool call fails after max retries
    - Confidence score < 0.4 (handled in intent classification)
    """
    if hasattr(context, "consecutive_errors") and context.consecutive_errors >= 3:
        return True

    if error and isinstance(error, VectrivaError):
        if context.consecutive_errors >= 2:
            return True

    return False
