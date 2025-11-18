from __future__ import annotations

import pytest

from cachine.backends.redis.async_ import AsyncRedisCache
from cachine.decorators.cached import cached
from cachine.middleware.fail_open import AsyncFailOpenMiddleware
from cachine.models.redis_config import RedisSingleConfig


@pytest.mark.asyncio
async def test_async_redis_connection_failure_on_invalid_host() -> None:
    """Test that async operations fail when Redis host is unreachable."""
    config = RedisSingleConfig(
        host="invalid.redis.host.that.does.not.exist",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # Operations should raise connection errors
    with pytest.raises(Exception):  # noqa: B017
        await cache.set("key", "value")

    with pytest.raises(Exception):  # noqa: B017
        await cache.get("key")

    await cache.close()


@pytest.mark.asyncio
async def test_async_redis_connection_failure_on_invalid_port() -> None:
    """Test that async operations fail when connecting to wrong port."""
    config = RedisSingleConfig(
        host="localhost",
        port=9999,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # Operations should raise connection errors
    with pytest.raises(Exception):  # noqa: B017
        await cache.set("key", "value")

    with pytest.raises(Exception):  # noqa: B017
        await cache.get("key")

    await cache.close()


@pytest.mark.asyncio
async def test_async_redis_clear_swallows_connection_errors() -> None:
    """Test that async clear() doesn't raise on connection failure."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # clear should swallow connection errors
    await cache.clear(dangerously_clear_all=True)

    await cache.close()


@pytest.mark.asyncio
async def test_async_redis_ping_reports_unhealthy_on_connection_failure() -> None:
    """Test that async ping returns unhealthy status when Redis is unreachable."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    cache = AsyncRedisCache(config, namespace="ut")

    # ping should return unhealthy
    health = await cache.ping()
    assert health["healthy"] is False

    # ping_ok should return False
    result = await cache.ping_ok()
    assert result is False

    await cache.close()


@pytest.mark.asyncio
async def test_async_fail_open_middleware_handles_connection_failure() -> None:
    """Test that async fail-open middleware allows operations to continue when Redis fails."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    base_cache = AsyncRedisCache(config, namespace="ut")
    cache = AsyncFailOpenMiddleware(base_cache)

    call_count = {"n": 0}

    @cached(cache=cache, ttl=60)
    async def compute(x: int) -> int:
        call_count["n"] += 1
        return x * 2

    # Should execute function despite connection failure
    result = await compute(3)
    assert result == 6
    assert call_count["n"] == 1

    # Second call should also work (no cache, so recomputes)
    result = await compute(3)
    assert result == 6
    assert call_count["n"] == 2

    await cache.close()


@pytest.mark.asyncio
async def test_async_fail_open_middleware_get_returns_default_on_failure() -> None:
    """Test that async fail-open middleware returns default value on connection failure."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    base_cache = AsyncRedisCache(config, namespace="ut")
    cache = AsyncFailOpenMiddleware(base_cache, log_tracebacks=True)

    # Should return default value
    result = await cache.get("nonexistent", default="default_value")
    assert result == "default_value"

    await cache.close()


@pytest.mark.asyncio
async def test_async_fail_open_middleware_set_does_not_raise() -> None:
    """Test that async fail-open middleware doesn't raise on set() failure."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    base_cache = AsyncRedisCache(config, namespace="ut")
    cache = AsyncFailOpenMiddleware(base_cache)

    # Should not raise
    await cache.set("key", "value", ttl=60)

    await cache.close()


@pytest.mark.asyncio
async def test_async_fail_open_middleware_delete_does_not_raise() -> None:
    """Test that async fail-open middleware doesn't raise on delete() failure."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    base_cache = AsyncRedisCache(config, namespace="ut")
    cache = AsyncFailOpenMiddleware(base_cache)

    # Should not raise, returns False (not deleted)
    result = await cache.delete("key")
    assert result is False

    await cache.close()


@pytest.mark.asyncio
async def test_async_fail_open_middleware_invalidate_tags_does_not_raise() -> None:
    """Test that async fail-open middleware doesn't raise on invalidate_tags() failure."""
    config = RedisSingleConfig(
        host="invalid.host",
        port=6379,
        db=0,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )

    base_cache = AsyncRedisCache(config, namespace="ut")
    cache = AsyncFailOpenMiddleware(base_cache)

    # Should not raise, returns 0 (nothing deleted)
    result = await cache.invalidate_tags(["tag1", "tag2"])
    assert result == 0

    await cache.close()
