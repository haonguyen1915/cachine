from typing import Any

import pytest

from cachine import cached


@pytest.mark.asyncio
async def test_async_tags_full_invalidation(redis_async_cache: Any) -> None:
    cache = redis_async_cache
    calls = {"n": 0}

    @cached(
        cache,
        ttl=60,
        stale_ttl=30,
        tags=lambda uid: ["users", f"user:{uid}"],
        tags_from_result=lambda u: [f"role:{u['role']}"] if u else [],
    )
    async def get_user(uid: int) -> dict[str, Any]:
        calls["n"] += 1
        return {"id": uid, "role": "admin" if uid == 1 else "member"}

    # Populate and cache two users
    assert await get_user(1) == {"id": 1, "role": "admin"}
    assert await get_user(2) == {"id": 2, "role": "member"}
    assert await get_user(1) == {"id": 1, "role": "admin"}
    assert await get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 2

    # Invalidate by role tag
    removed = await cache.invalidate_tags(["role:admin"])
    assert removed >= 1
    assert await get_user(1) == {"id": 1, "role": "admin"}
    assert await get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 3

    # Invalidate by users namespace and specific user tag
    removed = await cache.invalidate_tags(["users", "user:2"])
    assert removed >= 1
    assert await get_user(1) == {"id": 1, "role": "admin"}
    assert await get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 5
