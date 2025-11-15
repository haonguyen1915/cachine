from cachine import InMemoryCache
from cachine.middleware import MetricsMiddleware


def test_metrics_middleware_stats():
    cache = MetricsMiddleware(InMemoryCache())
    cache.set("k", "v")
    _ = cache.get("k")
    stats = cache.get_stats()
    assert "hit_rate" in stats

