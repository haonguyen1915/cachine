from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Optional

from ...strategies.eviction import LRUEviction

_MISSING = object()


class InMemoryCache:
    """A minimal, sync-only in-memory cache scaffold.

    Note: TTL, tags, and locks are not fully implemented in this stub.
    This is provided to align with the documented interface and allow
    quick experimentation. Replace with a full implementation later.
    """

    def __init__(self, *, max_size: Optional[int] = None, eviction_policy: Any | None = None, namespace: str | None = None) -> None:
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
    def get(self, key: str, default: Any = None, *, serializer: Any = None) -> Any:  # pylint: disable=unused-argument
        k = self._ns + key
        with self._lock:
            if k in self._store and not self._expired(k):
                if self._policy is not None:
                    self._policy.note_access(k)
                return self._store[k]
            # cleanup if expired
            self._cleanup_if_expired(k)
            return default

    def set(self, key: str, value: Any, *, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:  # pylint: disable=unused-argument
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
        k = self._ns + key
        with self._lock:
            existed = k in self._store
            self._remove_key(k)
            return existed

    def exists(self, key: str) -> bool:
        k = self._ns + key
        with self._lock:
            if self._expired(k):
                self._cleanup_if_expired(k)
                return False
            return k in self._store

    def clear(self, *, dangerously_clear_all: bool = False) -> None:
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
    def get_or_set(self, key: str, factory: Any, *, ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None) -> Any:  # pylint: disable=unused-argument
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
    def expire(self, key: str, *, ttl: int | timedelta) -> bool:
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
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            if when <= datetime.now(timezone.utc):
                self._remove_key(k)
                return True
            self._ttl[k] = when
            return True

    def touch(self, key: str, *, ttl: Optional[int | timedelta] = None) -> bool:
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
        k = self._ns + key
        with self._lock:
            if k not in self._store:
                return False
            had_ttl = self._ttl.get(k) is not None
            self._ttl[k] = None
            return had_ttl

    # Counters
    def incr(self, key: str, *, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
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

    def decr(self, key: str, *, delta: int = 1) -> int:
        return self.incr(key, delta=-int(delta))

    # Tags
    def invalidate_tags(self, tags: list[str]) -> int:
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
    def ping(self) -> dict[str, Any]:
        return {"healthy": True, "latency_ms": 0.0, "backend": "inmemory"}

    def ping_ok(self) -> bool:
        return True

    def close(self) -> None:  # no-op
        return None

    # Context manager
    def __enter__(self) -> InMemoryCache:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:  # no-op
        return None

    # Helpers
    def _expired(self, k: str) -> bool:
        exp = self._ttl.get(k)
        return exp is not None and exp <= datetime.now(timezone.utc)

    def _cleanup_if_expired(self, k: str) -> None:
        if self._expired(k):
            self._remove_key(k)

    def _remove_key(self, k: str) -> None:
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
        if self._max_size is None or self._policy is None:
            return
        while len(self._store) > self._max_size:
            victim = self._policy.evict_one()
            if not victim:
                break
            self._remove_key(victim)
