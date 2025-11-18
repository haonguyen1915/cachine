from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Optional

from cachine.core.types import HealthStatus
from cachine.strategies.eviction import LRUEviction

_MISSING = object()


class InMemoryCache:
    """In‑memory, sync‑only cache with TTL, counters, and tag invalidation.

    Features:
      - Namespace key prefixing for logical separation.
      - TTL management: ``set(ttl=...)``, ``expire``, ``expire_at``, ``touch``, ``ttl``, ``persist``.
      - Atomic-like counters: ``incr``/``decr`` with ``ttl_on_create`` semantics.
      - Tagging: associate keys with tags and invalidate by tag.
      - Optional eviction policy (LRU/LFU) when ``max_size`` is set.

    Args:
        max_size (int | None): Maximum number of keys to keep. When exceeded,
            the configured ``eviction_policy`` removes victims. If ``None``,
            no eviction is performed.
        eviction_policy (Any | None): Eviction policy instance implementing
            ``note_access``, ``note_remove``, and ``evict_one``. Defaults to
            :class:`~cachine.strategies.eviction.LRUEviction` when ``max_size`` is set.
        namespace (str | None): Optional namespace prefix added to every key.
            Useful to isolate tenants or test runs.
    """

    def __init__(self, *, max_size: Optional[int] = None, eviction_policy: Any | None = None, namespace: str | None = None) -> None:
        """Initialize an in-memory cache.

        - max_size: when set, enables eviction using ``eviction_policy`` (defaults
          to LRU). The size is the number of stored keys (not bytes).
        - eviction_policy: instance implementing ``note_access``, ``note_remove``,
          and ``evict_one`` (see strategies.eviction). When ``None`` and
          ``max_size`` is set, a default ``LRUEviction`` is used.
        - namespace: optional prefix added to all keys for logical separation.
        """
        self._store: dict[str, Any] = {}
        self._ttl: dict[str, Optional[datetime]] = {}
        self._ns = f"{namespace}:" if namespace else ""
        self._lock = RLock()
        self._max_size = max_size
        self._policy = eviction_policy or (LRUEviction() if max_size else None)
        # Tag indexes (namespaced)
        self._tag_to_keys: dict[str, set[str]] = {}
        self._key_to_tags: dict[str, set[str]] = {}

    # Basic ops
    def get(self, key: str, default: Any = None, serializer: Any = None) -> Any:  # pylint: disable=unused-argument
        """Get a value by key.

        Args:
            key (str): Cache key.
            default (Any, optional): Value to return when key is missing or expired.
            serializer (Any, optional): Ignored; present for interface parity.

        Returns:
            Any: The cached value or ``default`` if not present.
        """
        k = self._ns + key
        with self._lock:
            if k in self._store and not self._expired(k):
                if self._policy is not None:
                    self._policy.note_access(k)
                return self._store[k]
            # cleanup if expired
            self._cleanup_if_expired(k)
            return default

    def set(self, key: str, value: Any, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:  # pylint: disable=unused-argument
        """Set a value by key.

        Args:
            key (str): Cache key.
            value (Any): Value to store.
            ttl (int | timedelta | None): Optional time-to-live. ``<= 0`` deletes immediately.
            serializer (Any, optional): Ignored; present for interface parity.

        Returns:
            None
        """
        k = self._ns + key
        with self._lock:
            self._store[k] = value
            if ttl is None:
                self._ttl[k] = None
            else:
                seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
                if seconds <= 0:
                    # immediate expiry -> delete
                    self._remove_key(k)
                    return
                self._ttl[k] = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            if self._policy is not None:
                self._policy.note_access(k)
            self._evict_if_needed()

    def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if the key existed and was removed.
        """
        k = self._ns + key
        with self._lock:
            existed = k in self._store
            self._remove_key(k)
            return existed

    def exists(self, key: str) -> bool:
        """Check key existence.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if the key exists and is not expired.
        """
        k = self._ns + key
        with self._lock:
            if self._expired(k):
                self._cleanup_if_expired(k)
                return False
            return k in self._store

    def clear(self, dangerously_clear_all: bool = False) -> None:
        """Clear stored keys.

        Args:
            dangerously_clear_all (bool): When False and a namespace is configured,
                only keys within the namespace are removed. When True, the entire
                store and internal indices are cleared.

        Returns:
            None
        """
        with self._lock:
            if self._ns and not dangerously_clear_all:
                # Remove only keys in this namespace
                prefix = self._ns
                for k in list(self._store.keys()):
                    if k.startswith(prefix):
                        self._remove_key(k)
            else:
                self._store.clear()
                self._ttl.clear()
                self._tag_to_keys.clear()
                self._key_to_tags.clear()
                if self._policy is not None:
                    # reset policy tracking: drop and recreate
                    self._policy = LRUEviction() if self._max_size else None

    # Enrichment
    def get_or_set(self, key: str, factory: Any, ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None) -> Any:  # pylint: disable=unused-argument
        """Get or compute-and-set a value.

        Args:
            key (str): Cache key.
            factory (Any): Callable or value used to compute the value when missing.
            ttl (int | timedelta | None): Optional TTL for the stored value.
            jitter (int | None): Ignored in memory; for parity with other backends.

        Returns:
            Any: Existing value if present; otherwise the computed value.
        """
        sentinel = _MISSING
        val = self.get(key, default=sentinel)
        if val is not sentinel:
            return val
        if callable(factory):
            val = factory()
        else:
            val = factory
        self.set(key, val, ttl=ttl)
        return val

    # TTL management
    def expire(self, key: str, ttl: int | timedelta) -> bool:
        """Set a relative expiration.

        Args:
            key (str): Cache key.
            ttl (int | timedelta): Relative TTL; ``<= 0`` deletes the key.

        Returns:
            bool: True when the key existed (and was updated or removed).
        """
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
            if seconds <= 0:
                self._remove_key(k)
                return True
            self._ttl[k] = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            return True

    def expire_at(self, key: str, when: datetime) -> bool:
        """Set an absolute expiration (UTC).

        Args:
            key (str): Cache key.
            when (datetime): Absolute expiration time (UTC aware).

        Returns:
            bool: True when the key existed and the operation succeeded.
        """
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            if when <= datetime.now(timezone.utc):
                self._remove_key(k)
                return True
            self._ttl[k] = when
            return True

    def touch(self, key: str, ttl: Optional[int | timedelta] = None) -> bool:
        """Refresh TTL or assert presence.

        Args:
            key (str): Cache key.
            ttl (int | timedelta | None): New TTL. ``<= 0`` deletes the key. When None,
                the key is not modified and presence is reported.

        Returns:
            bool: True when the key exists (and was updated/removed when TTL provided).
        """
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            if ttl is None:
                # no TTL change
                return True
            seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
            if seconds <= 0:
                self._remove_key(k)
                return True
            self._ttl[k] = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            return True

    def ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL.

        Args:
            key (str): Cache key.

        Returns:
            int | None: Remaining seconds or ``None`` when no TTL or missing.
        """
        k = self._ns + key
        with self._lock:
            self._cleanup_if_expired(k)
            exp = self._ttl.get(k)
            if exp is None:
                return None
            delta = int((exp - datetime.now(timezone.utc)).total_seconds())
            if delta < 0:
                return None
            return delta

    def persist(self, key: str) -> bool:
        """Remove TTL from a key.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if the key existed with a TTL and it was removed.
        """
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            had_ttl = self._ttl.get(k) is not None
            self._ttl[k] = None
            return had_ttl

    # Counters
    def incr(self, key: str, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
        """Increment an integer value by ``delta``.

        Args:
            key (str): Cache key.
            delta (int): Increment amount.
            ttl_on_create (int | timedelta | None): TTL applied only when the key is created.

        Returns:
            int: The new integer value.
        """
        k = self._ns + key
        with self._lock:
            existed = k in self._store
            current = self._store.get(k, 0)
            new_val = int(current) + int(delta)
            self._store[k] = new_val
            if not existed and ttl_on_create is not None:
                seconds = int(ttl_on_create.total_seconds()) if isinstance(ttl_on_create, timedelta) else int(ttl_on_create)
                if seconds > 0:
                    self._ttl[k] = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            return new_val

    def decr(self, key: str, delta: int = 1) -> int:
        """Decrement an integer value.

        Args:
            key (str): Cache key.
            delta (int): Decrement amount.

        Returns:
            int: The new integer value after decrement.
        """
        return self.incr(key, delta=-int(delta))

    # Tags
    def invalidate_tags(self, tags: list[str]) -> int:
        """Invalidate keys by tags.

        Args:
            tags (list[str]): Tags to invalidate.

        Returns:
            int: Number of keys removed across all provided tags.
        """
        removed = 0
        with self._lock:
            for tag in tags:
                tkey = self._ns + tag
                keys = list(self._tag_to_keys.get(tkey, set()))
                for k in keys:
                    if k in self._store:
                        self._remove_key(k)
                        removed += 1
                # Clear tag entry
                self._tag_to_keys.pop(tkey, None)
        return removed

    # Tag assignment for decorator/strategies
    def add_tags(self, key: str, tags: list[str]) -> None:
        """Associate tags with a key for later invalidation.

        Args:
            key (str): Stored cache key.
            tags (list[str]): Tags to associate.

        Returns:
            None
        """
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return
            existing = self._key_to_tags.get(k, set())
            for tag in tags:
                tkey = self._ns + tag
                self._tag_to_keys.setdefault(tkey, set()).add(k)
                existing.add(tkey)
            self._key_to_tags[k] = existing

    # Health / lifecycle
    def ping(self) -> HealthStatus:
        """Check health.

        Returns:
            dict[str, Any]: Health payload with ``healthy``, ``latency_ms``, and ``backend``.
        """
        return {"healthy": True, "latency_ms": 0.0, "backend": "inmemory"}

    def ping_ok(self) -> bool:
        """Return a boolean health indicator.

        Returns:
            bool: True if the cache is considered healthy.
        """
        return True

    def close(self) -> None:  # no-op
        """Close resources (no-op for in‑memory cache)."""
        return None

    # Context manager
    def __enter__(self) -> InMemoryCache:
        """Enter context manager.

        Returns:
            InMemoryCache: This cache instance.
        """
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:  # no-op
        """Exit context manager (no cleanup required)."""
        return None

    # Helpers
    def _expired(self, k: str) -> bool:
        """Check internal expiry.

        Args:
            k (str): Fully-qualified internal key (with namespace).

        Returns:
            bool: True if the key is expired.
        """
        exp = self._ttl.get(k)
        return exp is not None and exp <= datetime.now(timezone.utc)

    def _cleanup_if_expired(self, k: str) -> None:
        """Remove a key if it is expired.

        Args:
            k (str): Fully-qualified internal key (with namespace).
        """
        if self._expired(k):
            self._remove_key(k)

    def _remove_key(self, k: str) -> None:
        """Delete a key and all metadata.

        Removes the value, TTL, and tag mappings, and notifies the eviction policy.

        Args:
            k (str): Fully-qualified internal key (with namespace).
        """
        # Remove key and any tag mappings
        self._store.pop(k, None)
        self._ttl.pop(k, None)
        tags = self._key_to_tags.pop(k, set())
        for t in tags:
            s = self._tag_to_keys.get(t)
            if s is not None:
                s.discard(k)
                if not s:
                    self._tag_to_keys.pop(t, None)
        if self._policy is not None:
            self._policy.note_remove(k)

    def _evict_if_needed(self) -> None:
        """Evict keys using the configured policy when above ``max_size``."""
        if self._max_size is None or self._policy is None:
            return
        while len(self._store) > self._max_size:
            victim = self._policy.evict_one()
            if not victim:
                break
            self._remove_key(victim)
