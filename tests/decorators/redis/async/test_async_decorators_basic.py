from typing import Any

import pytest

from cachine import AsyncRedisCache, cached


@pytest.mark.asyncio
async def test_async_decorator_basic_cache(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    calls = {"n": 0}

    @cached(cache, ttl=60)
    async def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert await add(1, 2) == 3
    assert await add(1, 2) == 3
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_async_decorator_stale_ttl_refresh(a_redis_cache: AsyncRedisCache) -> None:
    import asyncio

    cache = a_redis_cache
    calls = {"n": 0}

    @cached(cache, ttl=1, stale_ttl=5, singleflight=True)
    async def expensive() -> int:
        calls["n"] += 1
        return calls["n"]

    assert await expensive() == 1
    await asyncio.sleep(1.2)
    v = await expensive()  # stale
    assert v == 1
    # Wait up to 2s for background refresh
    deadline = asyncio.get_event_loop().time() + 2.0
    updated = False
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.05)
        if await expensive() == 2:
            updated = True
            break
    assert updated, "Background refresh did not complete in time"
