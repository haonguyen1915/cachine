from typing import Any

import pytest

from cachine import cached


@pytest.mark.asyncio
async def test_async_key_builder_receives_context(redis_async_cache: Any) -> None:
    cache = redis_async_cache
    captured = {}

    def kb(ctx: Any, a: int, b: int) -> str:
        captured["module"] = getattr(ctx, "module", None)
        captured["qualname"] = getattr(ctx, "qualname", None)
        captured["full_name"] = getattr(ctx, "full_name", None)
        captured["version"] = getattr(ctx, "version", None)
        return f"sum:{a}:{b}:{ctx.qualname}"

    calls = {"n": 0}

    @cached(cache, ttl=60, key_builder=kb, version="rv_async")
    async def add(a: int, b: int) -> int:
        calls["n"] += 1
        return a + b

    assert await add(1, 2) == 3
    assert await add(1, 2) == 3
    assert calls["n"] == 1

    assert captured["version"] == "rv_async"
    assert isinstance(captured["module"], str)
    assert isinstance(captured["qualname"], str) and "add" in captured["qualname"]
    assert isinstance(captured["full_name"], str)
