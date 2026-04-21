"""Demonstrate that CacheBuilder returns proper Cache/AsyncCache types.

This example shows that:
1. ``CacheBuilder(...).build()`` returns the ``Cache`` protocol.
2. ``AsyncCacheBuilder(...).build()`` returns the ``AsyncCache`` protocol.
3. Type checkers recognise the returned value as the protocol type.

Run with: python examples/builder_typing_demo.py
"""

from __future__ import annotations

from cachine import AsyncCacheBuilder, AsyncRedisCache, CacheBuilder, RedisCache
from cachine.core.types import AsyncCache, Cache
from cachine.middleware import AsyncMetricsMiddleware, MetricsMiddleware


def type_annotation_demo() -> None:
    """Demonstrate proper type annotations with builder pattern."""

    # Sync: pass a concrete cache, get the Cache protocol back
    redis_cache = RedisCache(host="localhost", port=6379, db=0)
    cache: Cache = CacheBuilder(redis_cache).add_middleware(MetricsMiddleware).build()

    print(f"✓ Sync cache type: {type(cache).__name__}")
    print(f"✓ Implements Cache protocol: {isinstance(cache, Cache)}")
    print("✓ Can use all Cache methods: set, get, delete, etc.\n")

    # Async mirror: AsyncCacheBuilder + AsyncCache protocol
    async_redis = AsyncRedisCache(host="localhost", port=6379, db=0)
    cache_async: AsyncCache = AsyncCacheBuilder(async_redis).add_middleware(AsyncMetricsMiddleware).build()

    print(f"✓ Async cache type: {type(cache_async).__name__}")
    print(f"✓ Implements AsyncCache protocol: {isinstance(cache_async, AsyncCache)}")
    print("✓ Can use all AsyncCache methods: set, get, delete, etc.\n")


def multiple_middleware_demo() -> None:
    """Show type safety with multiple middleware layers and kwargs forwarding."""
    from cachine.middleware import CompressionMiddleware

    redis_cache = RedisCache(host="localhost", port=6379, db=0)

    # add_middleware(cls, **kwargs) forwards constructor kwargs — no lambdas
    cache: Cache = (
        CacheBuilder(redis_cache)
        .add_middleware(CompressionMiddleware, algorithm="gzip", min_size=1024)
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
