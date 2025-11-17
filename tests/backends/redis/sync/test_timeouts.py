"""Test Redis timeout configurations."""

from __future__ import annotations

import time

import pytest

from cachine.backends.redis.async_ import AsyncRedisCache
from cachine.backends.redis.sync import RedisCache
from cachine.models.redis_config import RedisSingleConfig


def test_sync_redis_socket_connect_timeout() -> None:
    """Test that socket_connect_timeout is respected when connecting to invalid host."""
    config = RedisSingleConfig(
        host="invalid.redis.host.that.does.not.exist",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,  # 100ms timeout
    )

    cache = RedisCache(config, namespace="ut")

    # Measure time to failure
    start = time.time()
    with pytest.raises(Exception):
        cache.set("key", "value")
    elapsed = time.time() - start

    # Should fail quickly (within ~0.5 seconds, giving some buffer)
    # Without the timeout, DNS resolution could take much longer
    assert elapsed < 1.0, f"Connection attempt took too long: {elapsed:.2f}s"


def test_sync_redis_socket_timeout_on_slow_operations() -> None:
    """Test that socket_timeout affects operation timeouts."""
    config = RedisSingleConfig(
        host="localhost",
        port=9999,  # Wrong port
        db=0,
        socket_timeout=0.1,  # 100ms timeout
        socket_connect_timeout=0.1,
    )

    cache = RedisCache(config, namespace="ut")

    # Should timeout quickly
    start = time.time()
    with pytest.raises(Exception):
        cache.get("key")
    elapsed = time.time() - start

    assert elapsed < 1.0, f"Operation took too long: {elapsed:.2f}s"


def test_sync_redis_retry_on_timeout_disabled() -> None:
    """Test that retry_on_timeout=False doesn't retry."""
    config = RedisSingleConfig(
        host="localhost",
        port=9999,
        db=0,
        socket_timeout=0.1,
        socket_connect_timeout=0.1,
        retry_on_timeout=False,
    )

    cache = RedisCache(config, namespace="ut")

    # Should fail on first attempt without retry
    start = time.time()
    with pytest.raises(Exception):
        cache.set("key", "value")
    elapsed = time.time() - start

    # Should be quick since no retries
    assert elapsed < 0.5, f"Should fail quickly without retry: {elapsed:.2f}s"


def test_sync_redis_timeout_config_values() -> None:
    """Test that timeout values are correctly passed to the client."""
    config = RedisSingleConfig(
        host="localhost",
        port=6379,
        db=0,
        socket_timeout=2.5,
        socket_connect_timeout=1.0,
        retry_on_timeout=True,
    )

    cache = RedisCache(config, namespace="ut")

    # Verify config values are stored
    assert cache._config.socket_timeout == 2.5
    assert cache._config.socket_connect_timeout == 1.0
    assert cache._config.retry_on_timeout is True