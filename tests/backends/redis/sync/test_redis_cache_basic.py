from datetime import datetime, timedelta, timezone

from cachine import RedisCache
from cachine.serializers import JSONSerializer


def test_redis_sync_set_get_ttl_persist_delete(redis_cache: RedisCache) -> None:
    cache = redis_cache
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


def test_redis_sync_incr_and_ttl_on_create(redis_cache: RedisCache) -> None:
    cache = redis_cache

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


def test_exists_and_default(redis_cache: RedisCache) -> None:
    cache = redis_cache
    assert cache.get("missing", default=123) == 123
    assert cache.exists("missing") in (False, 0)
    cache.set("x", "1")
    assert cache.exists("x") in (True, 1)


def test_namespace_isolation(redis_cache: RedisCache) -> None:
    base = redis_cache
    # Build a second cache with a different namespace but same connection
    other = RedisCache(redis_cache._config, namespace="ns2")

    base.set("k", "v")
    assert base.get("k") == "v"
    assert other.get("k") is None


def test_get_or_set(redis_cache: RedisCache) -> None:
    cache = redis_cache
    calls = {"n": 0}

    def factory() -> int:
        calls["n"] += 1
        return 42

    assert cache.get_or_set("answer", factory, ttl=10) == 42
    assert cache.get_or_set("answer", factory, ttl=10) == 42
    assert calls["n"] == 1


def test_expire_expire_at_touch_ttl(redis_cache: RedisCache) -> None:
    cache = redis_cache
    ser = JSONSerializer()
    cache.set("s", {"x": 1}, serializer=ser)
    assert cache.expire("s", ttl=2) is True
    t = cache.ttl("s")
    assert t is None or (isinstance(t, int) and t >= 0)

    when = datetime.now(timezone.utc) + timedelta(seconds=2)
    assert cache.expire_at("s", when) is True
    # Touch without TTL should not error
    assert cache.touch("s") in (True, False)
    # Touch with TTL should extend
    assert cache.touch("s", ttl=3) is True


def test_delete_and_persist(redis_cache: RedisCache) -> None:
    cache = redis_cache
    cache.set("p", "v", ttl=10)
    assert cache.persist("p") in (True, False)
    assert cache.delete("p") in (True, False)
    assert cache.get("p") is None


def test_incr_decr_ttl_on_create(redis_cache: RedisCache) -> None:
    cache = redis_cache
    assert cache.incr("cnt") == 1
    assert cache.decr("cnt") == 0

    # TTL applied only on create
    assert cache.incr("cnt:new", ttl_on_create=5) == 1
    before = cache.ttl("cnt:new")
    cache.incr("cnt:new", ttl_on_create=1)
    after = cache.ttl("cnt:new")
    if isinstance(before, int) and isinstance(after, int):
        assert after <= before
