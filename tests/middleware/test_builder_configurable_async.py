"""Test cases for AsyncCacheBuilder with configurable middleware."""

from __future__ import annotations

import pytest

from cachine import AsyncCacheBuilder, AsyncRedisCache
from cachine.middleware import AsyncMetricsMiddleware, MetricsMiddleware
from tests.middleware.configurable_middleware import AsyncConfigurableMetricsMiddleware


@pytest.mark.asyncio
async def test_async_builder_with_configured_middleware_factory(a_redis_cache: AsyncRedisCache) -> None:
    """Test async builder with factory-style configured middleware."""
    cache = (
        AsyncCacheBuilder.from_cache(a_redis_cache)
        .add_middleware(AsyncConfigurableMetricsMiddleware.create(namespace="async-app", enabled=True))
        .build()
    )

    # Test operations
    await cache.set("akey1", "avalue1")
    assert await cache.get("akey1") == "avalue1"
    assert await cache.get("missing", default=None) is None

    # Verify configuration
    stats = cache.get_stats()
    assert stats["namespace"] == "async-app"
    assert stats["enabled"] is True
    assert stats["hits"] == 1
    assert stats["misses"] == 1


@pytest.mark.asyncio
async def test_async_builder_with_lambda_configured_middleware(a_redis_cache: AsyncRedisCache) -> None:
    """Test async builder with lambda-configured middleware."""
    cache = (
        AsyncCacheBuilder.from_cache(a_redis_cache)
        .add_middleware(lambda c: AsyncConfigurableMetricsMiddleware(c, namespace="lambda-async", enabled=False))
        .build()
    )

    # Test operations
    await cache.set("akey2", "avalue2")
    assert await cache.get("akey2") == "avalue2"
    assert await cache.get("missing2", default=None) is None

    # Verify configuration
    stats = cache.get_stats()
    assert stats["namespace"] == "lambda-async"
    assert stats["enabled"] is False
    assert stats["hits"] == 0  # Not counting because disabled
    assert stats["misses"] == 0


@pytest.mark.asyncio
async def test_async_builder_with_multiple_configured_middlewares(a_redis_cache: AsyncRedisCache) -> None:
    """Test async builder with multiple configured middlewares."""
    cache = (
        AsyncCacheBuilder.from_cache(a_redis_cache)
        .add_middleware(AsyncConfigurableMetricsMiddleware.create(namespace="async-first"))
        .add_middleware(AsyncMetricsMiddleware)  # Standard middleware
        .build()
    )

    # Test operations
    await cache.set("akey3", "avalue3")
    assert await cache.get("akey3") == "avalue3"
    assert await cache.get("missing3", default=None) is None

    # The outer middleware (AsyncMetricsMiddleware) should have stats
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1

    # Access inner middleware stats
    inner_cache = cache._cache  # type: ignore[attr-defined]
    inner_stats = inner_cache.get_stats()
    assert inner_stats["namespace"] == "async-first"
    assert inner_stats["hits"] == 1
    assert inner_stats["misses"] == 1


@pytest.mark.asyncio
@pytest.mark.skip(reason="memory:// URL scheme not supported")
async def test_async_builder_from_url_with_configured_middleware() -> None:
    """Test async builder from URL with configured middleware."""
    cache = (
        AsyncCacheBuilder.from_url("memory://")
        .add_middleware(AsyncConfigurableMetricsMiddleware.create(namespace="async-url-test", enabled=True))
        .build()
    )

    # Test operations
    await cache.set("url-akey", "url-avalue")
    assert await cache.get("url-akey") == "url-avalue"
    assert await cache.get("missing-url", default="default") == "default"

    # Verify configuration
    stats = cache.get_stats()
    assert stats["namespace"] == "async-url-test"
    assert stats["hits"] == 1
    assert stats["misses"] == 1


@pytest.mark.asyncio
async def test_async_builder_sync_middleware_auto_mapping_with_config(a_redis_cache: AsyncRedisCache) -> None:
    """Test that sync middleware classes are auto-mapped even when using factory pattern.

    Note: This tests the current behavior where sync middleware classes get mapped to async,
    but factory functions (lambdas) are used as-is, so we should use async factories.
    """
    # Using sync MetricsMiddleware class - should auto-map to AsyncMetricsMiddleware
    cache = (
        AsyncCacheBuilder.from_cache(a_redis_cache)
        .add_middleware(MetricsMiddleware)  # Sync class → auto-mapped to async
        .build()
    )

    await cache.set("sync-mapped", "value")
    assert await cache.get("sync-mapped") == "value"

    stats = cache.get_stats()
    assert stats["hits"] == 1


@pytest.mark.asyncio
async def test_async_builder_chaining_multiple_configured_middlewares(a_redis_cache: AsyncRedisCache) -> None:
    """Test chaining multiple configured middlewares with different settings."""
    cache = (
        AsyncCacheBuilder.from_cache(a_redis_cache)
        .add_middleware(AsyncConfigurableMetricsMiddleware.create(namespace="async-layer1", enabled=True))
        .add_middleware(AsyncConfigurableMetricsMiddleware.create(namespace="async-layer2", enabled=True))
        .build()
    )

    # Test operations
    await cache.set("chain-akey", "chain-avalue")
    assert await cache.get("chain-akey") == "chain-avalue"

    # The outermost middleware stats
    stats = cache.get_stats()
    assert stats["namespace"] == "async-layer2"  # Outer layer
    assert stats["hits"] == 1


@pytest.mark.asyncio
async def test_async_builder_as_factory_with_configured_middleware(a_redis_cache: AsyncRedisCache) -> None:
    """Test that async builder.as_factory() works with configured middleware."""
    factory = (
        AsyncCacheBuilder.from_cache(a_redis_cache)
        .add_middleware(AsyncConfigurableMetricsMiddleware.create(namespace="async-factory-test"))
        .as_factory()
    )

    # Build cache from factory
    cache = factory()
    await cache.set("factory-akey", "factory-avalue")
    assert await cache.get("factory-akey") == "factory-avalue"

    stats = cache.get_stats()
    assert stats["namespace"] == "async-factory-test"
    assert stats["hits"] == 1
