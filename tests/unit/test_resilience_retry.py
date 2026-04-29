"""Retry and backoff tests for resilience module.

This module tests the RetryWithBackoff functionality.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pg_mcp.config.settings import ResilienceConfig
from pg_mcp.models.errors import LLMError
from pg_mcp.resilience.retry import (
    RetryWithBackoff,
    with_db_retry,
    with_llm_retry,
    with_retry,
)


class TestRetryWithBackoff:
    """Test RetryWithBackoff functionality."""

    @pytest.fixture
    def config(self) -> ResilienceConfig:
        """Create test resilience config."""
        return ResilienceConfig(
            max_retries=3,
            retry_delay=0.1,  # Minimum allowed, fast for tests
            backoff_factor=2.0,
        )

    @pytest.mark.asyncio
    async def test_success_no_retry(self, config: ResilienceConfig) -> None:
        """Test that successful execution doesn't retry."""
        retry = RetryWithBackoff(config)
        mock_func = AsyncMock(return_value="success")

        result = await retry.execute(mock_func)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, config: ResilienceConfig) -> None:
        """Test that failures trigger retries."""
        retry = RetryWithBackoff(config)
        mock_func = AsyncMock(side_effect=[ValueError("error1"), ValueError("error2"), "success"])

        result = await retry.execute(
            mock_func,
            retryable_exceptions=(ValueError,),
        )

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self, config: ResilienceConfig) -> None:
        """Test that all retries exhausted raises last exception."""
        retry = RetryWithBackoff(config)
        mock_func = AsyncMock(side_effect=ValueError("always fails"))

        with pytest.raises(ValueError, match="always fails"):
            await retry.execute(
                mock_func,
                retryable_exceptions=(ValueError,),
            )

        # Initial attempt + 3 retries = 4 calls
        assert mock_func.call_count == 4

    @pytest.mark.asyncio
    async def test_non_retryable_exception_not_retried(self, config: ResilienceConfig) -> None:
        """Test that non-retryable exceptions don't trigger retries."""
        retry = RetryWithBackoff(config)
        mock_func = AsyncMock(side_effect=RuntimeError("fatal"))

        with pytest.raises(RuntimeError, match="fatal"):
            await retry.execute(
                mock_func,
                retryable_exceptions=(ValueError,),  # RuntimeError not included
            )

        assert mock_func.call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_backoff_delay_increases(self, config: ResilienceConfig) -> None:
        """Test that backoff delay increases with each retry."""
        retry = RetryWithBackoff(config)

        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        mock_func = AsyncMock(side_effect=[ValueError("error")] * 3 + ["success"])

        # Patch asyncio.sleep
        import asyncio
        asyncio.sleep = mock_sleep  # type: ignore

        try:
            await retry.execute(
                mock_func,
                retryable_exceptions=(ValueError,),
            )
        finally:
            asyncio.sleep = original_sleep

        # Should have 3 delays (backoff_factor=2.0)
        # Delays: 0.1, 0.2, 0.4
        assert len(delays) == 3
        assert delays[0] == pytest.approx(0.1, rel=0.1)
        assert delays[1] == pytest.approx(0.2, rel=0.1)
        assert delays[2] == pytest.approx(0.4, rel=0.1)


class TestRetryDecorators:
    """Test retry decorator factory functions."""

    @pytest.fixture
    def config(self) -> ResilienceConfig:
        """Create test resilience config."""
        return ResilienceConfig(
            max_retries=2,
            retry_delay=0.1,
            backoff_factor=2.0,
        )

    @pytest.mark.asyncio
    async def test_with_retry_decorator(self, config: ResilienceConfig) -> None:
        """Test generic retry decorator."""
        call_count = 0

        @with_retry(config, retryable_exceptions=(ValueError,))
        async def flaky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "success"

        result = await flaky_function()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_llm_retry_decorator(self, config: ResilienceConfig) -> None:
        """Test LLM-specific retry decorator."""
        call_count = 0

        @with_llm_retry(config)
        async def llm_call() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise LLMError(message="API error")
            return "llm response"

        result = await llm_call()

        assert result == "llm response"
        assert call_count == 2


class TestResilienceConfigUsage:
    """Test that ResilienceConfig retry settings are properly used."""

    @pytest.mark.asyncio
    async def test_retry_uses_config_values(self) -> None:
        """Test that retry delay and backoff from config are used."""
        config = ResilienceConfig(
            max_retries=1,
            retry_delay=0.1,
            backoff_factor=3.0,
        )

        retry = RetryWithBackoff(config)
        mock_func = AsyncMock(side_effect=[ValueError("error"), "success"])

        result = await retry.execute(
            mock_func,
            retryable_exceptions=(ValueError,),
        )

        assert result == "success"
        assert mock_func.call_count == 2
