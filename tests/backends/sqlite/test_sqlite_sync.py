from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cachine import SQLiteCache
from cachine.models.sqlite_config import SQLiteConfig
from cachine.serializers import JSONSerializer


def _make_cache(namespace: str = "test", database: str = ":memory:") -> SQLiteCache:
    return SQLiteCache(
        SQLiteConfig(database=database),
        namespace=namespace,
        serializer=JSONSerializer(),
    )


def test_basic_set_get_delete() -> None:
    cache = _make_cache()
    try:
        cache.set("k", {"v": 1})
        assert cache.get("k") == {"v": 1}
        assert cache.exists("k") is True
        assert cache.delete("k") is True
        assert cache.exists("k") is False
        assert cache.delete("missing") is False
    finally:
        cache.close()


def test_get_default() -> None:
    cache = _make_cache()
    try:
        assert cache.get("missing") is None
        assert cache.get("missing", default=42) == 42
    finally:
        cache.close()


def test_ttl_persist_touch() -> None:
    cache = _make_cache()
    try:
        cache.set("k", "v", ttl=60)
        t = cache.ttl("k")
        assert isinstance(t, int) and 0 < t <= 60

        assert cache.persist("k") is True
        assert cache.ttl("k") is None
        # persist on key without ttl returns False
        assert cache.persist("k") is False

        # touch without ttl just reports presence
        assert cache.touch("k") is True
        # touch with ttl sets ttl
        assert cache.touch("k", ttl=30) is True
        assert isinstance(cache.ttl("k"), int)
    finally:
        cache.close()


def test_expire_and_expire_at() -> None:
    cache = _make_cache()
    try:
        cache.set("x", 1)
        assert cache.expire("x", ttl=0) is True
        assert cache.exists("x") is False

        cache.set("y", 2)
        assert cache.expire_at("y", datetime.now(timezone.utc) - timedelta(seconds=1)) is True
        assert cache.exists("y") is False

        cache.set("z", 3)
        assert cache.expire_at("z", datetime.now(timezone.utc) + timedelta(seconds=60)) is True
        assert isinstance(cache.ttl("z"), int)
    finally:
        cache.close()


def test_incr_decr_and_ttl_on_create() -> None:
    cache = _make_cache()
    try:
        assert cache.incr("cnt") == 1
        assert cache.incr("cnt", delta=5) == 6
        assert cache.decr("cnt", delta=2) == 4

        assert cache.incr("new", ttl_on_create=30) == 1
        t1 = cache.ttl("new")
        assert isinstance(t1, int) and 0 < t1 <= 30
        # subsequent incrs must not reset the TTL
        cache.incr("new", ttl_on_create=5)
        t2 = cache.ttl("new")
        assert t2 is not None and t2 <= t1
    finally:
        cache.close()


def test_get_or_set_computes_once() -> None:
    cache = _make_cache()
    calls = {"n": 0}

    def factory() -> int:
        calls["n"] += 1
        return 42

    try:
        assert cache.get_or_set("ans", factory, ttl=60) == 42
        assert cache.get_or_set("ans", factory, ttl=60) == 42
        assert calls["n"] == 1
    finally:
        cache.close()


def test_tags_invalidation() -> None:
    cache = _make_cache()
    try:
        cache.set("user:1", {"id": 1})
        cache.set("user:2", {"id": 2})
        cache.add_tags("user:1", ["users", "user:1"])
        cache.add_tags("user:2", ["users", "user:2"])

        assert cache.invalidate_tags(["users"]) == 2
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
    finally:
        cache.close()


def test_invalidate_tags_subset() -> None:
    cache = _make_cache()
    try:
        cache.set("user:1", {"id": 1})
        cache.set("user:2", {"id": 2})
        cache.add_tags("user:1", ["users", "user:1"])
        cache.add_tags("user:2", ["users", "user:2"])

        assert cache.invalidate_tags(["user:1"]) == 1
        assert cache.get("user:1") is None
        assert cache.get("user:2") == {"id": 2}
    finally:
        cache.close()


def test_namespace_isolation_file(tmp_path: Path) -> None:
    db = str(tmp_path / "cache.db")
    a = SQLiteCache(SQLiteConfig(database=db), namespace="a")
    b = SQLiteCache(SQLiteConfig(database=db), namespace="b")
    try:
        a.set("k", "va")
        b.set("k", "vb")
        assert a.get("k") == "va"
        assert b.get("k") == "vb"
        a.clear()
        assert a.get("k") is None
        assert b.get("k") == "vb"
    finally:
        a.close()
        b.close()


def test_persistence_across_reopen(tmp_path: Path) -> None:
    db = str(tmp_path / "cache.db")
    c1 = SQLiteCache(SQLiteConfig(database=db), namespace="p", serializer=JSONSerializer())
    c1.set("stay", {"a": 1})
    c1.close()

    c2 = SQLiteCache(SQLiteConfig(database=db), namespace="p", serializer=JSONSerializer())
    try:
        assert c2.get("stay") == {"a": 1}
    finally:
        c2.close()


def test_clear_requires_namespace_or_flag() -> None:
    cache = SQLiteCache(SQLiteConfig(database=":memory:"))
    try:
        with pytest.raises(RuntimeError):
            cache.clear()
        cache.set("k", b"v")
        cache.clear(dangerously_clear_all=True)
        assert cache.get("k") is None
    finally:
        cache.close()


def test_ping_and_context_manager() -> None:
    with SQLiteCache(SQLiteConfig(database=":memory:"), namespace="t") as cache:
        status = cache.ping()
        assert status["healthy"] is True
        assert status["backend"] == "sqlite"
        assert cache.ping_ok() is True


def test_ttl_zero_deletes_immediately() -> None:
    cache = _make_cache()
    try:
        cache.set("k", "v", ttl=0)
        assert cache.get("k") is None
        assert cache.exists("k") is False
    finally:
        cache.close()


def test_expired_key_returns_default() -> None:
    import time

    cache = _make_cache()
    try:
        cache.set("k", "v", ttl=1)
        assert cache.get("k") == "v"
        time.sleep(1.05)
        assert cache.get("k", default="gone") == "gone"
        assert cache.exists("k") is False
    finally:
        cache.close()
