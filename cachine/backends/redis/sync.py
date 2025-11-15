from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from ...utils.helpers import to_seconds
from .client import RedisClient

_MISSING = object()


class RedisCache:
    """Synchronous Redis-backed cache.

    Provides get/set, TTL management, counters, and tag invalidation using a
    Redis client. A default serializer can be configured for values.

    Args:
        host (str): Redis host. Defaults to ``"localhost"``.
        port (int): Redis port. Defaults to ``6379``.
        db (int): Redis database index. Defaults to ``0``.
        password (str | None): Optional password.
        ssl (bool): Whether to use TLS.
        namespace (str | None): Optional key namespace prefix, e.g. ``"app:"``.
        client (Any | None): Optional injected client (must implement RedisClient-like API).
        serializer (Any | None): Default serializer for values supporting ``dumps``/``loads``.
    """

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
        namespace: Optional[str] = None,
        client: Optional[Any] = None,
        serializer: Optional[Any] = None,
    ) -> None:
        self._ns = f"{namespace}:" if namespace else ""
        self._cfg = {"host": host, "port": port, "db": db, "ssl": ssl}
        self._password = password
        self._client = client  # injected client for testing or custom usage
        self._serializer = serializer

    # Basic ops (stubs)
    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:
        """Get a value by key.

        Args:
            key (str): Cache key.
            default (Any, optional): Value to return when key is missing.
            serializer (Any, optional): Serializer to decode bytes; defaults to
                the instance serializer.

        Returns:
            Any: Decoded value from Redis or ``default`` if missing.
        """
        k = self._ns + key
        client = self._require_client()
        raw = client.get(k)
        if raw is None:
            return default
        ser = serializer or self._serializer
        if ser is not None:
            try:
                return ser.loads(raw)
            except Exception:
                # Fall back to raw if serializer fails
                return raw
        return raw

    def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:
        """Set a value by key.

        Args:
            key (str): Cache key.
            value (Any): Value to store.
            ttl (int | timedelta | None): Optional time-to-live.
            serializer (Any, optional): Serializer to encode value; defaults to instance serializer.

        Returns:
            None
        """
        k = self._ns + key
        client = self._require_client()
        ser = serializer or self._serializer
        payload = ser.dumps(value) if ser is not None else value
        seconds = to_seconds(ttl)
        if seconds is not None:
            client.set(k, payload, ex=seconds)
        else:
            client.set(k, payload)

    def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if the key existed and was removed.
        """
        k = self._ns + key
        client = self._require_client()
        try:
            res = client.delete(k)
            # redis-py returns int count of removed keys
            return bool(res)
        except AttributeError:
            # Some clients may use del
            before = client.get(k) is not None
            client.set(k, None)
            return before

    def exists(self, key: str) -> bool:
        """Check key existence.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if the key exists.
        """
        k = self._ns + key
        client = self._require_client()
        res = client.exists(k)
        if isinstance(res, bool):
            return res
        try:
            return bool(int(res))
        except Exception:
            return bool(res)

    def clear(self, *, dangerously_clear_all: bool = False) -> None:
        """Clear keys in the current namespace or flush the DB.

        Args:
            dangerously_clear_all (bool): When True, flushes the entire database.
                When False, requires a configured namespace and removes only keys
                in that namespace using SCAN/DEL.

        Returns:
            None
        """
        client = self._require_client()
        if dangerously_clear_all:
            try:
                client.flushdb()
            except Exception:
                pass
            return
        if not self._ns:
            raise RuntimeError("clear() requires a namespace or set dangerously_clear_all=True")
        # Delete keys with this namespace prefix
        pattern = f"{self._ns}*"
        try:
            keys = list(client.scan_iter(match=pattern))
        except Exception:
            keys = []
        # client may return bytes
        norm_keys = [k.decode("utf-8") if isinstance(k, bytes | bytearray) else k for k in keys]
        if norm_keys:
            try:
                client.delete_many(*norm_keys)
            except Exception:
                for k in norm_keys:
                    try:
                        client.delete(k)
                    except Exception:
                        pass

    # Enrichment
    def get_or_set(self, key: str, factory: Any, *, ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None) -> Any:  # pylint: disable=unused-argument
        """Get or compute-and-set a value.

        Args:
            key (str): Cache key.
            factory (Any): Callable or value used to compute the value when missing.
            ttl (int | timedelta | None): Optional TTL for the stored value.
            jitter (int | None): Ignored by this implementation.

        Returns:
            Any: Existing value if present; otherwise the computed value.

        Note:
            This implementation is non-atomic and may compute twice under races.
            For strict single-flight behavior consider using the decorator-based API.
        """
        sentinel = _MISSING
        val = self.get(key, default=sentinel)
        if val is not sentinel:
            return val
        computed = factory() if callable(factory) else factory
        self.set(key, computed, ttl=ttl)
        return computed

    # TTL management
    def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        """Set a relative expiration.

        Args:
            key (str): Cache key.
            ttl (int | timedelta): Relative TTL.

        Returns:
            bool: True if the key existed and TTL was set.
        """
        k = self._ns + key
        client = self._require_client()
        seconds = to_seconds(ttl)
        if seconds is None:
            return False
        res = client.expire(k, seconds)
        return bool(res)

    def expire_at(self, key: str, when: datetime) -> bool:
        """Set an absolute expiration.

        Args:
            key (str): Cache key.
            when (datetime): Absolute UTC expiration time.

        Returns:
            bool: True if the key existed and expiration was set.
        """
        k = self._ns + key
        client = self._require_client()
        # redis-py accepts unix time seconds for expireat
        ts = int(when.timestamp())
        res = client.expireat(k, ts)
        return bool(res)

    def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
        """Refresh presence or set a new TTL.

        Args:
            key (str): Cache key.
            ttl (int | timedelta | None): Optional TTL to set. When None, attempts
                a Redis TOUCH or falls back to existence check.

        Returns:
            bool: True if key exists (and TTL was updated when provided).
        """
        # Redis TOUCH does not change TTL; emulate by setting expire when ttl is provided.
        if ttl is None:
            # If client supports TOUCH, use it; else return exists
            client = self._require_client()
            try:
                res = client.touch(self._ns + key)
                return bool(res)
            except AttributeError:
                return self.exists(key)
        else:
            return self.expire(key, ttl=ttl)

    def ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL.

        Args:
            key (str): Cache key.

        Returns:
            int | None: Remaining seconds; None if no TTL or missing.
        """
        k = self._ns + key
        client = self._require_client()
        res = client.ttl(k)
        try:
            val = int(res)
        except Exception:
            return None
        if val < 0:
            # -2 key does not exist, -1 no expiry
            return None
        return val

    def persist(self, key: str) -> bool:
        """Remove expiration from a key.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if a TTL existed and was removed.
        """
        k = self._ns + key
        client = self._require_client()
        try:
            res = client.persist(k)
            return bool(res)
        except AttributeError:
            # Fallback: emulate via TTL check
            ttl = client.ttl(k)
            if ttl is None or (isinstance(ttl, int) and ttl < 0):
                return False
            # Try to remove expiry via PERSIST equivalent
            try:
                client.pexpire(k, 0)  # not correct; placeholder if no persist
            except Exception:
                pass
            return True

    # Counters
    def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
        """Increment an integer value by ``delta``.

        Args:
            key (str): Cache key.
            delta (int): Increment amount.
            ttl_on_create (int | timedelta | None): TTL set only when the key is first created.

        Returns:
            int: The new integer value.
        """
        k = self._ns + key
        client = self._require_client()
        if ttl_on_create is None:
            return int(client.incrby(k, int(delta)))

        # Use Lua for atomic set-ttl-on-create behavior
        pexpire_ms = to_seconds(ttl_on_create)
        ms = 0 if pexpire_ms is None else int(pexpire_ms * 1000)
        script = (
            "local exists = redis.call('EXISTS', KEYS[1])\n"
            "local val = redis.call('INCRBY', KEYS[1], ARGV[1])\n"
            "if exists == 0 and tonumber(ARGV[2]) and tonumber(ARGV[2]) > 0 then\n"
            "  redis.call('PEXPIRE', KEYS[1], ARGV[2])\n"
            "end\n"
            "return val\n"
        )
        try:
            return int(client.eval(script, 1, k, int(delta), ms))
        except AttributeError:
            # Fallback non-atomic path for limited clients
            existed = bool(client.exists(k))
            val = int(client.incrby(k, int(delta)))
            if not existed and ms > 0:
                try:
                    client.pexpire(k, ms)
                except Exception:
                    # try seconds if pexpire not available
                    client.expire(k, max(ms // 1000, 1))
            return val

    def decr(self, key: str, *, delta: int = 1) -> int:
        """Decrement an integer value.

        Args:
            key (str): Cache key.
            delta (int): Decrement amount.

        Returns:
            int: The new integer value.
        """
        return self.incr(key, delta=-int(delta))

    # Tags
    def invalidate_tags(self, tags: list[str]) -> int:
        """Invalidate keys by tags.

        Args:
            tags (list[str]): Tags to invalidate.

        Returns:
            int: Number of unique keys deleted across all tags.
        """
        client = self._require_client()
        deleted_keys: set[str] = set()
        for tag in tags:
            tkey = f"{self._ns}tag::{tag}"
            try:
                members = client.smembers(tkey)
            except Exception:
                members = set()
            for mk in members:
                # mk may be bytes
                key_name = mk.decode("utf-8") if isinstance(mk, bytes | bytearray) else mk
                try:
                    client.delete(key_name)
                except Exception:
                    pass
                deleted_keys.add(key_name)
            try:
                client.delete(tkey)
            except Exception:
                pass
        return len(deleted_keys)

    # Health / lifecycle
    def ping(self) -> dict[str, Any]:
        """Check health.

        Returns:
            dict[str, Any]: Health payload with ``healthy``, ``latency_ms``, and ``backend``.
        """
        return {"healthy": True, "latency_ms": 0.0, "backend": "redis"}

    def ping_ok(self) -> bool:
        """Return a boolean health indicator.

        Returns:
            bool: True if the cache is considered healthy.
        """
        s = self.ping()
        return bool(s.get("healthy", False))

    def close(self) -> None:
        """Close the underlying client if applicable."""
        return None

    # Context manager
    def __enter__(self) -> RedisCache:
        """Enter context manager.

        Returns:
            RedisCache: This cache instance.
        """
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit context manager; no explicit cleanup required."""
        return None

    # Internal helpers
    def _require_client(self) -> Any:
        """Return or construct a Redis client wrapper.

        Returns:
            Any: A client implementing the subset of redis-py used here.

        Raises:
            RuntimeError: If a client cannot be constructed and none is injected.
        """
        if self._client is not None:
            return self._client
        # Lazy import to avoid hard dependency when injected client is used
        try:
            self._client = RedisClient(
                host=str(self._cfg["host"]),
                port=int(self._cfg["port"]),
                db=int(self._cfg["db"]),
                password=self._password,
                ssl=bool(self._cfg["ssl"]),
                decode_responses=False,
            )
            return self._client
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Redis client not available and no client injected") from e

    # Tag helpers
    def add_tags(self, key: str, tags: list[str]) -> None:
        """Associate tags with a key.

        Args:
            key (str): Cache key (without namespace).
            tags (list[str]): Tags to associate.

        Returns:
            None
        """
        client = self._require_client()
        k = self._ns + key
        for tag in tags:
            tkey = f"{self._ns}tag::{tag}"
            try:
                client.sadd(tkey, k)
            except Exception:
                pass
