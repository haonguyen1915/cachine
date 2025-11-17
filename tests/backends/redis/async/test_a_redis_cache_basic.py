from datetime import datetime, timedelta, timezone

import pytest

from cachine import AsyncRedisCache
from cachine.serializers import JSONSerializer


@pytest.mark.asyncio
async def test_async_redis_set_get_ttl_persist_delete(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    ser = JSONSerializer()

    await cache.set("user:1", {"id": 1}, ttl=10, serializer=ser)
    assert await cache.get("user:1", serializer=ser) == {"id": 1}

    t = await cache.ttl("user:1")
    assert t is None or (isinstance(t, int) and t >= 0)

    _ = await cache.persist("user:1")
    t2 = await cache.ttl("user:1")
    assert t2 is None

    assert await cache.delete("user:1") in (True, False)
    assert await cache.get("user:1") is None


@pytest.mark.asyncio
async def test_async_redis_incr_and_ttl_on_create(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache

    assert await cache.incr("cnt") == 1
    assert await cache.incr("cnt", delta=4) == 5
    assert await cache.decr("cnt", delta=2) == 3

    assert await cache.incr("cnt:new", ttl_on_create=5) == 1
    t = await cache.ttl("cnt:new")
    assert t is None or (isinstance(t, int) and t >= 0)

    before = await cache.ttl("cnt:new")
    await cache.incr("cnt:new", ttl_on_create=1)
    after = await cache.ttl("cnt:new")
    if isinstance(before, int) and isinstance(after, int):
        assert after <= before


@pytest.mark.asyncio
async def test_async_exists_and_default(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    assert await cache.get("missing", default=123) == 123
    assert await cache.exists("missing") in (False, 0)
    await cache.set("x", "1")
    assert await cache.exists("x") in (True, 1)


@pytest.mark.asyncio
async def test_async_namespace_isolation(a_redis_cache: AsyncRedisCache) -> None:
    base = a_redis_cache
    other = AsyncRedisCache(base._config, namespace="ns2")  # type: ignore[attr-defined]

    await base.set("k", "v")
    assert await base.get("k") == "v"
    assert await other.get("k") is None


@pytest.mark.asyncio
async def test_async_get_or_set(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    calls = {"n": 0}

    async def factory() -> int:
        calls["n"] += 1
        return 42

    assert await cache.get_or_set("answer", factory, ttl=10) == 42
    assert await cache.get_or_set("answer", factory, ttl=10) == 42
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_async_expire_expire_at_touch_ttl(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    ser = JSONSerializer()
    await cache.set("s", {"x": 1}, serializer=ser)
    assert await cache.expire("s", ttl=2) is True
    t = await cache.ttl("s")
    assert t is None or (isinstance(t, int) and t >= 0)

    when = datetime.now(timezone.utc) + timedelta(seconds=2)
    assert await cache.expire_at("s", when) is True
    assert await cache.touch("s") in (True, False)
    assert await cache.touch("s", ttl=3) is True


@pytest.mark.asyncio
async def test_async_delete_and_persist(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    await cache.set("p", "v", ttl=10)
    assert await cache.persist("p") in (True, False)
    assert await cache.delete("p") in (True, False)
    assert await cache.get("p") is None


@pytest.mark.asyncio
async def test_async_redis_tags_invalidation(a_redis_cache: AsyncRedisCache) -> None:
    cache = a_redis_cache
    await cache.set("user:1", {"id": 1, "role": "admin"}, ttl=60)
    await cache.add_tags("user:1", ["users", "user:1", "role:admin"])
    removed = await cache.invalidate_tags(["users"])
    assert removed >= 1
    assert await cache.get("user:1") is None
