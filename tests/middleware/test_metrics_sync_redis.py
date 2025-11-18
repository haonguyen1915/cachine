from __future__ import annotations

from cachine import RedisCache
from cachine.middleware import MetricsMiddleware


def test_metrics_sync_with_redis(redis_cache: RedisCache) -> None:
    mw = MetricsMiddleware(redis_cache)

    assert mw.get("k1", default="d1") == "d1"
    mw.set("k1", "v1")
    assert mw.get("k1") == "v1"

    stats = mw.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert 0.0 <= stats["hit_rate"] <= 1.0
    assert stats["errors"] == 0
    assert stats["avg_latency_ms"] >= 0.0

