from __future__ import annotations

import pytest

from cachine import cached


@pytest.mark.usefixtures("redis_sync_cache")
def test_sync_template_key_builder_redis(redis_sync_cache):  # type: ignore[no-redef]
    cache = redis_sync_cache

    @cached(cache=cache, ttl=30, key_builder="{ctx.full_name}:{uid}", version="rv1")
    def get_user(uid: int) -> dict:
        return {"id": uid}

    u = get_user(5)
    assert u["id"] == 5
    expected_key = f"{get_user.__module__}.{get_user.__qualname__}:5|v:rv1"
    assert cache.exists(expected_key)
