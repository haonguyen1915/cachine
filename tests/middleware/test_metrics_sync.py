from __future__ import annotations

from cachine import InMemoryCache
from cachine.middleware import MetricsMiddleware


def test_metrics_sync_hits_and_misses() -> None:
    base = InMemoryCache()
    mw = MetricsMiddleware(base)

    # Miss path: nothing set yet
    assert mw.get("k1", default="d1") == "d1"

    # Set and then hit
    mw.set("k1", "v1")
    assert mw.get("k1") == "v1"

    stats = mw.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert 0.0 <= stats["hit_rate"] <= 1.0
    assert stats["errors"] == 0
    assert stats["avg_latency_ms"] >= 0.0
