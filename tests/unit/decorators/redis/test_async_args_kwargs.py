import pytest

from cachine import cached


@pytest.mark.asyncio
async def test_async_args_only(redis_async_cache):
    cache = redis_async_cache
    calls = {"n": 0}

    @cached(cache, ttl=60)
    async def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert await add(1, 2) == 3
    assert await add(1, 2) == 3
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_async_kwargs_only(redis_async_cache):
    cache = redis_async_cache
    calls = {"n": 0}

    @cached(cache, ttl=60)
    async def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert await add(a=1, b=2) == 3
    assert await add(a=1, b=2) == 3
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_async_args_kwargs_equivalence_with_custom_keybuilder(redis_async_cache):
    cache = redis_async_cache
    calls = {"n": 0}

    def kb(*args, **kwargs):
        if args and hasattr(args[0], "full_name"):
            args = args[1:]
        if len(args) >= 2:
            a, b = args[0], args[1]
        else:
            a = kwargs.get("a")
            b = kwargs.get("b")
        return f"sum:{a}:{b}"

    @cached(cache, ttl=60, key_builder=kb)
    async def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert await add(1, 2) == 3
    assert await add(a=1, b=2) == 3
    assert await add(b=2, a=1) == 3
    assert calls["n"] == 1

