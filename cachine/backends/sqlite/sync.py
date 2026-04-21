from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from threading import RLock
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

_MISSING = object()


class SQLiteCache:
    """Synchronous SQLite-backed cache.

    Fills the gap between :class:`~cachine.backends.inmemory.cache.InMemoryCache`
    (fast but non-persistent, single-process) and
    :class:`~cachine.backends.redis.sync.RedisCache` (distributed but requires
    a server). SQLite gives persistence with zero external dependencies —
    ideal for CLIs, desktop apps, notebooks, and single-VM services.

    Construction supports two forms:
      - Kwargs shortcut (recommended for simple cases)::

            SQLiteCache(database="/tmp/cache.db", namespace="app")

      - Explicit config (advanced tuning)::

            SQLiteCache(SQLiteConfig(database="...", journal_mode="WAL"), namespace="app")
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
            raise TypeError("SQLiteCache: pass either `config` or `database=...` kwargs, not both")
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
        self._lock = RLock()
        self._conn = self._create_connection(config)
        self._init_schema()

    # ---- URL constructor ----
    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        namespace: str | None = None,
        serializer: Any | None = None,
    ) -> SQLiteCache:
        """Construct a :class:`SQLiteCache` from a ``sqlite://`` URL."""
        from cachine.utils.sqlite_url import SQLiteURLParseError, parse_sqlite_url

        scheme = url.split("://", 1)[0].lower() if "://" in url else ""
        if scheme and scheme != "sqlite":
            raise SQLiteURLParseError(
                f"SQLiteCache.from_url received non-SQLite URL ({scheme!r}); use RedisCache.from_url for redis:// URLs"
            )
        config = parse_sqlite_url(url)
        return cls(config, namespace=namespace, serializer=serializer)

    # ---- Connection setup ----
    @staticmethod
    def _create_connection(config: SQLiteConfig) -> sqlite3.Connection:
        kwargs: dict[str, Any] = {
            "database": config.database,
            "timeout": float(config.timeout),
            "check_same_thread": bool(config.check_same_thread),
            "isolation_level": None,
        }
        if config.database.startswith("file:"):
            kwargs["uri"] = True
        for k, v in config.extra.items():
            kwargs.setdefault(k, v)
        conn: sqlite3.Connection = sqlite3.connect(**kwargs)
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._conn
            if self._config.journal_mode:
                try:
                    conn.execute(f"PRAGMA journal_mode={self._config.journal_mode}")
                except sqlite3.DatabaseError:
                    pass
            if self._config.synchronous:
                conn.execute(f"PRAGMA synchronous={self._config.synchronous}")
            if self._config.busy_timeout_ms is not None:
                conn.execute(f"PRAGMA busy_timeout={int(self._config.busy_timeout_ms)}")
            for stmt in DDL_STATEMENTS:
                conn.execute(stmt)

    # ---- Basic ops ----
    def get(self, key: str, default: Any = None, *, serializer: Any = MISSING) -> Any:
        """Get a value by key. Expired keys return ``default``."""
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="SQLiteCache.get",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        with self._lock:
            self._cleanup_if_expired(k)
            row = self._conn.execute("SELECT value FROM cache_data WHERE key = ?", (k,)).fetchone()
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

    def set(
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
                owner="SQLiteCache.set",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        ser = serializer if serializer is not MISSING and serializer is not None else self._serializer
        payload = ser.dumps(value) if ser is not None else value
        expires_at = self._expires_at(ttl)
        if expires_at is _EXPIRE_IMMEDIATELY:
            self.delete(key)
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO cache_data (key, value, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, expires_at = excluded.expires_at",
                (k, payload, expires_at),
            )

    def delete(self, key: str) -> bool:
        """Delete a key."""
        k = self._ns + key
        with self._lock:
            cur = self._conn.execute("DELETE FROM cache_data WHERE key = ?", (k,))
            self._conn.execute("DELETE FROM cache_tags WHERE key = ?", (k,))
            return bool(cur.rowcount)

    def exists(self, key: str) -> bool:
        """Return ``True`` if the key exists and is not expired."""
        k = self._ns + key
        with self._lock:
            self._cleanup_if_expired(k)
            row = self._conn.execute("SELECT 1 FROM cache_data WHERE key = ?", (k,)).fetchone()
        return row is not None

    def clear(self, *, all: bool = False, dangerously_clear_all: Any = MISSING) -> None:
        """Clear keys in this namespace, or the whole database."""
        force = resolve_renamed_kwarg(
            old_name="dangerously_clear_all",
            new_name="all",
            old_value=dangerously_clear_all,
            new_value=all,
            owner="SQLiteCache.clear",
            new_default=False,
        )
        force = bool(force) if force is not None else False
        with self._lock:
            if force or not self._ns:
                if not force and not self._ns:
                    raise RuntimeError("clear() requires a namespace or pass all=True")
                self._conn.execute("DELETE FROM cache_data")
                self._conn.execute("DELETE FROM cache_tags")
                return
            pattern = like_prefix_pattern(self._ns)
            self._conn.execute("DELETE FROM cache_tags WHERE key LIKE ? ESCAPE '\\'", (pattern,))
            self._conn.execute("DELETE FROM cache_data WHERE key LIKE ? ESCAPE '\\'", (pattern,))

    # ---- Enrichment ----
    def get_or_set(  # pylint: disable=unused-argument
        self,
        key: str,
        factory: Any,
        *,
        ttl: int | timedelta | None = None,
        jitter: int | None = None,  # noqa: ARG002
    ) -> Any:
        """Get the cached value or compute-and-set via ``factory``."""
        val = self.get(key, default=_MISSING)
        if val is not _MISSING:
            return val
        computed = factory() if callable(factory) else factory
        self.set(key, computed, ttl=ttl)
        return computed

    # ---- TTL management ----
    def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        """Set a relative TTL."""
        k = self._ns + key
        seconds = to_seconds(ttl)
        if seconds is None:
            return False
        if seconds <= 0:
            return self.delete(key)
        with self._lock:
            cur = self._conn.execute(
                "UPDATE cache_data SET expires_at = ? WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                (now_epoch() + seconds, k, now_epoch()),
            )
            return bool(cur.rowcount)

    def expire_at(self, key: str, when: datetime) -> bool:
        """Set an absolute expiration."""
        k = self._ns + key
        ts = when.timestamp() if when.tzinfo else when.replace(tzinfo=timezone.utc).timestamp()
        if ts <= now_epoch():
            return self.delete(key)
        with self._lock:
            cur = self._conn.execute(
                "UPDATE cache_data SET expires_at = ? WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                (ts, k, now_epoch()),
            )
            return bool(cur.rowcount)

    def touch(self, key: str, *, ttl: int | timedelta | None = None) -> bool:
        """Refresh presence; with ``ttl`` resets expiration."""
        if ttl is None:
            return self.exists(key)
        return self.expire(key, ttl=ttl)

    def ttl(self, key: str) -> int | None:
        """Return remaining TTL in seconds."""
        k = self._ns + key
        with self._lock:
            self._cleanup_if_expired(k)
            row = self._conn.execute("SELECT expires_at FROM cache_data WHERE key = ?", (k,)).fetchone()
        if row is None or row[0] is None:
            return None
        remaining = int(row[0] - now_epoch())
        return remaining if remaining >= 0 else None

    def persist(self, key: str) -> bool:
        """Remove expiration from a key."""
        k = self._ns + key
        with self._lock:
            cur = self._conn.execute(
                "UPDATE cache_data SET expires_at = NULL WHERE key = ? AND expires_at IS NOT NULL",
                (k,),
            )
            return bool(cur.rowcount)

    # ---- Counters ----
    def incr(
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
            owner="SQLiteCache.incr",
        )
        k = self._ns + key
        create_seconds = to_seconds(effective_ttl) if effective_ttl is not None else None
        with self._lock, _transaction(self._conn):
            row = self._conn.execute(
                "SELECT value, expires_at FROM cache_data WHERE key = ?",
                (k,),
            ).fetchone()
            existed = row is not None and not _row_expired(row)
            if existed:
                current = _coerce_int(row[0])
                new_val = current + int(delta)
                self._conn.execute(
                    "UPDATE cache_data SET value = ? WHERE key = ?",
                    (new_val, k),
                )
            else:
                new_val = int(delta)
                expires_at = now_epoch() + create_seconds if create_seconds and create_seconds > 0 else None
                self._conn.execute(
                    "INSERT INTO cache_data (key, value, expires_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = ?, expires_at = ?",
                    (k, new_val, expires_at, new_val, expires_at),
                )
            return new_val

    def decr(self, key: str, *, delta: int = 1) -> int:
        """Decrement an integer counter."""
        return self.incr(key, delta=-int(delta))

    # ---- Tags ----
    def add_tags(self, key: str, tags: list[str], *, ttl: int | timedelta | None = None) -> None:  # noqa: ARG002  # pylint: disable=unused-argument
        """Associate ``tags`` with ``key``."""
        if not tags:
            return
        k = self._ns + key
        ns_tags = [self._ns + t for t in tags]
        with self._lock, _transaction(self._conn):
            row = self._conn.execute("SELECT 1 FROM cache_data WHERE key = ?", (k,)).fetchone()
            if row is None:
                return
            self._conn.executemany(
                "INSERT OR IGNORE INTO cache_tags (tag, key) VALUES (?, ?)",
                [(t, k) for t in ns_tags],
            )

    def invalidate_tags(self, tags: list[str]) -> int:
        """Delete all keys associated with the given tags."""
        if not tags:
            return 0
        ns_tags = [self._ns + t for t in tags]
        placeholders = ",".join("?" for _ in ns_tags)
        with self._lock, _transaction(self._conn):
            rows = self._conn.execute(
                f"SELECT DISTINCT key FROM cache_tags WHERE tag IN ({placeholders})",
                ns_tags,
            ).fetchall()
            keys = [r[0] for r in rows]
            if not keys:
                self._conn.execute(
                    f"DELETE FROM cache_tags WHERE tag IN ({placeholders})",
                    ns_tags,
                )
                return 0
            key_placeholders = ",".join("?" for _ in keys)
            deleted = self._conn.execute(
                f"DELETE FROM cache_data WHERE key IN ({key_placeholders})",
                keys,
            ).rowcount
            self._conn.execute(
                f"DELETE FROM cache_tags WHERE key IN ({key_placeholders})",
                keys,
            )
            self._conn.execute(
                f"DELETE FROM cache_tags WHERE tag IN ({placeholders})",
                ns_tags,
            )
            return int(deleted or 0)

    # ---- Health / lifecycle ----
    def health(self) -> HealthStatus:
        """Check health by running ``SELECT 1``."""
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return {"healthy": True, "latency_ms": 0.0, "backend": "sqlite"}
        except Exception:
            return {"healthy": False, "latency_ms": 0.0, "backend": "sqlite"}

    def healthy(self) -> bool:
        """Return ``True`` if the cache is healthy."""
        return bool(self.health().get("healthy", False))

    # Deprecated aliases
    def ping(self) -> HealthStatus:
        """Deprecated alias for :meth:`health`."""
        warn_deprecated_method(name="ping", owner="SQLiteCache", replacement="health")
        return self.health()

    def ping_ok(self) -> bool:
        """Deprecated alias for :meth:`healthy`."""
        warn_deprecated_method(name="ping_ok", owner="SQLiteCache", replacement="healthy")
        return self.healthy()

    def close(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def get_stats(self) -> dict[str, Any] | None:
        """Return ``None``; middleware may override."""
        return None

    # ---- Context manager ----
    def __enter__(self) -> SQLiteCache:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

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

    def _cleanup_if_expired(self, k: str) -> None:
        self._conn.execute(
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


class _transaction:
    """``BEGIN IMMEDIATE`` context manager with commit/rollback semantics."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self._conn.execute("BEGIN IMMEDIATE")
        return self._conn

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is None:
            self._conn.execute("COMMIT")
        else:
            try:
                self._conn.execute("ROLLBACK")
            except Exception:
                pass
