from __future__ import annotations

import pytest

from cachine import RedisCache
from cachine.decorators import cached


@pytest.mark.usefixtures("redis_cache")
def test_sync_template_key_builder_redis(redis_cache: RedisCache) -> None:
    cache = redis_cache

    @cached(cache=cache, ttl=30, key_builder="{ctx.full_name}:{uid}", version="rv1")
    def get_user(uid: int) -> dict[str, int]:
        return {"id": uid}

    u = get_user(5)
    assert u["id"] == 5
    expected_key = f"{get_user.__module__}.{get_user.__qualname__}:5|v:rv1"
    assert cache.exists(expected_key)
