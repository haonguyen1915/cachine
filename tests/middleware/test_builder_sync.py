from __future__ import annotations

from cachine import CacheBuilder, InMemoryCache
from cachine.middleware import MetricsMiddleware


def test_sync_builder_from_cache_and_middleware() -> None:
    builder = CacheBuilder.from_cache(InMemoryCache())
    cache = builder.add_middleware(MetricsMiddleware).build()

    # Miss path returns default and increments metrics
    assert cache.get("k1", default="d1") == "d1"
    cache.set("k1", "v1")
    assert cache.get("k1") == "v1"

    # Outer middleware is MetricsMiddleware with get_stats
    stats = cache.get_stats()
    assert stats["hits"] == 1 and stats["misses"] == 1

