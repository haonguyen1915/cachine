from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

from cachine.core.types import HealthStatus
from cachine.strategies.eviction import LRUEviction
from cachine.utils._deprecations import (
    MISSING,
    resolve_renamed_kwarg,
    warn_deprecated_kwarg,
    warn_deprecated_method,
)

_MISSING = object()


class InMemoryCache:
    """In-memory, sync-only cache with TTL, counters, and tag invalidation.

    Features:
      - Namespace key prefixing for logical separation.
      - TTL management: ``set(ttl=...)``, ``expire``, ``expire_at``, ``touch``, ``ttl``, ``persist``.
      - Atomic-like counters: ``incr``/``decr`` with ``ttl_if_new`` semantics.
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

    def __init__(
        self,
        *,
        max_size: int | None = None,
        eviction_policy: Any | None = None,
        namespace: str | None = None,
        serializer: Any | None = None,
    ) -> None:
        self._store: dict[str, Any] = {}
        self._ttl: dict[str, datetime | None] = {}
        self._ns = f"{namespace}:" if namespace else ""
        self._lock = RLock()
        self._max_size = max_size
        self._policy = eviction_policy or (LRUEviction() if max_size else None)
        self._serializer = serializer
        # Tag indexes (namespaced)
        self._tag_to_keys: dict[str, set[str]] = {}
        self._key_to_tags: dict[str, set[str]] = {}

    # Basic ops
    def get(self, key: str, default: Any = None, *, serializer: Any = MISSING) -> Any:
        """Get a value by key.

        Args:
            key: Cache key.
            default: Value to return when the key is missing or expired.

        Returns:
            The cached value or ``default`` if not present.
        """
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="InMemoryCache.get",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        with self._lock:
            if k in self._store and not self._expired(k):
                if self._policy is not None:
                    self._policy.note_access(k)
                return self._store[k]
            self._cleanup_if_expired(k)
            return default

    def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | timedelta | None = None,
        serializer: Any = MISSING,
    ) -> None:
        """Set a value by key.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: Optional time-to-live. ``<= 0`` deletes immediately.
        """
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="InMemoryCache.set",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        with self._lock:
            self._store[k] = value
            if ttl is None:
                self._ttl[k] = None
            else:
                seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
                if seconds <= 0:
                    self._remove_key(k)
                    return
                self._ttl[k] = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            if self._policy is not None:
                self._policy.note_access(k)
            self._evict_if_needed()

    def delete(self, key: str) -> bool:
        """Delete a key. Returns ``True`` when the key existed."""
        k = self._ns + key
        with self._lock:
            existed = k in self._store
            self._remove_key(k)
            return existed

    def exists(self, key: str) -> bool:
        """Return ``True`` if the key exists and is not expired."""
        k = self._ns + key
        with self._lock:
            if self._expired(k):
                self._cleanup_if_expired(k)
                return False
            return k in self._store

    def clear(self, *, all: bool = False, dangerously_clear_all: Any = MISSING) -> None:
        """Clear stored keys.

        Args:
            all: When ``False`` and a namespace is configured, only keys within
                the namespace are removed. When ``True``, the entire store and
                internal indices are cleared.
            dangerously_clear_all: Deprecated alias for ``all``.
        """
        force = resolve_renamed_kwarg(
            old_name="dangerously_clear_all",
            new_name="all",
            old_value=dangerously_clear_all,
            new_value=all,
            owner="InMemoryCache.clear",
            new_default=False,
        )
        force = bool(force) if force is not None else False
        with self._lock:
            if self._ns and not force:
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
                    self._policy = LRUEviction() if self._max_size else None

    # Enrichment
    def get_or_set(  # pylint: disable=unused-argument
        self,
        key: str,
        factory: Any,
        *,
        ttl: int | timedelta | None = None,
        jitter: int | None = None,  # noqa: ARG002
    ) -> Any:
        """Get an existing value or compute, store, and return a new one."""
        val = self.get(key, default=_MISSING)
        if val is not _MISSING:
            return val
        val = factory() if callable(factory) else factory
        self.set(key, val, ttl=ttl)
        return val

    # TTL management
    def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        """Set a relative expiration. ``ttl <= 0`` deletes the key."""
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
        """Set an absolute expiration (UTC)."""
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            if when <= datetime.now(timezone.utc):
                self._remove_key(k)
                return True
            self._ttl[k] = when
            return True

    def touch(self, key: str, *, ttl: int | timedelta | None = None) -> bool:
        """Refresh TTL or assert presence."""
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            if ttl is None:
                return True
            seconds = int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
            if seconds <= 0:
                self._remove_key(k)
                return True
            self._ttl[k] = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            return True

    def ttl(self, key: str) -> int | None:
        """Get remaining TTL in seconds, or ``None`` if no TTL/missing."""
        k = self._ns + key
        with self._lock:
            self._cleanup_if_expired(k)
            exp = self._ttl.get(k)
            if exp is None:
                return None
            delta = int((exp - datetime.now(timezone.utc)).total_seconds())
            return delta if delta >= 0 else None

    def persist(self, key: str) -> bool:
        """Remove TTL from a key. Returns ``True`` if a TTL was cleared."""
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            had_ttl = self._ttl.get(k) is not None
            self._ttl[k] = None
            return had_ttl

    # Counters
    def incr(
        self,
        key: str,
        *,
        delta: int = 1,
        ttl_if_new: int | timedelta | None = None,
        ttl_on_create: Any = MISSING,
    ) -> int:
        """Increment an integer counter by ``delta``.

        ``ttl_if_new`` is applied only when the key is newly created.
        ``ttl_on_create`` is the deprecated alias.
        """
        effective_ttl = resolve_renamed_kwarg(
            old_name="ttl_on_create",
            new_name="ttl_if_new",
            old_value=ttl_on_create,
            new_value=ttl_if_new,
            owner="InMemoryCache.incr",
        )
        k = self._ns + key
        with self._lock:
            existed = k in self._store
            current = self._store.get(k, 0)
            new_val = int(current) + int(delta)
            self._store[k] = new_val
            if not existed and effective_ttl is not None:
                seconds = int(effective_ttl.total_seconds()) if isinstance(effective_ttl, timedelta) else int(effective_ttl)
                if seconds > 0:
                    self._ttl[k] = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            return new_val

    def decr(self, key: str, *, delta: int = 1) -> int:
        """Decrement an integer counter by ``delta``."""
        return self.incr(key, delta=-int(delta))

    # Tags
    def invalidate_tags(self, tags: list[str]) -> int:
        """Invalidate keys associated with the given tags. Returns removed count."""
        removed = 0
        with self._lock:
            for tag in tags:
                tkey = self._ns + tag
                keys = list(self._tag_to_keys.get(tkey, set()))
                for k in keys:
                    if k in self._store:
                        self._remove_key(k)
                        removed += 1
                self._tag_to_keys.pop(tkey, None)
        return removed

    def add_tags(self, key: str, tags: list[str], *, ttl: int | timedelta | None = None) -> None:  # noqa: ARG002  # pylint: disable=unused-argument
        """Associate ``tags`` with ``key``."""
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
    def health(self) -> HealthStatus:
        """Return cache health status."""
        return {"healthy": True, "latency_ms": 0.0, "backend": "inmemory"}

    def healthy(self) -> bool:
        """Return ``True`` if the cache is considered healthy."""
        return True

    # Deprecated aliases
    def ping(self) -> HealthStatus:
        """Deprecated alias for :meth:`health`."""
        warn_deprecated_method(name="ping", owner="InMemoryCache", replacement="health")
        return self.health()

    def ping_ok(self) -> bool:
        """Deprecated alias for :meth:`healthy`."""
        warn_deprecated_method(name="ping_ok", owner="InMemoryCache", replacement="healthy")
        return self.healthy()

    def close(self) -> None:
        """Close resources (no-op for in-memory)."""
        return None

    def get_stats(self) -> dict[str, Any] | None:
        """Return ``None``; middleware may override to provide stats."""
        return None

    # Context manager
    def __enter__(self) -> InMemoryCache:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    # Helpers
    def _expired(self, k: str) -> bool:
        exp = self._ttl.get(k)
        return exp is not None and exp <= datetime.now(timezone.utc)

    def _cleanup_if_expired(self, k: str) -> None:
        if self._expired(k):
            self._remove_key(k)

    def _remove_key(self, k: str) -> None:
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
        if self._max_size is None or self._policy is None:
            return
        while len(self._store) > self._max_size:
            victim = self._policy.evict_one()
            if not victim:
                break
            self._remove_key(victim)
