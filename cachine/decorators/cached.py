from __future__ import annotations

import inspect
import threading
import time
import random
from typing import Any, Callable, Optional, NamedTuple

from ..utils.key_builder import default_key_builder
from ..utils.helpers import to_seconds


class KeyContext(NamedTuple):
    module: str
    qualname: str
    full_name: str
    version: Optional[str]


class _Singleflight:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, threading.Event] = {}

    def acquire(self, key: str) -> tuple[bool, threading.Event]:
        with self._lock:
            ev = self._events.get(key)
            if ev is None:
                ev = threading.Event()
                self._events[key] = ev
                return True, ev  # leader
            return False, ev    # follower

    def release(self, key: str) -> None:
        with self._lock:
            ev = self._events.pop(key, None)
        if ev is not None:
            ev.set()


_sf = _Singleflight()
_MISSING = object()


def _build_key(fn: Callable[..., Any], key_builder: Optional[Callable[..., str]], version: Optional[str], args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if key_builder is not None:
        module = fn.__module__
        qualname = getattr(fn, "__qualname__", fn.__name__)
        ctx = KeyContext(module=module, qualname=qualname, full_name=f"{module}.{qualname}", version=version)
        try:
            # Prefer calling with context first
            k = key_builder(ctx, *args, **kwargs)  # type: ignore[misc]
        except TypeError:
            try:
                k = key_builder(*args, **kwargs)
            except TypeError:
                # key_builder might expect fewer args (e.g., self, x)
                k = key_builder(*args)  # type: ignore[misc]
    else:
        func_name = f"{fn.__module__}.{getattr(fn, '__qualname__', fn.__name__)}"
        k = default_key_builder(func_name, *args, **kwargs)
    if version:
        k = f"{k}|v:{version}"
    return k


def _compute_ttls(ttl: Optional[int | float], jitter: Optional[int], stale_ttl: Optional[int]) -> tuple[Optional[int], Optional[int], Optional[float]]:
    """Return (store_ttl, fresh_ttl, fresh_until_ts)"""
    if ttl is None:
        return None, None, None
    fresh = int(ttl)
    if jitter and jitter > 0:
        fresh += random.randint(0, int(jitter))
    store_ttl = fresh + (int(stale_ttl) if stale_ttl else 0)
    fresh_until = time.time() + fresh
    return int(store_ttl), int(fresh), float(fresh_until)


def cached(
    cache: Any,
    ttl: Optional[int | float] = None,
    *,
    jitter: Optional[int] = None,
    key_builder: Optional[Callable[..., str]] = None,
    condition: Optional[Callable[[Any], bool]] = None,
    version: Optional[str] = None,
    cache_none: bool = False,
    stale_ttl: Optional[int] = None,
    singleflight: bool = False,
    tags: Optional[Callable[..., list[str]] | list[str]] = None,
    tags_from_result: Optional[Callable[[Any], list[str]]] = None,
):
    """Cache-aside decorator with stale-while-revalidate, tags, and singleflight.

    Use this decorator to transparently cache function results using a provided cache.
    It supports both sync functions (e.g., with `InMemoryCache` or sync `RedisCache`) and
    async functions (with `AsyncRedisCache`).

    Parameters
    - cache: Cache instance that implements the documented interface (sync or async).
    - ttl: Base freshness time in seconds. During this period the value is considered fresh.
    - jitter: Optional max additional seconds randomly added to ttl to stagger refreshes.
    - key_builder: Optional callable to build the cache key from function args/kwargs.
      Defaults to a stable key: "module.qualname:args|kwargs".
    - condition: Optional predicate applied to the function result; cache only if True.
    - version: Optional version string to append to the key to bust old entries.
    - cache_none: Whether to cache None results. Defaults to False.
    - stale_ttl: Additional window (seconds) after ttl to serve stale data while a
      background refresh is triggered. Stored TTL = ttl(+jitter) + stale_ttl.
    - singleflight: Deduplicate concurrent identical calls so only one computation runs,
      and others wait for the result to be cached.
    - tags: Static list[str] or callable(args, kwargs)->list[str] to attach tags to the entry.
      Tags enable targeted invalidation via `cache.invalidate_tags([...])`.
    - tags_from_result: Callable(result)->list[str] to derive tags from the computed result.

    Behavior
    - Keying: If `key_builder` is not provided, a stable key is built from function
      identity plus normalized arguments. `version` is appended for explicit busting.
    - Fresh vs Stale: If `stale_ttl` is set, values are stored as an envelope containing
      the value and a "fresh-until" timestamp. Within [0, ttl] → serve fresh; within
      (ttl, ttl+stale_ttl] → serve stale and trigger background refresh; after ttl+stale_ttl →
      treat as miss and compute.
    - Singleflight: On misses, only one caller computes while others wait for an event and
      then read from cache. During the stale window, the stale value is returned immediately
      and a background refresh is started (leaders only).
    - Tags: When tags or tags_from_result are provided and the cache supports `add_tags`,
      tags are attached after a successful store so future `invalidate_tags` can purge the entry.

    Notes
    - For async functions, background refresh is scheduled via `asyncio.create_task`.
    - For sync functions, background refresh runs in a daemon thread. If you need strict
      control over concurrency across processes, consider adding distributed locks.
    - `ttl` may be combined with `jitter` to reduce stampedes; `stale_ttl` further protects
      tail latency by serving stale during refresh.
    """

    def decorator(fn: Callable[..., Any]):
        is_coro = inspect.iscoroutinefunction(fn)

        def _finalize_tags(result: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[str]:
            out: list[str] = []
            if tags:
                if callable(tags):
                    out.extend(tags(*args, **kwargs))  # type: ignore[misc]
                else:
                    out.extend(tags)
            if tags_from_result and (result is not None or cache_none):
                try:
                    out.extend(tags_from_result(result))
                except Exception:
                    pass
            # dedupe while preserving order
            seen = set()
            unique: list[str] = []
            for t in out:
                if t not in seen:
                    unique.append(t)
                    seen.add(t)
            return unique

        def _store_value(key: str, value: Any) -> None:
            store_ttl, fresh_ttl, fresh_until = _compute_ttls(ttl, jitter, stale_ttl)
            if ttl is None or stale_ttl is None:
                # No stale logic: store raw value
                cache.set(key, value, ttl=ttl)
            else:
                envelope = {"__cachine__": 1, "v": value, "fu": fresh_until}
                cache.set(key, envelope, ttl=store_ttl)

        def _get_cached_entry(key: str) -> tuple[bool, Any, Optional[float]]:
            """Returns (hit, value_or_envelope, fresh_until)."""
            val = cache.get(key, default=_MISSING)
            if val is _MISSING:
                return False, None, None
            if isinstance(val, dict) and val.get("__cachine__") == 1 and "fu" in val:
                return True, val.get("v"), float(val.get("fu"))
            return True, val, None

        def _background_refresh(key: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            leader, ev = _sf.acquire(key)
            if not leader:
                # another refresher is already running
                return
            try:
                result = fn(*args, **kwargs)
                if inspect.isawaitable(result):
                    # background refresh for async function is not handled in sync path
                    return
                if (result is None) and not cache_none:
                    return
                if condition is not None and not condition(result):
                    return
                _store_value(key, result)
                # attach tags
                final_tags = _finalize_tags(result, args, kwargs)
                if final_tags and hasattr(cache, "add_tags"):
                    try:
                        getattr(cache, "add_tags")(key, final_tags)
                    except Exception:
                        pass
            finally:
                _sf.release(key)

        if is_coro:
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = _build_key(fn, key_builder, version, args, kwargs)
                hit, value, fresh_until = _get_cached_entry(key)
                now = time.time()
                if hit:
                    if fresh_until is None or now <= fresh_until:
                        return value
                    # stale
                    if stale_ttl is not None and now <= fresh_until + int(stale_ttl):
                        # kick off background refresh if not already running
                        if singleflight:
                            leader, ev = _sf.acquire(key)
                            if leader:
                                # spawn task to refresh
                                async def _refresh():
                                    try:
                                        result = await fn(*args, **kwargs)
                                        if (result is None) and not cache_none:
                                            return
                                        if condition is not None and not condition(result):
                                            return
                                        store_ttl, _, fresh_until2 = _compute_ttls(ttl, jitter, stale_ttl)
                                        envelope = {"__cachine__": 1, "v": result, "fu": fresh_until2}
                                        await cache.set(key, envelope, ttl=store_ttl)
                                        final_tags = _finalize_tags(result, args, kwargs)
                                        if final_tags and hasattr(cache, "add_tags"):
                                            maybe = getattr(cache, "add_tags")(key, final_tags)
                                            if inspect.isawaitable(maybe):
                                                await maybe
                                    finally:
                                        _sf.release(key)

                                try:
                                    import asyncio

                                    asyncio.create_task(_refresh())
                                except Exception:
                                    _sf.release(key)
                        return value
                    # fully expired -> compute
                if singleflight:
                    leader, ev = _sf.acquire(key)
                    if not leader:
                        ev.wait()
                        # read from cache after leader done
                        hit2, value2, _ = _get_cached_entry(key)
                        if hit2:
                            return value2
                try:
                    result = await fn(*args, **kwargs)
                    if (result is None) and not cache_none:
                        return result
                    if condition is not None and not condition(result):
                        return result
                    store_ttl, _, fresh_until3 = _compute_ttls(ttl, jitter, stale_ttl)
                    if ttl is None or stale_ttl is None:
                        await cache.set(key, result, ttl=ttl)
                    else:
                        envelope = {"__cachine__": 1, "v": result, "fu": fresh_until3}
                        await cache.set(key, envelope, ttl=store_ttl)
                    final_tags = _finalize_tags(result, args, kwargs)
                    if final_tags and hasattr(cache, "add_tags"):
                        maybe = getattr(cache, "add_tags")(key, final_tags)
                        if inspect.isawaitable(maybe):
                            await maybe
                    return result
                finally:
                    if singleflight:
                        _sf.release(key)

            return async_wrapper

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _build_key(fn, key_builder, version, args, kwargs)
            hit, value, fresh_until = _get_cached_entry(key)
            now = time.time()
            if hit:
                if fresh_until is None or now <= fresh_until:
                    return value
                if stale_ttl is not None and now <= fresh_until + int(stale_ttl):
                    # trigger background refresh
                    if singleflight:
                        # attempt leader acquire for background refresh
                        t = threading.Thread(target=_background_refresh, args=(key, args, kwargs), daemon=True)
                        t.start()
                    return value
                # fully expired -> compute
            if singleflight:
                leader, ev = _sf.acquire(key)
                if not leader:
                    ev.wait()
                    hit2, value2, _ = _get_cached_entry(key)
                    if hit2:
                        return value2
            try:
                result = fn(*args, **kwargs)
                if (result is None) and not cache_none:
                    return result
                if condition is not None and not condition(result):
                    return result
                _store_value(key, result)
                final_tags = _finalize_tags(result, args, kwargs)
                if final_tags and hasattr(cache, "add_tags"):
                    try:
                        getattr(cache, "add_tags")(key, final_tags)
                    except Exception:
                        pass
                return result
            finally:
                if singleflight:
                    _sf.release(key)

        return sync_wrapper

    return decorator
