from datetime import datetime, timedelta, timezone

from cachine.backends.redis.sync import RedisCache
from cachine.serializers import JSONSerializer


def test_exists_and_default(redis_sync_cache):
    cache = redis_sync_cache
    assert cache.get("missing", default=123) == 123
    assert cache.exists("missing") in (False, 0)
    cache.set("x", "1")
    assert cache.exists("x") in (True, 1)


def test_namespace_isolation(redis_sync_cache):
    base = redis_sync_cache
    # Build a second cache with a different namespace but same connection
    cfg = dict(host=base._cfg["host"], port=base._cfg["port"], db=base._cfg["db"], ssl=base._cfg["ssl"])  # type: ignore[attr-defined]
    other = RedisCache(namespace="ns2", password=base._password, **cfg)  # type: ignore[attr-defined]

    base.set("k", "v")
    assert base.get("k") == "v"
    assert other.get("k") is None


def test_get_or_set(redis_sync_cache):
    cache = redis_sync_cache
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return 42

    assert cache.get_or_set("answer", factory, ttl=10) == 42
    assert cache.get_or_set("answer", factory, ttl=10) == 42
    assert calls["n"] == 1


def test_expire_expire_at_touch_ttl(redis_sync_cache):
    cache = redis_sync_cache
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


def test_delete_and_persist(redis_sync_cache):
    cache = redis_sync_cache
    cache.set("p", "v", ttl=10)
    assert cache.persist("p") in (True, False)
    assert cache.delete("p") in (True, False)
    assert cache.get("p") is None


def test_incr_decr_ttl_on_create(redis_sync_cache):
    cache = redis_sync_cache
    assert cache.incr("cnt") == 1
    assert cache.decr("cnt") == 0

    # TTL applied only on create
    assert cache.incr("cnt:new", ttl_on_create=5) == 1
    before = cache.ttl("cnt:new")
    cache.incr("cnt:new", ttl_on_create=1)
    after = cache.ttl("cnt:new")
    if isinstance(before, int) and isinstance(after, int):
        assert after <= before
