from __future__ import annotations

import pytest

from cachine import AsyncRedisCache
from cachine.middleware import AsyncMetricsMiddleware


@pytest.mark.asyncio
async def test_metrics_async_hits_and_misses(a_redis_cache: AsyncRedisCache) -> None:
    base = a_redis_cache
    mw = AsyncMetricsMiddleware(base)

    # Miss path
    assert await mw.get("k1", default="d1") == "d1"

    # Hit path
    await mw.set("k1", "v1")
    assert await mw.get("k1") == "v1"

    stats = mw.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert 0.0 <= stats["hit_rate"] <= 1.0
    assert stats["errors"] == 0
    assert stats["avg_latency_ms"] >= 0.0
