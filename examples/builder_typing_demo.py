"""Demonstrate that CacheBuilder returns proper Cache/AsyncCache types.

This example shows that:
1. CacheBuilder.build() returns Cache type (not concrete middleware class)
2. AsyncCacheBuilder.build() returns AsyncCache type
3. Type checkers recognize the returned value as the protocol type

Run with: python examples/builder_typing_demo.py
"""
from __future__ import annotations

from cachine import AsyncCacheBuilder, AsyncRedisCache, CacheBuilder, RedisCache
from cachine.core.types import AsyncCache, Cache
from cachine.middleware import AsyncMetricsMiddleware, MetricsMiddleware


def type_annotation_demo() -> None:
    """Demonstrate proper type annotations with builder pattern."""
    # Example 1: Sync builder with explicit Cache type
    redis_cache = RedisCache(host="localhost", port=6379, db=0)

    # The return type is Cache, NOT MetricsMiddleware
    cache: Cache = (
        CacheBuilder.from_cache(redis_cache)
        .add_middleware(MetricsMiddleware)
        .build()
    )

    print(f"✓ Sync cache type: {type(cache).__name__}")
    print(f"✓ Implements Cache protocol: {isinstance(cache, Cache)}")
    print(f"✓ Can use all Cache methods: set, get, delete, etc.\n")

    # Example 2: Async builder with explicit AsyncCache type
    async_redis = AsyncRedisCache(host="localhost", port=6379, db=0)

    cache_async: AsyncCache = (
        AsyncCacheBuilder.from_cache(async_redis)
        .add_middleware(AsyncMetricsMiddleware)
        .build()
    )

    print(f"✓ Async cache type: {type(cache_async).__name__}")
    print(f"✓ Implements AsyncCache protocol: {isinstance(cache_async, AsyncCache)}")
    print(f"✓ Can use all AsyncCache methods: set, get, delete, etc.\n")


def multiple_middleware_demo() -> None:
    """Show type safety with multiple middleware layers."""
    from tests.middleware.test_configurable_middleware import ConfigurableMetricsMiddleware

    redis_cache = RedisCache(host="localhost", port=6379, db=0)

    # Multiple middleware, still returns Cache type
    cache: Cache = (
        CacheBuilder.from_cache(redis_cache)
        .add_middleware(ConfigurableMetricsMiddleware.create(namespace="app1"))
        .add_middleware(MetricsMiddleware)
        .build()
    )

    print(f"✓ Multiple middleware type: {type(cache).__name__}")
    print(f"✓ Still implements Cache protocol: {isinstance(cache, Cache)}")
    print("\n--- Summary ---")
    print("The builder pattern ensures that .build() returns Cache/AsyncCache")
    print("This gives you type safety while allowing flexible middleware composition!")


if __name__ == "__main__":
    print("=== Cache Builder Type Safety Demo ===\n")
    type_annotation_demo()
    multiple_middleware_demo()