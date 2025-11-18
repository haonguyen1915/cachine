from datetime import datetime, timedelta, timezone

from cachine import InMemoryCache
from cachine.strategies import TagBasedInvalidation


def test_get_default_and_exists() -> None:
    cache = InMemoryCache()
    assert cache.get("missing") is None
    assert cache.get("missing", default=123) == 123
    assert cache.exists("missing") is False


def test_set_get_delete_clear_namespace() -> None:
    cache = InMemoryCache(namespace="ns")
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert cache.delete("a") is True
    assert cache.get("a") is None

    cache.set("b", 2)
    cache.clear()
    assert cache.get("b") is None


def test_ttl_expire_persist_touch() -> None:
    cache = InMemoryCache()
    cache.set("k", "v", ttl=10)
    t = cache.ttl("k")
    assert t is None or isinstance(t, int)

    # persist removes ttl
    assert cache.persist("k") is True
    assert cache.ttl("k") is None

    # expire to delete when ttl <= 0
    cache.set("x", 1)
    assert cache.expire("x", ttl=0) is True
    assert cache.exists("x") is False

    # expire_at in past deletes
    cache.set("y", 2)
    assert cache.expire_at("y", datetime.now(timezone.utc) - timedelta(seconds=1)) is True
    assert cache.exists("y") is False

    # touch with ttl extends
    cache.set("z", 3)
    assert cache.touch("z", ttl=5) is True
    assert isinstance(cache.ttl("z"), int)


def test_get_or_set() -> None:
    cache = InMemoryCache()
    called = {"n": 0}

    def factory() -> int:
        called["n"] += 1
        return 42

    assert cache.get_or_set("answer", factory, ttl=60) == 42
    assert cache.get_or_set("answer", factory, ttl=60) == 42
    assert called["n"] == 1


def test_counters_incr_decr_and_ttl_on_create() -> None:
    cache = InMemoryCache()
    assert cache.incr("cnt") == 1
    assert cache.incr("cnt", delta=5) == 6
    assert cache.decr("cnt", delta=2) == 4

    # ttl_on_create applies only when first created
    assert cache.incr("newcnt", ttl_on_create=30) == 1
    t = cache.ttl("newcnt")
    assert isinstance(t, int) and 0 <= t <= 30
    # subsequent increments preserve TTL (do not reset)
    before = cache.ttl("newcnt")
    cache.incr("newcnt", delta=1, ttl_on_create=10)
    after = cache.ttl("newcnt")
    assert before == after


def test_tags_invalidation_direct_and_strategy() -> None:
    cache = InMemoryCache()
    cache.set("user:1", {"id": 1})
    # Attach tags via internal method (used by decorator/strategy)
    cache.add_tags("user:1", ["users", "user:1"])
    assert cache.invalidate_tags(["users"]) == 1
    assert cache.get("user:1") is None

    # Strategy wrapper also attaches tags when setting
    inv = TagBasedInvalidation(cache)

    import asyncio

    asyncio.get_event_loop().run_until_complete(inv.set("user:2", {"id": 2}, ttl=60, tags=["users", "user:2"]))
    assert cache.get("user:2") == {"id": 2}
    asyncio.get_event_loop().run_until_complete(inv.invalidate_tag("users"))
    assert cache.get("user:2") is None


def test_context_manager_and_ping() -> None:
    with InMemoryCache() as cache:
        cache.set("k", "v")
        assert cache.get("k") == "v"
        status = cache.ping()
        assert status["healthy"] is True
        assert cache.ping_ok() is True
