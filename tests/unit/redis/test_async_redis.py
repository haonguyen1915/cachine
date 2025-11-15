import pytest


@pytest.mark.asyncio
async def test_async_redis_set_get_incr_ttl(redis_async_cache):
    cache = redis_async_cache

    # set/get
    await cache.set("k", {"a": 1}, ttl=5)
    assert await cache.get("k") == {"a": 1}

    # ttl and persist
    t = await cache.ttl("k")
    assert t is None or (isinstance(t, int) and t >= 0)
    _ = await cache.persist("k")
    assert await cache.ttl("k") is None

    # counters
    assert await cache.incr("cnt") == 1
    assert await cache.incr("cnt", delta=4) == 5
    assert await cache.decr("cnt", delta=2) == 3

    # ttl_on_create on new key
    assert await cache.incr("cnt:new", ttl_on_create=3) == 1
    t2 = await cache.ttl("cnt:new")
    assert t2 is None or (isinstance(t2, int) and t2 >= 0)

    # delete
    assert await cache.delete("k") in (True, False)
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_async_redis_tags_invalidation(redis_async_cache):
    cache = redis_async_cache

    await cache.set("user:1", {"id": 1, "role": "admin"}, ttl=60)
    # attach tags and invalidate
    await cache.add_tags("user:1", ["users", "user:1", "role:admin"])  # type: ignore[attr-defined]
    removed = await cache.invalidate_tags(["users"])  # type: ignore[attr-defined]
    assert removed >= 1
    assert await cache.get("user:1") is None

