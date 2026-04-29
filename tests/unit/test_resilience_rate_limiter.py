"""Rate limiter tests for resilience module.

This module tests the RateLimiter and MultiRateLimiter functionality.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from pg_mcp.config.settings import ResilienceConfig
from pg_mcp.resilience.rate_limiter import (
    MultiRateLimiter,
    RateLimitExceeded,
    RateLimiter,
)


class TestRateLimiter:
    """Test basic RateLimiter functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_within_limit(self) -> None:
        """Test that operations within limit are allowed."""
        limiter = RateLimiter(max_concurrent=3)

        # Should be able to acquire 3 times
        assert await limiter.acquire(timeout=0.1) is True
        assert await limiter.acquire(timeout=0.1) is True
        assert await limiter.acquire(timeout=0.1) is True

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_over_limit(self) -> None:
        """Test that operations over limit are blocked until slot frees."""
        limiter = RateLimiter(max_concurrent=1)

        # Acquire once
        assert await limiter.acquire(timeout=0.1) is True

        # Second acquire should fail (timeout) - use 0.1s to ensure it times out
        assert await limiter.acquire(timeout=0.1) is False

    @pytest.mark.asyncio
    async def test_rate_limiter_context_manager(self) -> None:
        """Test context manager usage."""
        limiter = RateLimiter(max_concurrent=1)

        async with limiter:
            # Inside context, one slot is used
            assert limiter.active_count == 1

        # After context, slot is released
        assert limiter.active_count == 0


class TestMultiRateLimiter:
    """Test MultiRateLimiter functionality."""

    @pytest.mark.asyncio
    async def test_query_rate_limiting(self) -> None:
        """Test query-specific rate limiting."""
        limiter = MultiRateLimiter(query_limit=1, llm_limit=5)

        # Acquire query slot
        await limiter.acquire_query()

        # Second query acquire should raise RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            await limiter.acquire_query(timeout=0.01)

    @pytest.mark.asyncio
    async def test_llm_rate_limiting(self) -> None:
        """Test LLM-specific rate limiting."""
        limiter = MultiRateLimiter(query_limit=5, llm_limit=1)

        # Acquire LLM slot
        await limiter.acquire_llm()

        # Second LLM acquire should raise RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            await limiter.acquire_llm(timeout=0.01)

    @pytest.mark.asyncio
    async def test_query_and_llm_limits_are_separate(self) -> None:
        """Test that query and LLM limits are independent."""
        limiter = MultiRateLimiter(query_limit=1, llm_limit=1)

        # Acquire both slots
        await limiter.acquire_query()
        await limiter.acquire_llm()

        # Both should be blocked now
        with pytest.raises(RateLimitExceeded):
            await limiter.acquire_query(timeout=0.01)

        with pytest.raises(RateLimitExceeded):
            await limiter.acquire_llm(timeout=0.01)

    @pytest.mark.asyncio
    async def test_query_context_manager(self) -> None:
        """Test query context manager."""
        limiter = MultiRateLimiter(query_limit=1, llm_limit=5)

        async with limiter.for_queries():
            # Inside query context
            pass

        # Should be able to acquire again after context exits
        await limiter.acquire_query()

    @pytest.mark.asyncio
    async def test_llm_context_manager(self) -> None:
        """Test LLM context manager."""
        limiter = MultiRateLimiter(query_limit=5, llm_limit=1)

        async with limiter.for_llm():
            # Inside LLM context
            pass

        # Should be able to acquire again after context exits
        await limiter.acquire_llm()


class TestResilienceConfigRateLimits:
    """Test that ResilienceConfig rate limits are used correctly."""

    def test_rate_limiter_uses_config_values(self) -> None:
        """Test that MultiRateLimiter uses configured rate limits."""
        config = ResilienceConfig(
            query_rate_limit=50,
            llm_rate_limit=10,
        )

        limiter = MultiRateLimiter(
            query_limit=config.query_rate_limit,
            llm_limit=config.llm_rate_limit,
        )

        assert limiter.query_limiter.max_concurrent == 50
        assert limiter.llm_limiter.max_concurrent == 10
