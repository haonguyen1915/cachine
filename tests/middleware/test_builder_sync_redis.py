from __future__ import annotations

from cachine import CacheBuilder, RedisCache
from cachine.middleware import MetricsMiddleware


def test_sync_builder_with_redis(redis_cache: RedisCache) -> None:
    builder = CacheBuilder.from_cache(redis_cache)
    cache = builder.add_middleware(MetricsMiddleware).build()

    # Miss returns default
    assert cache.get("k1", default="d1") == "d1"
    cache.set("k1", "v1")
    assert cache.get("k1") == "v1"

    stats = cache.get_stats()
    assert stats["hits"] == 1 and stats["misses"] == 1
