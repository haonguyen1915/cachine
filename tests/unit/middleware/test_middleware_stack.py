import pprint

from cachine import InMemoryCache
from cachine.middleware import CompressionMiddleware, EncryptionMiddleware, MetricsMiddleware


def test_middleware_stack_inmemory_basic():
    base = InMemoryCache(namespace="mw")
    cache = CompressionMiddleware(base, algorithm="gzip", min_size=0)
    cache = EncryptionMiddleware(cache, key="secret", key_id="v1")
    cache = MetricsMiddleware(cache)

    data = {"a": 1, "b": [2, 3]}
    cache.set("k", data, ttl=5)
    assert cache.get("k") == data

    # exercise ttl funcs through the stack
    t = cache.ttl("k")
    assert t is None or (isinstance(t, int) and t >= 0)
    assert cache.persist("k") in (True, False)
    assert cache.delete("k") in (True, False)

    # metrics available
    stats = cache.get_stats()
    assert set(["hits", "misses"]).issubset(stats.keys())
    pprint.pprint(stats)


def test_middleware_forwards_invalidate_tags():
    base = InMemoryCache(namespace="mw2")
    cache = MetricsMiddleware(base)

    cache.set("user:1", {"id": 1})
    # add tags via backend helper and use invalidate through middleware
    base.add_tags("user:1", ["users", "user:1"])  # type: ignore[attr-defined]
    stats = cache.get_stats()
    pprint.pprint(stats)
    removed = cache.invalidate_tags(["users"])  # forwarded
    assert removed >= 1
    assert cache.get("user:1") is None
