from __future__ import annotations

import pytest

from cachine import AsyncCacheBuilder, AsyncRedisCache
from cachine.middleware import AsyncMetricsMiddleware, MetricsMiddleware


@pytest.mark.asyncio
async def test_async_builder_from_cache_with_async_middleware(a_redis_cache: AsyncRedisCache) -> None:
    builder = AsyncCacheBuilder.from_cache(a_redis_cache)
    cache = builder.add_middleware(AsyncMetricsMiddleware).build()

    print(type(cache))
    await cache.set("k1", "v1")
    assert await cache.get("missing", default=None) is None
    assert await cache.get("k1") == "v1"

    stats = cache.get_stats()
    assert stats["hits"] == 1 and stats["misses"] == 1


@pytest.mark.asyncio
async def test_async_builder_maps_sync_to_async_middleware(a_redis_cache: AsyncRedisCache) -> None:
    builder = AsyncCacheBuilder.from_cache(a_redis_cache)
    cache = builder.add_middleware(MetricsMiddleware).build()
    await cache.set("k2", "v2")
    assert await cache.get("missing2", default=None) is None
    assert await cache.get("k2") == "v2"
    stats = cache.get_stats()
    assert stats["hits"] == 1 and stats["misses"] == 1
