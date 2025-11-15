from __future__ import annotations

import os
import time

import pytest

from cachine import InMemoryCache
from cachine.decorators import cached


def _truthy(v: str | None) -> bool:
    return (v or "").lower() in {"1", "true", "yes", "on"}


perf_enabled = pytest.mark.skipif(not _truthy(os.getenv("RUN_PERF_TESTS")), reason="RUN_PERF_TESTS not enabled")


@perf_enabled
def test_inmemory_set_get_throughput() -> None:
    cache = InMemoryCache()
    N = int(os.getenv("PERF_N", "5000"))

    # Populate
    for i in range(N):
        cache.set(f"k{i}", i)

    # Measure get throughput and correctness
    start = time.perf_counter()
    for i in range(N):
        assert cache.get(f"k{i}") == i
    elapsed = time.perf_counter() - start
    ops = N / elapsed if elapsed > 0 else float("inf")
    print(f"InMemory get throughput: {ops:,.0f} ops/s ({N} gets in {elapsed:.4f}s)")


@perf_enabled
def test_cached_decorator_hit_latency_improvement() -> None:
    cache = InMemoryCache()

    # A deliberately slow function
    def slow(x: int) -> int:
        time.sleep(0.002)  # 2ms
        return x * 2

    # Baseline
    N = int(os.getenv("PERF_N", "300"))
    t0 = time.perf_counter()
    for _ in range(N):
        slow(1)
    baseline_avg = (time.perf_counter() - t0) / N

    # Cached variant
    @cached(cache=cache, ttl=60)
    def cached_slow(x: int) -> int:
        return slow(x)

    # Warm up the cache (establish a hit)
    assert cached_slow(1) == 2

    t1 = time.perf_counter()
    for _ in range(N):
        assert cached_slow(1) == 2
    cached_avg = (time.perf_counter() - t1) / N

    print(f"baseline avg: {baseline_avg * 1e3:.3f} ms, cached avg: {cached_avg * 1e3:.3f} ms")

    # Cached hits should be significantly faster than computing slow()
    assert cached_avg < baseline_avg * 0.5


@perf_enabled
def test_inmemory_eviction_set_throughput() -> None:
    # Exercise eviction under pressure to catch pathological slowdowns
    max_size = 2000
    over = max_size + int(max_size * 0.25)
    cache = InMemoryCache(max_size=max_size)

    start = time.perf_counter()
    for i in range(over):
        cache.set(f"k{i}", i)
    elapsed = time.perf_counter() - start
    print(f"InMemory set with eviction: {over} sets in {elapsed:.4f}s (max_size={max_size})")
    # Ensure size cap is respected indirectly by existence checks
    survivors = sum(1 for i in range(over) if cache.get(f"k{i}") is not None)
    assert survivors <= max_size
