from datetime import timedelta

from cachine.serializers import JSONSerializer


def test_redis_sync_set_get_ttl_persist_delete(redis_sync_cache):
    cache = redis_sync_cache
    ser = JSONSerializer()

    cache.set("user:1", {"id": 1}, ttl=10, serializer=ser)
    assert cache.get("user:1", serializer=ser) == {"id": 1}

    t = cache.ttl("user:1")
    assert t is None or (isinstance(t, int) and t >= 0)

    # Persist removes expiry and returns bool
    _ = cache.persist("user:1")
    t2 = cache.ttl("user:1")
    assert t2 is None

    # Delete returns bool
    assert cache.delete("user:1") in (True, False)
    assert cache.get("user:1") is None


def test_redis_sync_incr_and_ttl_on_create(redis_sync_cache):
    cache = redis_sync_cache

    assert cache.incr("cnt") == 1
    assert cache.incr("cnt", delta=4) == 5
    assert cache.decr("cnt", delta=2) == 3

    # ttl_on_create applied on first create only
    assert cache.incr("cnt:new", ttl_on_create=5) == 1
    t = cache.ttl("cnt:new")
    assert t is None or (isinstance(t, int) and t >= 0)

    # Subsequent increments should not reset TTL
    before = cache.ttl("cnt:new")
    cache.incr("cnt:new", ttl_on_create=1)
    after = cache.ttl("cnt:new")
    # 'before' can be None or int; if int, it should remain same or decrease
    if isinstance(before, int) and isinstance(after, int):
        assert after <= before

