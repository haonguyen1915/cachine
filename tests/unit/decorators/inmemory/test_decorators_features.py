import time
from threading import Barrier, Thread

from cachine import InMemoryCache, cached


def test_condition_and_cache_none():
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache, ttl=60, condition=lambda r: r is not None, cache_none=False)
    def maybe_get(flag: bool):
        calls["n"] += 1
        return 1 if flag else None

    assert maybe_get(True) == 1
    assert maybe_get(True) == 1
    assert calls["n"] == 1
    # None result should not be cached
    assert maybe_get(False) is None
    assert maybe_get(False) is None
    assert calls["n"] == 3


def test_stale_ttl_background_refresh():
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache, ttl=1, stale_ttl=5, singleflight=True)
    def expensive():
        calls["n"] += 1
        return calls["n"]

    # First call computes value 1
    assert expensive() == 1
    # Wait until fresh TTL expires but within stale window
    time.sleep(1.2)
    # Should return stale (1) and trigger background refresh to set value 2
    v = expensive()
    assert v == 1
    # Give background refresh time to run
    time.sleep(0.1)
    # Now value should be updated to 2 (fresh)
    assert expensive() == 2


def test_singleflight_concurrent_miss():
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(cache, ttl=60, singleflight=True)
    def slow_add(a, b):
        calls["n"] += 1
        time.sleep(0.05)
        return a + b

    barrier = Barrier(3)
    results = {}

    def worker(i):
        barrier.wait()
        results[i] = slow_add(1, 2)

    t1 = Thread(target=worker, args=(1,))
    t2 = Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    barrier.wait()
    t1.join()
    t2.join()

    assert results[1] == 3 and results[2] == 3
    assert calls["n"] == 1


def test_tags_and_invalidation():
    cache = InMemoryCache()

    @cached(cache, ttl=60, tags=["users"], tags_from_result=lambda u: [f"user:{u['id']}"])
    def get_user(uid: int):
        return {"id": uid}

    u = get_user(10)
    assert u == {"id": 10}
    # Invalidate by tag
    assert cache.invalidate_tags(["users"]) >= 1
    # Should recompute after invalidation
    u2 = get_user(10)
    assert u2 == {"id": 10}
