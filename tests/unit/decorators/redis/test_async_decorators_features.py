from typing import Any

import pytest

from cachine import cached


@pytest.mark.asyncio
async def test_async_decorator_condition_and_cache_none(a_redis_cache: Any) -> None:
    cache = a_redis_cache
    calls = {"n": 0}

    @cached(cache, ttl=60, condition=lambda r: r is not None, cache_none=False)
    async def maybe(flag: bool) -> int | None:
        calls["n"] += 1
        return 1 if flag else None

    assert await maybe(True) == 1
    assert await maybe(True) == 1
    # None results are not cached
    assert await maybe(False) is None
    assert await maybe(False) is None
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_async_decorator_tags_and_invalidation(a_redis_cache: Any) -> None:
    cache = a_redis_cache

    @cached(
        cache,
        ttl=60,
        tags=lambda uid: ["users", f"user:{uid}"],
        tags_from_result=lambda u: [f"role:{u['role']}"] if u else [],
    )
    async def get_user(uid: int) -> dict[str, Any]:
        return {"id": uid, "role": "admin" if uid == 1 else "member"}

    assert await get_user(1) == {"id": 1, "role": "admin"}
    assert await get_user(1) == {"id": 1, "role": "admin"}
    # Invalidate by tag
    removed = await cache.invalidate_tags(["users"])
    assert removed >= 1
    # Recompute after invalidation
    assert await get_user(1) == {"id": 1, "role": "admin"}
