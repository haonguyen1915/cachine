from typing import Any

import pytest

from cachine import AsyncRedisCache, cached


@pytest.mark.asyncio
async def test_async_instance_method_caching(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache

    class Service:
        def __init__(self, tenant: str) -> None:
            self.tenant = tenant
            self.calls = 0

        @cached(cache, ttl=60, key_builder=lambda ctx, self, a, b: f"{self.tenant}:{a}:{b}:{ctx.qualname}")
        async def add(self, a: int, b: int) -> int:
            self.calls += 1
            return a + b

    s = Service("t1")
    assert await s.add(1, 2) == 3
    assert await s.add(1, 2) == 3
    assert s.calls == 1


@pytest.mark.asyncio
async def test_async_staticmethod_caching(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache

    class Util:
        calls = 0

        @staticmethod
        @cached(cache, ttl=60)
        async def mul(a: int, b: int) -> int:
            Util.calls += 1
            return a * b

    assert await Util.mul(2, 3) == 6
    assert await Util.mul(2, 3) == 6
    assert Util.calls == 1


@pytest.mark.asyncio
async def test_async_classmethod_caching(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache

    class Counter:
        calls = 0

        @classmethod
        @cached(cache, ttl=60)
        async def inc(cls, x: int) -> int:
            cls.calls += 1
            return x + 1

    assert await Counter.inc(5) == 6
    assert await Counter.inc(5) == 6
    assert Counter.calls == 1
