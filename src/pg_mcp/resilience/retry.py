"""Retry and backoff utilities for PostgreSQL MCP Server.

This module provides retry decorators and utilities with configurable
delay and exponential backoff for transient failures.
"""

import asyncio
import functools
import logging
from typing import Callable, TypeVar

from pg_mcp.config.settings import ResilienceConfig
from pg_mcp.models.errors import LLMError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryWithBackoff:
    """Retry handler with exponential backoff.

    Implements retry logic with configurable initial delay and backoff factor.
    Used for transient failures in LLM and database operations.

    Example:
        >>> config = ResilienceConfig(max_retries=3, retry_delay=1.0, backoff_factor=2.0)
        >>> retry = RetryWithBackoff(config)
        >>> result = await retry.execute(some_async_function, arg1, arg2)
    """

    def __init__(self, config: ResilienceConfig) -> None:
        """Initialize retry handler.

        Args:
            config: Resilience configuration containing retry settings.
        """
        self.max_retries = config.max_retries
        self.retry_delay = config.retry_delay
        self.backoff_factor = config.backoff_factor

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
        context: dict | None = None,
        **kwargs,
    ) -> T:
        """Execute function with retry and exponential backoff.

        Args:
            func: Async function to execute.
            *args: Positional arguments for the function.
            retryable_exceptions: Tuple of exception types that should trigger retry.
            context: Optional context dict for logging (e.g., request_id).
            **kwargs: Keyword arguments for the function.

        Returns:
            The result of the function execution.

        Raises:
            The last exception if all retries are exhausted.
        """
        context = context or {}
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except retryable_exceptions as e:
                last_exception = e

                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    delay = self.retry_delay * (self.backoff_factor ** attempt)

                    logger.warning(
                        f"Function failed, retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries + 1})",
                        extra={
                            **context,
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries + 1,
                            "delay_seconds": delay,
                            "error": str(e),
                        },
                    )

                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Function failed after {self.max_retries + 1} attempts",
                        extra={
                            **context,
                            "attempts": attempt + 1,
                            "error": str(e),
                        },
                    )

        # All retries exhausted
        raise last_exception if last_exception else RuntimeError("Retry failed")


def with_retry(
    config: ResilienceConfig,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator factory for adding retry logic to async functions.

    Args:
        config: Resilience configuration.
        retryable_exceptions: Tuple of exception types that should trigger retry.

    Returns:
        Decorator function.

    Example:
        >>> @with_retry(config, retryable_exceptions=(LLMError,))
        ... async def generate_sql(question: str) -> str:
        ...     return await llm_client.generate(question)
    """
    retry_handler = RetryWithBackoff(config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Extract request_id from kwargs if present for logging context
            context = {}
            if "request_id" in kwargs:
                context["request_id"] = kwargs["request_id"]

            return await retry_handler.execute(
                func,
                *args,
                retryable_exceptions=retryable_exceptions,
                context=context,
                **kwargs,
            )

        return wrapper

    return decorator


# Specific retry configurations for different operations

def with_llm_retry(config: ResilienceConfig) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for LLM operations with appropriate retry settings.

    LLM operations may fail due to rate limits, network issues, or transient API errors.

    Args:
        config: Resilience configuration.

    Returns:
        Decorator configured for LLM operations.
    """
    return with_retry(
        config,
        retryable_exceptions=(
            LLMError,
            ConnectionError,
            TimeoutError,
        ),
    )


def with_db_retry(config: ResilienceConfig) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for database operations with appropriate retry settings.

    Database operations may fail due to connection issues or transient errors.

    Args:
        config: Resilience configuration.

    Returns:
        Decorator configured for database operations.
    """
    # Import here to avoid circular dependency
    import asyncpg

    return with_retry(
        config,
        retryable_exceptions=(
            ConnectionError,
            TimeoutError,
            asyncpg.PostgresConnectionError,
            asyncpg.TooManyConnectionsError,
        ),
    )
