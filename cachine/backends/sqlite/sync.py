from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

from cachine.core.types import HealthStatus
from cachine.models.sqlite_config import SQLiteConfig
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

    Storage layout:
      - ``cache_data(key, value, expires_at)`` holds values as BLOBs (when a
        serializer is configured) or their native sqlite types (ints for
        counters, strings, bytes). ``expires_at`` is UTC Unix seconds or NULL.
      - ``cache_tags(tag, key)`` maintains the many-to-many association used
        by ``add_tags`` / ``invalidate_tags``.

    Concurrency:
      - A single connection with ``check_same_thread=False`` is shared, and
        access is serialized through a :class:`threading.RLock`. WAL journal
        mode is enabled by default so concurrent readers from other processes
        don't block each other.
      - ``incr``/``invalidate_tags`` wrap their statements in ``BEGIN
        IMMEDIATE`` transactions to make multi-step mutations atomic under
        concurrent processes.

    Args:
        config (SQLiteConfig): SQLite configuration.
        namespace (str | None): Optional key namespace prefix.
        serializer (Any | None): Default serializer (``dumps``/``loads``).

    Examples:
        >>> from cachine.models.sqlite_config import SQLiteConfig
        >>> cache = SQLiteCache(SQLiteConfig(database=":memory:"), namespace="app")
        >>> cache.set("k", b"v", ttl=60)
        >>> cache.get("k")
        b'v'
    """

    def __init__(
        self,
        config: SQLiteConfig,
        *,
        namespace: str | None = None,
        serializer: Any | None = None,
    ) -> None:
        self._config = config
        self._ns = f"{namespace}:" if namespace else ""
        self._serializer = serializer
        self._lock = RLock()
        self._conn = self._create_connection(config)
        self._init_schema()

    # ---- Connection setup ----
    @staticmethod
    def _create_connection(config: SQLiteConfig) -> sqlite3.Connection:
        kwargs: dict[str, Any] = {
            "database": config.database,
            "timeout": float(config.timeout),
            "check_same_thread": bool(config.check_same_thread),
            # autocommit: we issue explicit BEGIN when needed.
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
                    # WAL is unsupported on some in-memory databases; ignore.
                    pass
            if self._config.synchronous:
                conn.execute(f"PRAGMA synchronous={self._config.synchronous}")
            if self._config.busy_timeout_ms is not None:
                conn.execute(f"PRAGMA busy_timeout={int(self._config.busy_timeout_ms)}")
            for stmt in DDL_STATEMENTS:
                conn.execute(stmt)

    # ---- Basic ops ----
    def get(self, key: str, default: Any = None, serializer: Any = None) -> Any:
        """Get a value by key. Expired keys return ``default``."""
        k = self._ns + key
        with self._lock:
            self._cleanup_if_expired(k)
            row = self._conn.execute("SELECT value FROM cache_data WHERE key = ?", (k,)).fetchone()
        if row is None:
            return default
        raw = row[0]
        ser = serializer or self._serializer
        if ser is not None and isinstance(raw, bytes | bytearray):
            try:
                return ser.loads(bytes(raw))
            except Exception:
                return raw
        return raw

    def set(self, key: str, value: Any, ttl: int | timedelta | None = None, serializer: Any = None) -> None:
        """Store a value with optional TTL (seconds or timedelta)."""
        k = self._ns + key
        ser = serializer or self._serializer
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
        """Delete a key. Returns True if it existed."""
        k = self._ns + key
        with self._lock:
            cur = self._conn.execute("DELETE FROM cache_data WHERE key = ?", (k,))
            self._conn.execute("DELETE FROM cache_tags WHERE key = ?", (k,))
            return bool(cur.rowcount)

    def exists(self, key: str) -> bool:
        """Return True if ``key`` exists and is not expired."""
        k = self._ns + key
        with self._lock:
            self._cleanup_if_expired(k)
            row = self._conn.execute("SELECT 1 FROM cache_data WHERE key = ?", (k,)).fetchone()
        return row is not None

    def clear(self, dangerously_clear_all: bool = False) -> None:
        """Clear keys in this namespace, or the whole database."""
        with self._lock:
            if dangerously_clear_all or not self._ns:
                if not dangerously_clear_all and not self._ns:
                    raise RuntimeError("clear() requires a namespace or set dangerously_clear_all=True")
                self._conn.execute("DELETE FROM cache_data")
                self._conn.execute("DELETE FROM cache_tags")
                return
            pattern = like_prefix_pattern(self._ns)
            self._conn.execute("DELETE FROM cache_tags WHERE key LIKE ? ESCAPE '\\'", (pattern,))
            self._conn.execute("DELETE FROM cache_data WHERE key LIKE ? ESCAPE '\\'", (pattern,))

    # ---- Enrichment ----
    def get_or_set(self, key: str, factory: Any, ttl: int | timedelta | None = None, jitter: int | None = None) -> Any:  # pylint: disable=unused-argument
        """Get the cached value or compute-and-set via ``factory``."""
        sentinel = _MISSING
        val = self.get(key, default=sentinel)
        if val is not sentinel:
            return val
        computed = factory() if callable(factory) else factory
        self.set(key, computed, ttl=ttl)
        return computed

    # ---- TTL management ----
    def expire(self, key: str, ttl: int | timedelta) -> bool:
        """Set a relative TTL. ``ttl <= 0`` deletes the key."""
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
        """Set an absolute expiration. Past timestamps delete the key."""
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

    def touch(self, key: str, ttl: int | timedelta | None = None) -> bool:
        """Refresh presence; with ``ttl`` also resets expiration."""
        if ttl is None:
            return self.exists(key)
        return self.expire(key, ttl)

    def ttl(self, key: str) -> int | None:
        """Return remaining TTL in seconds, or None if key/TTL is missing."""
        k = self._ns + key
        with self._lock:
            self._cleanup_if_expired(k)
            row = self._conn.execute("SELECT expires_at FROM cache_data WHERE key = ?", (k,)).fetchone()
        if row is None or row[0] is None:
            return None
        remaining = int(row[0] - now_epoch())
        return remaining if remaining >= 0 else None

    def persist(self, key: str) -> bool:
        """Remove expiration from a key. Returns True if a TTL was cleared."""
        k = self._ns + key
        with self._lock:
            cur = self._conn.execute(
                "UPDATE cache_data SET expires_at = NULL WHERE key = ? AND expires_at IS NOT NULL",
                (k,),
            )
            return bool(cur.rowcount)

    # ---- Counters ----
    def incr(self, key: str, delta: int = 1, ttl_on_create: int | timedelta | None = None) -> int:
        """Atomically add ``delta`` to an integer counter. ``ttl_on_create`` only applies on first create."""
        k = self._ns + key
        create_seconds = to_seconds(ttl_on_create)
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

    def decr(self, key: str, delta: int = 1) -> int:
        """Decrement an integer counter by ``delta``."""
        return self.incr(key, delta=-int(delta))

    # ---- Tags ----
    def add_tags(self, key: str, tags: list[str], ttl: int | timedelta | None = None) -> None:  # pylint: disable=unused-argument
        """Associate ``tags`` with ``key``. ``ttl`` is accepted for interface parity and ignored."""
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
        """Delete all keys associated with the given tags. Returns number removed."""
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
    def ping(self) -> HealthStatus:
        """Check health by running ``SELECT 1``."""
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return {"healthy": True, "latency_ms": 0.0, "backend": "sqlite"}
        except Exception:
            return {"healthy": False, "latency_ms": 0.0, "backend": "sqlite"}

    def ping_ok(self) -> bool:
        """Boolean health check."""
        return bool(self.ping().get("healthy", False))

    def close(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def get_stats(self) -> dict[str, Any] | None:
        """Return None; middleware may override to provide stats."""
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
        """Delete a key in place if past its expires_at. Caller holds the lock."""
        self._conn.execute(
            "DELETE FROM cache_data WHERE key = ? AND expires_at IS NOT NULL AND expires_at <= ?",
            (k, now_epoch()),
        )


# Sentinel for the "ttl <= 0 -> immediate delete" path out of _expires_at.
_EXPIRE_IMMEDIATELY = object()


def _row_expired(row: tuple[Any, float | None]) -> bool:
    exp = row[1]
    return exp is not None and exp <= now_epoch()


def _coerce_int(value: Any) -> int:
    """Read a counter value back as int. SQLite stores the native int we wrote,
    but serialized counters (bytes/str) are possible if the user mixed APIs."""
    if isinstance(value, int):
        return value
    if isinstance(value, bytes | bytearray):
        try:
            return int(value.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Cannot increment non-integer bytes value: {value!r}") from e
    return int(value)


class _transaction:
    """``BEGIN IMMEDIATE`` context manager that commits on success, rolls back on error."""

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
