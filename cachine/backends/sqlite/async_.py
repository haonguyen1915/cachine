from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, overload

from cachine.core.types import HealthStatus
from cachine.models.sqlite_config import SQLiteConfig
from cachine.utils._deprecations import (
    MISSING,
    resolve_renamed_kwarg,
    warn_deprecated_kwarg,
    warn_deprecated_method,
)
from cachine.utils.helpers import to_seconds

from ._schema import DDL_STATEMENTS, like_prefix_pattern, now_epoch


class AsyncSQLiteCache:
    """Async SQLite cache built on ``aiosqlite``.

    Mirrors :class:`cachine.backends.sqlite.sync.SQLiteCache` with coroutine
    methods. ``aiosqlite`` serializes its own operations on a dedicated
    worker thread; an :class:`asyncio.Lock` guards our multi-statement
    transactions (``incr``, ``invalidate_tags``).
    """

    @overload
    def __init__(
        self,
        config: SQLiteConfig,
        *,
        namespace: str | None = None,
        serializer: Any | None = None,
    ) -> None: ...

    @overload
    def __init__(
        self,
        *,
        database: str = ":memory:",
        timeout: float = 5.0,
        busy_timeout_ms: int | None = 5000,
        journal_mode: str | None = "WAL",
        synchronous: str | None = "NORMAL",
        check_same_thread: bool = False,
        namespace: str | None = None,
        serializer: Any | None = None,
    ) -> None: ...

    def __init__(
        self,
        config: SQLiteConfig | None = None,
        *,
        database: str | None = None,
        timeout: float = 5.0,
        busy_timeout_ms: int | None = 5000,
        journal_mode: str | None = "WAL",
        synchronous: str | None = "NORMAL",
        check_same_thread: bool = False,
        namespace: str | None = None,
        serializer: Any | None = None,
    ) -> None:
        if config is not None and database is not None:
            raise TypeError("AsyncSQLiteCache: pass either `config` or `database=...` kwargs, not both")
        if config is None:
            config = SQLiteConfig(
                database=database if database is not None else ":memory:",
                timeout=timeout,
                busy_timeout_ms=busy_timeout_ms,
                journal_mode=journal_mode,
                synchronous=synchronous,
                check_same_thread=check_same_thread,
            )
        self._config = config
        self._ns = f"{namespace}:" if namespace else ""
        self._serializer = serializer
        self._lock = asyncio.Lock()
        self._conn: Any = None

    # ---- URL constructor ----
    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        namespace: str | None = None,
        serializer: Any | None = None,
    ) -> AsyncSQLiteCache:
        """Construct an :class:`AsyncSQLiteCache` from a ``sqlite://`` URL."""
        from cachine.utils.sqlite_url import SQLiteURLParseError, parse_sqlite_url

        scheme = url.split("://", 1)[0].lower() if "://" in url else ""
        if scheme and scheme != "sqlite":
            raise SQLiteURLParseError(
                f"AsyncSQLiteCache.from_url received non-SQLite URL ({scheme!r}); use AsyncRedisCache.from_url for redis:// URLs"
            )
        config = parse_sqlite_url(url)
        return cls(config, namespace=namespace, serializer=serializer)

    # ---- Connection setup ----
    async def _ensure_conn(self) -> Any:
        conn: Any = self._conn
        if conn is not None:
            return conn
        async with self._lock:
            conn = self._conn
            if conn is not None:
                return conn
            try:
                import aiosqlite
            except ImportError as e:
                raise RuntimeError("aiosqlite is not installed; install with: `pip install aiosqlite`") from e

            kwargs: dict[str, Any] = {
                "database": self._config.database,
                "timeout": float(self._config.timeout),
                "check_same_thread": bool(self._config.check_same_thread),
                "isolation_level": None,
            }
            if self._config.database.startswith("file:"):
                kwargs["uri"] = True
            for k, v in self._config.extra.items():
                kwargs.setdefault(k, v)

            conn = await aiosqlite.connect(**kwargs)
            if self._config.journal_mode:
                try:
                    await conn.execute(f"PRAGMA journal_mode={self._config.journal_mode}")
                except Exception:
                    pass
            if self._config.synchronous:
                await conn.execute(f"PRAGMA synchronous={self._config.synchronous}")
            if self._config.busy_timeout_ms is not None:
                await conn.execute(f"PRAGMA busy_timeout={int(self._config.busy_timeout_ms)}")
            for stmt in DDL_STATEMENTS:
                await conn.execute(stmt)
            self._conn = conn
            return conn

    # ---- Basic ops ----
    async def get(self, key: str, default: Any = None, *, serializer: Any = MISSING) -> Any:
        """Get a value by key."""
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="AsyncSQLiteCache.get",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        conn = await self._ensure_conn()
        await self._cleanup_if_expired(conn, k)
        async with conn.execute("SELECT value FROM cache_data WHERE key = ?", (k,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return default
        raw = row[0]
        ser = serializer if serializer is not MISSING and serializer is not None else self._serializer
        if ser is not None and isinstance(raw, bytes | bytearray):
            try:
                return ser.loads(bytes(raw))
            except Exception:
                return raw
        return raw

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | timedelta | None = None,
        serializer: Any = MISSING,
    ) -> None:
        """Store a value with optional TTL."""
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="AsyncSQLiteCache.set",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        ser = serializer if serializer is not MISSING and serializer is not None else self._serializer
        payload = ser.dumps(value) if ser is not None else value
        expires_at = self._expires_at(ttl)
        if expires_at is _EXPIRE_IMMEDIATELY:
            await self.delete(key)
            return
        conn = await self._ensure_conn()
        await conn.execute(
            "INSERT INTO cache_data (key, value, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, expires_at = excluded.expires_at",
            (k, payload, expires_at),
        )

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        k = self._ns + key
        conn = await self._ensure_conn()
        cur = await conn.execute("DELETE FROM cache_data WHERE key = ?", (k,))
        rowcount = cur.rowcount
        await cur.close()
        await conn.execute("DELETE FROM cache_tags WHERE key = ?", (k,))
        return bool(rowcount)

    async def exists(self, key: str) -> bool:
        """Return ``True`` if the key exists."""
        k = self._ns + key
        conn = await self._ensure_conn()
        await self._cleanup_if_expired(conn, k)
        async with conn.execute("SELECT 1 FROM cache_data WHERE key = ?", (k,)) as cur:
            row = await cur.fetchone()
        return row is not None

    async def clear(self, *, all: bool = False, dangerously_clear_all: Any = MISSING) -> None:
        """Clear keys in the current namespace or the whole database."""
        force = resolve_renamed_kwarg(
            old_name="dangerously_clear_all",
            new_name="all",
            old_value=dangerously_clear_all,
            new_value=all,
            owner="AsyncSQLiteCache.clear",
            new_default=False,
        )
        force = bool(force) if force is not None else False
        conn = await self._ensure_conn()
        if force or not self._ns:
            if not force and not self._ns:
                raise RuntimeError("clear() requires a namespace or pass all=True")
            await conn.execute("DELETE FROM cache_data")
            await conn.execute("DELETE FROM cache_tags")
            return
        pattern = like_prefix_pattern(self._ns)
        await conn.execute("DELETE FROM cache_tags WHERE key LIKE ? ESCAPE '\\'", (pattern,))
        await conn.execute("DELETE FROM cache_data WHERE key LIKE ? ESCAPE '\\'", (pattern,))

    # ---- Enrichment ----
    async def get_or_set(  # pylint: disable=unused-argument
        self,
        key: str,
        factory: Any,
        *,
        ttl: int | timedelta | None = None,
        jitter: int | None = None,  # noqa: ARG002
    ) -> Any:
        """Get or compute-and-set a value."""
        sentinel = object()
        val = await self.get(key, default=sentinel)
        if val is not sentinel:
            return val
        computed = factory() if callable(factory) else factory
        if inspect.isawaitable(computed):
            computed = await computed
        await self.set(key, computed, ttl=ttl)
        return computed

    # ---- TTL management ----
    async def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        """Set a relative TTL."""
        k = self._ns + key
        seconds = to_seconds(ttl)
        if seconds is None:
            return False
        if seconds <= 0:
            return await self.delete(key)
        conn = await self._ensure_conn()
        cur = await conn.execute(
            "UPDATE cache_data SET expires_at = ? WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
            (now_epoch() + seconds, k, now_epoch()),
        )
        rowcount = cur.rowcount
        await cur.close()
        return bool(rowcount)

    async def expire_at(self, key: str, when: datetime) -> bool:
        """Set an absolute expiration."""
        k = self._ns + key
        ts = when.timestamp() if when.tzinfo else when.replace(tzinfo=timezone.utc).timestamp()
        if ts <= now_epoch():
            return await self.delete(key)
        conn = await self._ensure_conn()
        cur = await conn.execute(
            "UPDATE cache_data SET expires_at = ? WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
            (ts, k, now_epoch()),
        )
        rowcount = cur.rowcount
        await cur.close()
        return bool(rowcount)

    async def touch(self, key: str, *, ttl: int | timedelta | None = None) -> bool:
        """Refresh presence; with ``ttl`` resets expiration."""
        if ttl is None:
            return await self.exists(key)
        return await self.expire(key, ttl=ttl)

    async def ttl(self, key: str) -> int | None:
        """Return remaining TTL in seconds."""
        k = self._ns + key
        conn = await self._ensure_conn()
        await self._cleanup_if_expired(conn, k)
        async with conn.execute("SELECT expires_at FROM cache_data WHERE key = ?", (k,)) as cur:
            row = await cur.fetchone()
        if row is None or row[0] is None:
            return None
        remaining = int(row[0] - now_epoch())
        return remaining if remaining >= 0 else None

    async def persist(self, key: str) -> bool:
        """Remove expiration from a key."""
        k = self._ns + key
        conn = await self._ensure_conn()
        cur = await conn.execute(
            "UPDATE cache_data SET expires_at = NULL WHERE key = ? AND expires_at IS NOT NULL",
            (k,),
        )
        rowcount = cur.rowcount
        await cur.close()
        return bool(rowcount)

    # ---- Counters ----
    async def incr(
        self,
        key: str,
        *,
        delta: int = 1,
        ttl_if_new: int | timedelta | None = None,
        ttl_on_create: Any = MISSING,
    ) -> int:
        """Atomically add ``delta`` to an integer counter."""
        effective_ttl = resolve_renamed_kwarg(
            old_name="ttl_on_create",
            new_name="ttl_if_new",
            old_value=ttl_on_create,
            new_value=ttl_if_new,
            owner="AsyncSQLiteCache.incr",
        )
        k = self._ns + key
        create_seconds = to_seconds(effective_ttl) if effective_ttl is not None else None
        conn = await self._ensure_conn()
        async with self._lock:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                async with conn.execute("SELECT value, expires_at FROM cache_data WHERE key = ?", (k,)) as cur:
                    row = await cur.fetchone()
                existed = row is not None and not _row_expired(row)
                if existed:
                    current = _coerce_int(row[0])
                    new_val = current + int(delta)
                    await conn.execute(
                        "UPDATE cache_data SET value = ? WHERE key = ?",
                        (new_val, k),
                    )
                else:
                    new_val = int(delta)
                    expires_at = now_epoch() + create_seconds if create_seconds and create_seconds > 0 else None
                    await conn.execute(
                        "INSERT INTO cache_data (key, value, expires_at) VALUES (?, ?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = ?, expires_at = ?",
                        (k, new_val, expires_at, new_val, expires_at),
                    )
                await conn.execute("COMMIT")
                return new_val
            except BaseException:
                try:
                    await conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

    async def decr(self, key: str, *, delta: int = 1) -> int:
        """Decrement an integer counter."""
        return await self.incr(key, delta=-int(delta))

    # ---- Tags ----
    async def add_tags(self, key: str, tags: list[str], *, ttl: int | timedelta | None = None) -> None:  # noqa: ARG002  # pylint: disable=unused-argument
        """Associate ``tags`` with ``key``."""
        if not tags:
            return
        k = self._ns + key
        ns_tags = [self._ns + t for t in tags]
        conn = await self._ensure_conn()
        async with self._lock:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                async with conn.execute("SELECT 1 FROM cache_data WHERE key = ?", (k,)) as cur:
                    row = await cur.fetchone()
                if row is None:
                    await conn.execute("COMMIT")
                    return
                await conn.executemany(
                    "INSERT OR IGNORE INTO cache_tags (tag, key) VALUES (?, ?)",
                    [(t, k) for t in ns_tags],
                )
                await conn.execute("COMMIT")
            except BaseException:
                try:
                    await conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

    async def invalidate_tags(self, tags: list[str]) -> int:
        """Delete all keys associated with the given tags."""
        if not tags:
            return 0
        ns_tags = [self._ns + t for t in tags]
        placeholders = ",".join("?" for _ in ns_tags)
        conn = await self._ensure_conn()
        async with self._lock:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                async with conn.execute(
                    f"SELECT DISTINCT key FROM cache_tags WHERE tag IN ({placeholders})",
                    ns_tags,
                ) as cur:
                    rows = await cur.fetchall()
                keys = [r[0] for r in rows]
                if not keys:
                    await conn.execute(
                        f"DELETE FROM cache_tags WHERE tag IN ({placeholders})",
                        ns_tags,
                    )
                    await conn.execute("COMMIT")
                    return 0
                key_placeholders = ",".join("?" for _ in keys)
                del_cur = await conn.execute(
                    f"DELETE FROM cache_data WHERE key IN ({key_placeholders})",
                    keys,
                )
                deleted = del_cur.rowcount
                await del_cur.close()
                await conn.execute(
                    f"DELETE FROM cache_tags WHERE key IN ({key_placeholders})",
                    keys,
                )
                await conn.execute(
                    f"DELETE FROM cache_tags WHERE tag IN ({placeholders})",
                    ns_tags,
                )
                await conn.execute("COMMIT")
                return int(deleted or 0)
            except BaseException:
                try:
                    await conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

    # ---- Health / lifecycle ----
    async def health(self) -> HealthStatus:
        """Return cache health status."""
        try:
            conn = await self._ensure_conn()
            async with conn.execute("SELECT 1") as cur:
                await cur.fetchone()
            return {"healthy": True, "latency_ms": 0.0, "backend": "sqlite"}
        except Exception:
            return {"healthy": False, "latency_ms": 0.0, "backend": "sqlite"}

    async def healthy(self) -> bool:
        """Return ``True`` if the cache is healthy."""
        s = await self.health()
        return bool(s.get("healthy", False))

    # Deprecated aliases
    async def ping(self) -> HealthStatus:
        """Deprecated alias for :meth:`health`."""
        warn_deprecated_method(name="ping", owner="AsyncSQLiteCache", replacement="health")
        return await self.health()

    async def ping_ok(self) -> bool:
        """Deprecated alias for :meth:`healthy`."""
        warn_deprecated_method(name="ping_ok", owner="AsyncSQLiteCache", replacement="healthy")
        return await self.healthy()

    async def close(self) -> None:
        """Close the underlying aiosqlite connection."""
        if self._conn is None:
            return
        try:
            await self._conn.close()
        except Exception:
            pass
        self._conn = None

    def get_stats(self) -> dict[str, Any] | None:
        """Return ``None``; middleware may override."""
        return None

    # ---- Async context manager ----
    async def __aenter__(self) -> AsyncSQLiteCache:
        await self._ensure_conn()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    # ---- Internal helpers ----
    def _expires_at(self, ttl: int | timedelta | None) -> float | None | object:
        if ttl is None:
            return None
        seconds = to_seconds(ttl)
        if seconds is None:
            return None
        if seconds <= 0:
            return _EXPIRE_IMMEDIATELY
        return now_epoch() + seconds

    async def _cleanup_if_expired(self, conn: Any, k: str) -> None:
        await conn.execute(
            "DELETE FROM cache_data WHERE key = ? AND expires_at IS NOT NULL AND expires_at <= ?",
            (k, now_epoch()),
        )


_EXPIRE_IMMEDIATELY = object()


def _row_expired(row: tuple[Any, float | None]) -> bool:
    exp = row[1]
    return exp is not None and exp <= now_epoch()


def _coerce_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, bytes | bytearray):
        try:
            return int(value.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Cannot increment non-integer bytes value: {value!r}") from e
    return int(value)
