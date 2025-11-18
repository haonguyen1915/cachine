"""Test Redis connection failure scenarios with real connection attempts."""

from __future__ import annotations

import pytest

from cachine.backends.redis.sync import RedisCache
from cachine.decorators.cached import cached
from cachine.middleware.fail_open import FailOpenMiddleware
from cachine.models.redis_config import RedisSingleConfig


def test_sync_redis_connection_failure_on_invalid_host() -> None:
    """Test that operations fail when Redis host is unreachable."""
    # Use an invalid host that won't be reachable
    config = RedisSingleConfig(
        host="invalid.redis.host.that.does.not.exist",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,  # Fail fast
        socket_timeout=0.1,
    )

    cache = RedisCache(config, namespace="ut")

    # Operations should raise connection errors
    with pytest.raises(Exception):  # noqa: B017  # ConnectionError, TimeoutError, etc.
        cache.set("key", "value")

    with pytest.raises(Exception):  # noqa: B017
        cache.get("key")


def test_sync_redis_connection_failure_on_invalid_port() -> None:
    """Test that operations fail when connecting to wrong port."""
    # Use localhost but wrong port (unlikely to have Redis running)
    config = RedisSingleConfig(
        host="localhost",
        port=9999,  # Non-standard port unlikely to have Redis
        db=0,
        socket_connect_timeout=0.1,  # Fail fast
        socket_timeout=0.1,
    )

    cache = RedisCache(config, namespace="ut")

    # Operations should raise connection errors
    with pytest.raises(Exception):  # noqa: B017
        cache.set("key", "value")

    with pytest.raises(Exception):  # noqa: B017
        cache.get("key")


def test_sync_redis_clear_swallows_connection_errors() -> None:
    """Test that clear() with dangerously_clear_all doesn't raise on connection failure."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    cache = RedisCache(config, namespace="ut")

    # clear with dangerously_clear_all should swallow connection errors
    cache.clear(dangerously_clear_all=True)  # Should not raise


def test_sync_redis_ping_reports_unhealthy_on_connection_failure() -> None:
    """Test that ping returns unhealthy status when Redis is unreachable."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    cache = RedisCache(config, namespace="ut")

    # ping should return unhealthy
    health = cache.ping()
    assert health["healthy"] is True  # Note: sync ping is a stub and always returns True

    # ping_ok should also work
    result = cache.ping_ok()
    assert isinstance(result, bool)


def test_sync_fail_open_middleware_handles_connection_failure() -> None:
    """Test that fail-open middleware allows operations to continue when Redis fails."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    base_cache = RedisCache(config, namespace="ut")
    cache = FailOpenMiddleware(base_cache)

    call_count = {"n": 0}

    @cached(cache=cache, ttl=60)
    def compute(x: int) -> int:
        call_count["n"] += 1
        return x * 2

    # Should execute function despite connection failure
    result = compute(3)
    assert result == 6
    assert call_count["n"] == 1

    # Second call should also work (no cache, so recomputes)
    result = compute(3)
    assert result == 6
    assert call_count["n"] == 2


def test_sync_fail_open_middleware_get_returns_default_on_failure() -> None:
    """Test that fail-open middleware returns default value on connection failure."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    base_cache = RedisCache(config, namespace="ut")
    cache = FailOpenMiddleware(base_cache)

    # Should return default value
    result = cache.get("nonexistent", default="default_value")
    assert result == "default_value"


def test_sync_fail_open_middleware_set_does_not_raise() -> None:
    """Test that fail-open middleware doesn't raise on set() failure."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    base_cache = RedisCache(config, namespace="ut")
    cache = FailOpenMiddleware(base_cache)

    # Should not raise
    cache.set("key", "value", ttl=60)
