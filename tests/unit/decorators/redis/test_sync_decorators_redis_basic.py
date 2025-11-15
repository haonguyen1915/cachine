import time
from threading import Barrier, Thread

from cachine import cached


def test_redis_cached_basic(redis_sync_cache):
    calls = {"n": 0}

    @cached(redis_sync_cache, ttl=30)
    def add(a, b):
        calls["n"] += 1
        return a + b

    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert calls["n"] == 1


def test_redis_singleflight(redis_sync_cache):
    calls = {"n": 0}

    @cached(redis_sync_cache, ttl=30, singleflight=True)
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


def test_redis_stale_ttl_refresh(redis_sync_cache):
    calls = {"n": 0}

    @cached(redis_sync_cache, ttl=1, stale_ttl=5, singleflight=True)
    def expensive():
        calls["n"] += 1
        return calls["n"]

    assert expensive() == 1
    time.sleep(1.2)
    v = expensive()
    assert v == 1
    time.sleep(0.1)
    assert expensive() == 2
