"""Test cases for CacheBuilder with configurable middleware."""

from __future__ import annotations

import pytest

from cachine import CacheBuilder, RedisCache
from cachine.middleware import MetricsMiddleware
from tests.middleware.configurable_middleware import ConfigurableMetricsMiddleware


def test_builder_with_configured_middleware_factory(redis_cache: RedisCache) -> None:
    """Test builder with factory-style configured middleware."""
    cache = (
        CacheBuilder.from_cache(redis_cache).add_middleware(ConfigurableMetricsMiddleware.create(namespace="my-app", enabled=True)).build()
    )

    # Test operations
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"
    assert cache.get("missing", default=None) is None

    # Verify configuration
    stats = cache.get_stats()
    assert stats["namespace"] == "my-app"
    assert stats["enabled"] is True
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_builder_with_lambda_configured_middleware(redis_cache: RedisCache) -> None:
    """Test builder with lambda-configured middleware."""
    cache = (
        CacheBuilder.from_cache(redis_cache)
        .add_middleware(lambda c: ConfigurableMetricsMiddleware(c, namespace="lambda-app", enabled=False))
        .build()
    )

    # Test operations
    cache.set("key2", "value2")
    assert cache.get("key2") == "value2"
    assert cache.get("missing2", default=None) is None

    # Verify configuration
    stats = cache.get_stats()
    assert stats["namespace"] == "lambda-app"
    assert stats["enabled"] is False  # Metrics disabled
    assert stats["hits"] == 0  # Not counting because disabled
    assert stats["misses"] == 0


def test_builder_with_multiple_configured_middlewares(redis_cache: RedisCache) -> None:
    """Test builder with multiple configured middlewares."""
    cache = (
        CacheBuilder.from_cache(redis_cache)
        .add_middleware(ConfigurableMetricsMiddleware.create(namespace="first"))
        .add_middleware(MetricsMiddleware)  # Standard middleware
        .build()
    )

    # Test operations
    cache.set("key3", "value3")
    assert cache.get("key3") == "value3"
    assert cache.get("missing3", default=None) is None

    # The outer middleware (MetricsMiddleware) should have stats
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1

    # Access inner middleware stats through the wrapper
    inner_cache = cache._cache  # type: ignore[attr-defined]
    inner_stats = inner_cache.get_stats()
    assert inner_stats["namespace"] == "first"
    assert inner_stats["hits"] == 1
    assert inner_stats["misses"] == 1


@pytest.mark.skip(reason="memory:// URL scheme not supported")
def test_builder_from_url_with_configured_middleware() -> None:
    """Test builder from URL with configured middleware."""
    cache = (
        CacheBuilder.from_url("memory://").add_middleware(ConfigurableMetricsMiddleware.create(namespace="url-test", enabled=True)).build()
    )

    # Test operations
    cache.set("url-key", "url-value")
    assert cache.get("url-key") == "url-value"
    assert cache.get("missing-url", default="default") == "default"

    # Verify configuration
    stats = cache.get_stats()
    assert stats["namespace"] == "url-test"
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_builder_chaining_multiple_configured_middlewares(redis_cache: RedisCache) -> None:
    """Test chaining multiple configured middlewares with different settings."""
    # Simulate a scenario with multiple layers
    cache = (
        CacheBuilder.from_cache(redis_cache)
        .add_middleware(ConfigurableMetricsMiddleware.create(namespace="layer1", enabled=True))
        .add_middleware(ConfigurableMetricsMiddleware.create(namespace="layer2", enabled=True))
        .build()
    )

    # Test operations
    cache.set("chain-key", "chain-value")
    assert cache.get("chain-key") == "chain-value"

    # The outermost middleware stats
    stats = cache.get_stats()
    assert stats["namespace"] == "layer2"  # Outer layer
    assert stats["hits"] == 1


def test_builder_as_factory_with_configured_middleware(redis_cache: RedisCache) -> None:
    """Test that builder.as_factory() works with configured middleware."""
    factory = (
        CacheBuilder.from_cache(redis_cache).add_middleware(ConfigurableMetricsMiddleware.create(namespace="factory-test")).as_factory()
    )

    # Build cache from factory
    cache = factory()
    cache.set("factory-key", "factory-value")
    assert cache.get("factory-key") == "factory-value"

    stats = cache.get_stats()
    assert stats["namespace"] == "factory-test"
    assert stats["hits"] == 1
