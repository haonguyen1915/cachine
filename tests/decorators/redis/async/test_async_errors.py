import asyncio
from typing import Any

import pytest

from cachine import AsyncRedisCache, cached


@pytest.mark.asyncio
async def test_exception_not_cached_and_propagates_async(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    state = {"fail": True, "calls": 0}

    @cached(cache, ttl=60)
    async def compute(x: int) -> int:
        state["calls"] += 1
        if state["fail"]:
            raise ValueError("boom")
        return x * 2

    with pytest.raises(ValueError):
        await compute(2)
    assert state["calls"] == 1

    state["fail"] = False
    assert await compute(2) == 4
    assert await compute(2) == 4
    assert state["calls"] == 2


@pytest.mark.asyncio
async def test_stale_ttl_refresh_error_async(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    state = {"fail": False, "n": 0}

    @cached(cache, ttl=1, stale_ttl=3, singleflight=True)
    async def expensive() -> int:
        state["n"] += 1
        if state["fail"]:
            raise RuntimeError("refresh failed")
        return state["n"]

    assert await expensive() == 1
    await asyncio.sleep(1.2)
    state["fail"] = True
    assert await expensive() == 1  # stale
    state["fail"] = False
    _ = await expensive()  # stale, triggers refresh
    # Wait up to 2s for background refresh to complete (timing-sensitive on CI)
    deadline = asyncio.get_event_loop().time() + 2.0
    updated = False
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.05)
        if await expensive() == 3:
            updated = True
            break
    assert updated, "Background refresh did not complete in time"
