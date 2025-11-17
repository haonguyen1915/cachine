from __future__ import annotations

from typing import Any

import pytest

from cachine import AsyncRedisCache, cached
from cachine.utils.key_builder import template_key_builder


@pytest.mark.asyncio
async def test_async_template_key_builder_redis(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    kb = template_key_builder("{ctx.full_name}:pid={pid}")

    @cached(cache=cache, ttl=30, key_builder=kb, version="rav1")
    async def get_post(pid: int) -> dict[str, int]:
        return {"id": pid}

    p = await get_post(11)
    assert p["id"] == 11
    expected_key = f"{get_post.__module__}.{get_post.__qualname__}:pid=11|v:rav1"
    assert await cache.exists(expected_key)
