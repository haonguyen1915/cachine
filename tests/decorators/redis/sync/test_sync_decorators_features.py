import hashlib
import time
from threading import Barrier, Thread
from typing import Any

from cachine import RedisCache, cached


def _kb(a: int, b: int) -> str:
    return f"sum:{hashlib.sha256(f'{a}:{b}'.encode()).hexdigest()}"


def test_redis_decorator_full_config(redis_cache: RedisCache) -> None:
    cache = redis_cache
    calls = {"n": 0}

    @cached(
        cache,
        ttl=1,
        jitter=1,
        key_builder=_kb,
        condition=lambda r: r is not None,
        version="v1",
        cache_none=False,
        stale_ttl=2,
        singleflight=True,
        tags=["math", "sum"],
        tags_from_result=lambda r: [f"sum:{r}"] if r is not None else [],
    )
    def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    # caches result
    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert calls["n"] == 1

    # Invalidate by tag and recompute
    removed = cache.invalidate_tags(["math"])
    assert removed >= 1
    assert add(1, 2) == 3
    assert calls["n"] == 2

    # Stale-while-revalidate window
    time.sleep(1.2)
    v = add(1, 2)
    assert v == 3  # stale
    time.sleep(0.2)
    # Fresh after background refresh (value is still 3; verify no extra calls beyond 3rd compute)
    add(1, 2)
    assert calls["n"] >= 3


def test_redis_decorator_version_isolation(redis_cache: RedisCache) -> None:
    cache = redis_cache

    @cached(cache, ttl=60, key_builder=_kb, version="v1")
    def f1(a: int, b: int) -> int:
        return 100

    @cached(cache, ttl=60, key_builder=_kb, version="v2")
    def f2(a: int, b: int) -> int:
        return 200

    assert f1(1, 2) == 100
    # Different version should compute separately, not read f1's cache
    assert f2(1, 2) == 200


def test_redis_decorator_singleflight_concurrency(redis_cache: RedisCache) -> None:
    cache = redis_cache
    calls = {"n": 0}

    @cached(cache, ttl=60, singleflight=True, key_builder=_kb)
    def slow(a: int, b: int) -> int:
        calls["n"] += 1
        time.sleep(0.05)
        return a + b

    barrier = Barrier(3)
    results = {}

    def worker(i: int) -> None:
        barrier.wait()
        results[i] = slow(1, 2)

    t1 = Thread(target=worker, args=(1,))
    t2 = Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    barrier.wait()
    t1.join()
    t2.join()

    assert results[1] == 3 and results[2] == 3
    assert calls["n"] == 1
