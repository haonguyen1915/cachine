from __future__ import annotations

import os
import time
from typing import Any

import pytest

from cachine import cached

try:
    import pytest_asyncio  # noqa: F401

    HAS_ASYNCIO = True
except Exception:  # pragma: no cover
    HAS_ASYNCIO = False


def _truthy(v: str | None) -> bool:
    return (v or "").lower() in {"1", "true", "yes", "on"}


perf_enabled = pytest.mark.skipif(not _truthy(os.getenv("RUN_PERF_TESTS")), reason="RUN_PERF_TESTS not enabled")


@perf_enabled
def test_redis_sync_set_get_throughput(redis_sync_cache: Any) -> None:
    cache = redis_sync_cache
    N = int(os.getenv("PERF_N_REDIS", os.getenv("PERF_N", "2000")))

    # Populate
    for i in range(N):
        cache.set(f"k{i}", i)

    # Measure gets
    start = time.perf_counter()
    for i in range(N):
        assert cache.get(f"k{i}") == i
    elapsed = time.perf_counter() - start
    ops = N / elapsed if elapsed > 0 else float("inf")
    print(f"Redis sync get throughput: {ops:,.0f} ops/s ({N} gets in {elapsed:.4f}s)")


@perf_enabled
def test_redis_sync_cached_hit_latency_improvement(redis_sync_cache: Any) -> None:
    cache = redis_sync_cache

    def slow(x: int) -> int:
        time.sleep(0.002)
        return x * 2

    N = int(os.getenv("PERF_N_REDIS", os.getenv("PERF_N", "200")))

    t0 = time.perf_counter()
    for _ in range(N):
        slow(1)
    baseline_avg = (time.perf_counter() - t0) / N

    @cached(cache=cache, ttl=60)
    def cached_slow(x: int) -> int:
        return slow(x)

    assert cached_slow(1) == 2  # warm

    t1 = time.perf_counter()
    for _ in range(N):
        assert cached_slow(1) == 2
    cached_avg = (time.perf_counter() - t1) / N

    print(f"Redis cached avg: {cached_avg * 1e3:.3f} ms vs baseline {baseline_avg * 1e3:.3f} ms")
    assert cached_avg < baseline_avg * 0.5


@perf_enabled
@pytest.mark.skipif(not HAS_ASYNCIO, reason="pytest-asyncio not installed")
@pytest.mark.asyncio
async def test_redis_async_set_get_throughput(redis_async_cache: Any) -> None:
    cache = redis_async_cache
    N = int(os.getenv("PERF_N_REDIS", os.getenv("PERF_N", "1500")))

    for i in range(N):
        await cache.set(f"k{i}", i)

    start = time.perf_counter()
    for i in range(N):
        assert await cache.get(f"k{i}") == i
    elapsed = time.perf_counter() - start
    ops = N / elapsed if elapsed > 0 else float("inf")
    print(f"Redis async get throughput: {ops:,.0f} ops/s ({N} gets in {elapsed:.4f}s)")


@perf_enabled
@pytest.mark.skipif(not HAS_ASYNCIO, reason="pytest-asyncio not installed")
@pytest.mark.asyncio
async def test_redis_async_cached_hit_latency_improvement(redis_async_cache: Any) -> None:
    cache = redis_async_cache

    async def slow(x: int) -> int:
        # Simulate async workload
        import asyncio

        await asyncio.sleep(0.002)
        return x * 2

    N = int(os.getenv("PERF_N_REDIS", os.getenv("PERF_N", "200")))

    t0 = time.perf_counter()
    for _ in range(N):
        await slow(1)
    baseline_avg = (time.perf_counter() - t0) / N

    @cached(cache=cache, ttl=60)
    async def cached_slow(x: int) -> int:
        return await slow(x)

    assert await cached_slow(1) == 2

    t1 = time.perf_counter()
    for _ in range(N):
        assert await cached_slow(1) == 2
    cached_avg = (time.perf_counter() - t1) / N

    print(f"Redis async cached avg: {cached_avg * 1e3:.3f} ms vs baseline {baseline_avg * 1e3:.3f} ms")
    assert cached_avg < baseline_avg * 0.5
