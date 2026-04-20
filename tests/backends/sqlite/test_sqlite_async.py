from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cachine import AsyncSQLiteCache
from cachine.models.sqlite_config import SQLiteConfig
from cachine.serializers import JSONSerializer


def _make_cache(namespace: str = "atest", database: str = ":memory:") -> AsyncSQLiteCache:
    return AsyncSQLiteCache(
        SQLiteConfig(database=database),
        namespace=namespace,
        serializer=JSONSerializer(),
    )


@pytest.mark.asyncio
async def test_async_basic_set_get_delete() -> None:
    cache = _make_cache()
    try:
        await cache.set("k", {"v": 1})
        assert await cache.get("k") == {"v": 1}
        assert await cache.exists("k") is True
        assert await cache.delete("k") is True
        assert await cache.exists("k") is False
        assert await cache.delete("missing") is False
    finally:
        await cache.close()


@pytest.mark.asyncio
async def test_async_ttl_persist_touch() -> None:
    cache = _make_cache()
    try:
        await cache.set("k", "v", ttl=60)
        t = await cache.ttl("k")
        assert isinstance(t, int) and 0 < t <= 60
        assert await cache.persist("k") is True
        assert await cache.ttl("k") is None
        assert await cache.touch("k", ttl=30) is True
        assert isinstance(await cache.ttl("k"), int)
    finally:
        await cache.close()


@pytest.mark.asyncio
async def test_async_expire_expire_at() -> None:
    cache = _make_cache()
    try:
        await cache.set("x", 1)
        assert await cache.expire("x", ttl=0) is True
        assert await cache.exists("x") is False

        await cache.set("y", 2)
        assert await cache.expire_at("y", datetime.now(timezone.utc) - timedelta(seconds=1)) is True
        assert await cache.exists("y") is False

        await cache.set("z", 3)
        assert await cache.expire_at("z", datetime.now(timezone.utc) + timedelta(seconds=60)) is True
        assert isinstance(await cache.ttl("z"), int)
    finally:
        await cache.close()


@pytest.mark.asyncio
async def test_async_incr_decr_and_ttl_on_create() -> None:
    cache = _make_cache()
    try:
        assert await cache.incr("cnt") == 1
        assert await cache.incr("cnt", delta=5) == 6
        assert await cache.decr("cnt", delta=2) == 4

        assert await cache.incr("new", ttl_on_create=30) == 1
        t1 = await cache.ttl("new")
        assert isinstance(t1, int) and 0 < t1 <= 30
        await cache.incr("new", ttl_on_create=5)
        t2 = await cache.ttl("new")
        assert t2 is not None and t2 <= t1
    finally:
        await cache.close()


@pytest.mark.asyncio
async def test_async_get_or_set_sync_and_async_factory() -> None:
    cache = _make_cache()
    calls = {"n": 0}

    async def async_factory() -> int:
        calls["n"] += 1
        return 42

    try:
        assert await cache.get_or_set("ans", async_factory, ttl=60) == 42
        assert await cache.get_or_set("ans", async_factory, ttl=60) == 42
        assert calls["n"] == 1
    finally:
        await cache.close()


@pytest.mark.asyncio
async def test_async_tags_invalidation() -> None:
    cache = _make_cache()
    try:
        await cache.set("user:1", {"id": 1})
        await cache.set("user:2", {"id": 2})
        await cache.add_tags("user:1", ["users", "user:1"])
        await cache.add_tags("user:2", ["users", "user:2"])

        removed = await cache.invalidate_tags(["users"])
        assert removed == 2
        assert await cache.get("user:1") is None
        assert await cache.get("user:2") is None
    finally:
        await cache.close()


@pytest.mark.asyncio
async def test_async_persistence_across_reopen(tmp_path: Path) -> None:
    db = str(tmp_path / "async_cache.db")
    c1 = AsyncSQLiteCache(SQLiteConfig(database=db), namespace="p", serializer=JSONSerializer())
    await c1.set("stay", {"a": 1})
    await c1.close()

    c2 = AsyncSQLiteCache(SQLiteConfig(database=db), namespace="p", serializer=JSONSerializer())
    try:
        assert await c2.get("stay") == {"a": 1}
    finally:
        await c2.close()


@pytest.mark.asyncio
async def test_async_ping_and_context_manager() -> None:
    async with AsyncSQLiteCache(SQLiteConfig(database=":memory:"), namespace="t") as cache:
        status = await cache.ping()
        assert status["healthy"] is True
        assert status["backend"] == "sqlite"
        assert await cache.ping_ok() is True


@pytest.mark.asyncio
async def test_async_clear_namespace(tmp_path: Path) -> None:
    db = str(tmp_path / "async_clear.db")
    a = AsyncSQLiteCache(SQLiteConfig(database=db), namespace="a")
    b = AsyncSQLiteCache(SQLiteConfig(database=db), namespace="b")
    try:
        await a.set("k", b"va")
        await b.set("k", b"vb")
        await a.clear()
        assert await a.get("k") is None
        assert await b.get("k") == b"vb"
    finally:
        await a.close()
        await b.close()
