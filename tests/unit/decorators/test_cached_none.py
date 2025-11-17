from __future__ import annotations

import asyncio

from cachine.decorators.cached import cached


def test_sync_cached_none_passes_through() -> None:
    calls = {"n": 0}

    @cached(cache=None, ttl=1)
    def compute(x: int) -> int:
        calls["n"] += 1
        return x * 2

    assert compute(2) == 4
    assert compute(2) == 4
    assert calls["n"] == 2  # no caching, function executed twice


def test_async_cached_none_passes_through() -> None:
    calls = {"n": 0}

    @cached(cache=None, ttl=1)
    async def acompute(x: int) -> int:
        calls["n"] += 1
        return x * 2

    async def run() -> None:
        assert await acompute(3) == 6
        assert await acompute(3) == 6

    asyncio.run(run())
    assert calls["n"] == 2  # no caching, coroutine executed twice
