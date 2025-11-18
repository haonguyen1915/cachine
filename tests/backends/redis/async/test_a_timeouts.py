"""Test Redis timeout configurations."""

from __future__ import annotations

import time

import pytest

from cachine.backends.redis.async_ import AsyncRedisCache
from cachine.backends.redis.sync import RedisCache
from cachine.models.redis_config import RedisSingleConfig


@pytest.mark.asyncio
async def test_async_redis_socket_connect_timeout() -> None:
    """Test that async socket_connect_timeout is respected."""
    config = RedisSingleConfig(
        host="invalid.redis.host.that.does.not.exist",
        port=6379,
        db=0,
        socket_connect_timeout=3,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # Measure time to failure
    start = time.time()
    with pytest.raises(Exception) as exc_info:  # noqa: B017
        await cache.set("key", "value")
        print(f"Exception raised: {exc_info.value}")
    elapsed = time.time() - start

    await cache.close()

    # Should fail quickly
    assert elapsed < 1.0, f"Async connection attempt took too long: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_async_redis_socket_timeout_on_slow_operations() -> None:
    """Test that async socket_timeout affects operation timeouts."""
    config = RedisSingleConfig(
        host="localhost",
        port=9999,
        db=0,
        socket_timeout=0.1,
        socket_connect_timeout=0.1,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # Should timeout quickly
    start = time.time()
    with pytest.raises(Exception):  # noqa: B017
        await cache.get("key")
    elapsed = time.time() - start

    await cache.close()

    assert elapsed < 1.0, f"Async operation took too long: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_async_redis_retry_on_timeout_disabled() -> None:
    """Test that async retry_on_timeout=False doesn't retry."""
    config = RedisSingleConfig(
        host="localhost",
        port=9999,
        db=0,
        socket_timeout=0.1,
        socket_connect_timeout=0.1,
        retry_on_timeout=False,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # Should fail on first attempt
    start = time.time()
    with pytest.raises(Exception):  # noqa: B017
        await cache.set("key", "value")
    elapsed = time.time() - start

    await cache.close()

    # Should be quick since no retries
    assert elapsed < 0.5, f"Async should fail quickly without retry: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_async_redis_timeout_config_values() -> None:
    """Test that async timeout values are correctly configured."""
    config = RedisSingleConfig(
        host="localhost",
        port=6379,
        db=0,
        socket_timeout=3.0,
        socket_connect_timeout=1.5,
        retry_on_timeout=True,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # Verify config values are stored
    assert cache._config.socket_timeout == 3.0
    assert cache._config.socket_connect_timeout == 1.5
    assert cache._config.retry_on_timeout is True

    await cache.close()


@pytest.mark.asyncio
async def test_async_redis_default_timeout_values() -> None:
    """Test that default timeout values are reasonable."""
    config = RedisSingleConfig(
        host="localhost",
        port=6379,
        db=0,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # Check defaults
    assert cache._config.socket_timeout is None  # No default timeout
    assert cache._config.socket_connect_timeout is None
    assert cache._config.retry_on_timeout is False

    await cache.close()


def test_sync_redis_default_timeout_values() -> None:
    """Test that sync default timeout values are reasonable."""
    config = RedisSingleConfig(
        host="localhost",
        port=6379,
        db=0,
    )

    cache = RedisCache(config, namespace="ut")

    # Check defaults
    assert cache._config.socket_timeout is None
    assert cache._config.socket_connect_timeout is None
    assert cache._config.retry_on_timeout is False
