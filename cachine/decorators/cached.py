from __future__ import annotations

import functools
import inspect
import logging
import random
import threading
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any, Optional, Union, cast

from cachine.core.types import AsyncCache, Cache, CacheLike

# from cachine.utils.key_builder import default_key_builder, template_key_builder
from ._utils import build_cache_key

# Type aliases for cache factories
CacheFactory = Callable[[], Cache]
AsyncCacheFactory = Callable[[], AsyncCache]
AnyCacheFactory = Union[CacheFactory, AsyncCacheFactory, Callable[[], CacheLike]]

_logger = logging.getLogger(__name__)


class _Singleflight:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, threading.Event] = {}

    def acquire(self, key: str) -> tuple[bool, threading.Event]:
        """Acquire leader/follower role for a key.

        Args:
            key (str): Singleflight group key.

        Returns:
            tuple[bool, threading.Event]: ``(is_leader, event)`` where followers
            can wait on ``event`` for leader completion.
        """
        with self._lock:
            ev = self._events.get(key)
            if ev is None:
                ev = threading.Event()
                self._events[key] = ev
                return True, ev  # leader
            return False, ev  # follower

    def release(self, key: str) -> None:
        """Signal completion for a key group and release waiters.

        Args:
            key (str): Singleflight group key.
        """
        with self._lock:
            ev = self._events.pop(key, None)
        if ev is not None:
            ev.set()


_sf = _Singleflight()
_MISSING = object()
_CACHE_UNRESOLVED = object()


# def _build_key(  # pylint: disable=too-many-branches,too-many-nested-blocks
#     fn: Callable[..., Any],
#     key_builder: Optional[str | Callable[..., str]],
#     version: Optional[str],
#     args: tuple[Any, ...],
#     kwargs: dict[str, Any],
# ) -> str:
#     """Build a stable cache key for a function call.
#
#     Args:
#         fn (Callable[..., Any]): Wrapped function.
#         key_builder (str | Callable[..., str] | None): Optional custom key builder;
#             either a string template or a callable.
#         version (str | None): Optional version string to append.
#         args (tuple[Any, ...]): Positional arguments.
#         kwargs (dict[str, Any]): Keyword arguments.
#
#     Returns:
#         str: Cache key string.
#     """
#     if key_builder is not None:
#         # Support string templates directly; bind positional args to names for convenience
#         template_builder = None
#         bound_kwargs: Optional[dict[str, Any]] = None
#         if isinstance(key_builder, str):
#             template_builder = template_key_builder(key_builder)
#             # Try to bind positional/keyword args to parameter names so templates like {uid}
#             # work even when the function was called positionally, including kw-only params.
#             try:
#                 sig = inspect.signature(fn)
#                 ba = sig.bind_partial(*args, **kwargs)
#                 merged = dict(ba.arguments)
#                 merged.update(kwargs)  # explicit kwargs precedence
#                 bound_kwargs = merged
#             except Exception:  # pylint: disable=try-except-raise
#                 # Fallback: map positional args to KEYWORD_ONLY parameter names in order
#                 try:
#                     sig = inspect.signature(fn)
#                     kwonly_names = [
#                         p.name for p in sig.parameters.values() if p.kind == inspect.Parameter.KEYWORD_ONLY and p.name not in kwargs
#                     ]
#                     if kwonly_names and len(args) <= len(kwonly_names):
#                         mapped = {kwonly_names[i]: args[i] for i in range(len(args))}
#                         merged = dict(kwargs)
#                         merged.update(mapped)
#                         bound_kwargs = merged
#                     else:
#                         bound_kwargs = None
#                 except Exception:
#                     bound_kwargs = None
#             # Use the wrapped builder moving forward
#             key_builder = template_builder
#         module = fn.__module__
#         qualname = fn.__qualname__ if hasattr(fn, "__qualname__") else fn.__name__
#         ctx = KeyContext(module=module, qualname=qualname, full_name=f"{module}.{qualname}", version=version)
#         k = None
#         try:
#             # Prefer calling with context first
#             if bound_kwargs is not None:
#                 k = key_builder(ctx, *args, **bound_kwargs)
#             else:
#                 k = key_builder(ctx, *args, **kwargs)
#         except TypeError as e:
#             _logger.warning("key_builder(ctx, ...) failed for %r: %s; retrying without ctx", fn, e)
#             try:
#                 k = key_builder(*args, **kwargs)
#             except TypeError as e2:
#                 _logger.warning("key_builder(*args, **kwargs) failed for %r: %s; retrying args-only", fn, e2)
#                 try:
#                     k = key_builder(*args)
#                 except Exception as e3:  # pragma: no cover - rare path
#                     _logger.warning("key_builder final attempt failed for %r: %s; using default key", fn, e3)
#                     k = None
#         if k is None:
#             func_name = f"{module}.{qualname}"
#             k = default_key_builder(func_name, *args, **kwargs)
#     else:
#         module = fn.__module__
#         qualname = fn.__qualname__ if hasattr(fn, "__qualname__") else fn.__name__
#         func_name = f"{module}.{qualname}"
#
#         # Smart handling for methods: avoid raw self/cls repr in keys
#         norm_args: list[Any] = list(args)
#         if "." in qualname and args:
#             first = args[0]
#             if inspect.isclass(first):
#                 cls = first
#                 norm_args[0] = f"cls:{cls.__module__}.{cls.__qualname__}"
#             else:
#                 # Heuristic: treat as instance method only if first arg looks like an object instance
#                 primitive_types = (int, float, str, bytes, bytearray, bool, tuple, list, dict, set, frozenset)
#                 if not isinstance(first, primitive_types):
#                     ident: Optional[str] = None
#                     if hasattr(first, "__cache_key__") and callable(first.__cache_key__):
#                         try:
#                             ident = str(first.__cache_key__())
#                         except Exception:
#                             ident = None
#                     elif hasattr(first, "cache_key"):
#                         ck = first.cache_key
#                         try:
#                             ident = str(ck() if callable(ck) else ck)
#                         except Exception:
#                             ident = None
#                     if not ident:
#                         inst_id = getattr(first, "__cachine_id", None)
#                         if not inst_id:
#                             inst_id = uuid.uuid4().hex
#                             try:
#                                 setattr(first, "__cachine_id", inst_id)
#                             except Exception:
#                                 pass
#                         ident = f"inst:{inst_id}"
#                     norm_args[0] = ident
#
#         k = default_key_builder(func_name, *norm_args, **kwargs)
#     if version:
#         k = f"{k}|v:{version}"
#     _logger.debug(f"Built cache key: '{k}'")
#     return k


def _compute_ttls(
    ttl: Optional[int | float], jitter: Optional[int], stale_ttl: Optional[int]
) -> tuple[Optional[int], Optional[int], Optional[float]]:
    """Compute storage and freshness TTLS.

    Args:
        ttl (int | float | None): Base freshness TTL in seconds.
        jitter (int | None): Optional max random jitter seconds added to ``ttl``.
        stale_ttl (int | None): Additional stale-while-revalidate window.

    Returns:
        tuple[Optional[int], Optional[int], Optional[float]]: A tuple of
        ``(store_ttl, fresh_ttl, fresh_until_ts)`` where ``store_ttl`` is the
        value stored in the backend, ``fresh_ttl`` is the freshness window, and
        ``fresh_until_ts`` is a UNIX timestamp when the value becomes stale.
    """
    if ttl is None:
        return None, None, None
    fresh = int(ttl)
    if jitter and jitter > 0:
        fresh += random.randint(0, int(jitter))
    store_ttl = fresh + (int(stale_ttl) if stale_ttl else 0)
    fresh_until = time.time() + fresh
    return int(store_ttl), int(fresh), float(fresh_until)


def cached(
    cache: CacheLike | Callable[..., CacheLike] | None,
    *,
    ttl: Optional[Callable[..., int | float] | int | float] = None,
    jitter: Optional[int] = None,
    key_builder: Optional[str | Callable[..., str]] = None,
    condition: Optional[Callable[[Any], bool]] = None,
    enabled: Optional[bool | Callable[..., bool]] = True,
    version: Optional[str] = None,
    cache_none: bool = False,
    stale_ttl: Optional[int] = None,
    singleflight: bool = False,
    tags: Optional[Callable[..., list[str]] | list[str]] = None,
    tags_from_result: Optional[Callable[[Any], list[str]]] = None,
    tag_ttl: Optional[int | timedelta] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Cache-aside decorator with SWR, tags, and singleflight.

    Transparently caches function results using a provided cache. Works with both
    sync and async callables.

    Args:
        cache (CacheLike | Callable[..., CacheLike] | None): Cache instance implementing
            the sync or async interface, or a callable that returns such an instance.
            If a callable is provided, it is resolved lazily on first function call
            (not at import/decorator time) to avoid early initialization order issues.
        ttl (Callable[..., int | float] | int | float | None): Freshness period in seconds.
            Can be a static value (int/float) or a callable that receives the function's
            arguments and returns a dynamic TTL. Falls back to None on callable errors.
        jitter (int | None): Max random seconds added to ``ttl`` to stagger refreshes.
        key_builder (Callable[..., str] | str | None): Custom key builder; either a callable
            receiving ``(ctx, *args, **kwargs)`` or a template string using ``str.format`` with
            placeholders like ``{0}``, ``{uid}``, and ``{ctx.full_name}``. Defaults to a stable
            key derived from function identity and normalized args/kwargs.
        condition (Callable[[Any], bool] | None): Predicate applied to the result; cache only if True.
        enabled (bool | Callable[..., bool]): Whether caching is enabled. Can be a static boolean
            or a callable that receives the function's arguments and returns True to enable caching
            or False to bypass it. Falls back to True on callable errors.
        version (str | None): Version string appended to cache key for explicit busting.
        cache_none (bool): Whether to cache ``None`` results. Defaults to False.
        stale_ttl (int | None): Additional stale window during which stale data is served
            while a background refresh is triggered. Stored TTL = ttl(+jitter) + stale_ttl.
        singleflight (bool): Deduplicate concurrent identical calls so that only one
            computes while followers wait.
        tags (Callable[..., list[str]] | list[str] | None): Static list or callable to attach tags.
        tags_from_result (Callable[[Any], list[str]] | None): Derive tags from the computed result.

    Returns:
        Callable[[Callable[..., Any]], Callable[..., Any]]: A decorator that wraps the function.

    Notes:
        - Keying: If ``key_builder`` is not provided, a stable key is built from function
          identity and normalized arguments. ``version`` is appended for busting.
        - Fresh vs Stale: With ``stale_ttl``, values are stored as an envelope containing
          the value and a "fresh-until" timestamp. Within [0, ttl] returns fresh; within
          (ttl, ttl+stale_ttl] returns stale and triggers background refresh; afterwards a miss.
        - Singleflight: On misses, only one caller computes while others wait. During the
          stale window, the stale value is returned immediately and a refresh is scheduled.
        - Tags: When tags are provided and the cache supports ``add_tags``, tags are attached
          after storing so future ``invalidate_tags`` can purge the entry.
        - Dynamic TTL: When ``ttl`` is a callable, it receives the function arguments and returns
          a TTL value per-call. Example: ``ttl=lambda user_id, premium=False: 3600 if premium else 60``

    Examples:
        Static TTL:

        >>> @cached(cache=cache, ttl=60)
        ... def get_user(user_id: int):
        ...     return fetch_user(user_id)

        Dynamic TTL based on function arguments:

        >>> @cached(cache=cache, ttl=lambda user_id, premium=False: 3600 if premium else 60)
        ... def get_user(user_id: int, premium: bool = False):
        ...     return fetch_user(user_id)
        >>> get_user(123)  # Uses TTL=60 (default premium=False)
        >>> get_user(456, premium=True)  # Uses TTL=3600
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        is_coro = inspect.iscoroutinefunction(fn)
        sig = None
        try:
            sig = inspect.signature(fn)
        except Exception:
            sig = None

        # Lazily resolve cache on first call to avoid early initialization.
        resolved_cache: CacheLike | None | object = _CACHE_UNRESOLVED
        _resolve_lock = threading.Lock()

        def _resolve_cache() -> CacheLike | None:
            nonlocal resolved_cache
            if resolved_cache is _CACHE_UNRESOLVED:
                with _resolve_lock:
                    if resolved_cache is _CACHE_UNRESOLVED:
                        try:
                            if cache is None:
                                resolved_cache = None
                            elif callable(cache):
                                resolved_cache = cache()
                            else:
                                resolved_cache = cache
                        except Exception as e:  # pragma: no cover - rare
                            _logger.error("Failed to resolve cache for %r: %s; falling back to pass-through", fn, e)
                            resolved_cache = None
            # Return None if cache couldn't be resolved, otherwise return the resolved cache
            # Type narrowing: after resolution, resolved_cache is either CacheLike or None
            return cast(Optional[CacheLike], None if resolved_cache is None else resolved_cache)

        def _finalize_tags(result: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[str]:
            out: list[str] = []
            if tags:
                if callable(tags):
                    out.extend(tags(*args, **kwargs))
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

        def _store_value(key: str, value: Any, effective_ttl: Optional[int | float], cache_instance: CacheLike) -> None:
            store_ttl, _fresh_ttl, fresh_until = _compute_ttls(effective_ttl, jitter, stale_ttl)
            if effective_ttl is None or stale_ttl is None:
                # No stale logic: store raw value
                # Normalize ttl to expected type (int | timedelta | None)
                ttl_arg = int(effective_ttl) if isinstance(effective_ttl, float) else effective_ttl
                cache_instance.set(key, value, ttl=ttl_arg)
            else:
                envelope = {"__cachine__": 1, "v": value, "fu": fresh_until}
                cache_instance.set(key, envelope, ttl=store_ttl)

        def _get_cached_entry(key: str) -> tuple[bool, Any, Optional[float]]:
            """Read cached entry and freshness info.

            Args:
                key (str): Cache key.

            Returns:
                tuple[bool, Any, float | None]: ``(hit, value, fresh_until_ts)``.
            """
            val = cast(CacheLike, resolved_cache).get(key, default=_MISSING)
            if val is _MISSING:
                return False, None, None
            if isinstance(val, dict) and val.get("__cachine__") == 1 and "fu" in val:
                fu_val = val.get("fu")
                return True, val.get("v"), float(fu_val) if fu_val is not None else None
            return True, val, None

        async def _aget_cached_entry(key: str) -> tuple[bool, Any, Optional[float]]:
            """Async version of ``_get_cached_entry``.

            Args:
                key (str): Cache key.

            Returns:
                tuple[bool, Any, float | None]: ``(hit, value, fresh_until_ts)``.
            """
            val = await cast(CacheLike, resolved_cache).get(key, default=_MISSING)
            if val is _MISSING:
                return False, None, None
            if isinstance(val, dict) and val.get("__cachine__") == 1 and "fu" in val:
                fu_val = val.get("fu")
                return True, val.get("v"), float(fu_val) if fu_val is not None else None
            return True, val, None

        def _background_refresh(key: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            leader, _ = _sf.acquire(key)
            if not leader:
                # another refresher is already running
                return
            try:
                try:
                    result = fn(*args, **kwargs)
                except TypeError:
                    if sig is not None:
                        try:
                            ba = sig.bind_partial(*args, **kwargs)
                            result = fn(**ba.arguments)
                        except Exception:
                            # Attempt to map positional args to KEYWORD_ONLY parameters
                            try:
                                kwonly = [p.name for p in sig.parameters.values() if p.kind == inspect.Parameter.KEYWORD_ONLY]
                                if len(args) <= len(kwonly):
                                    merged = dict(kwargs)
                                    for i, name in enumerate(kwonly[: len(args)]):
                                        merged[name] = args[i]
                                    result = fn(**merged)
                                else:  # noqa: E722 - re-raise original
                                    raise
                            except Exception:  # pylint: disable=try-except-raise
                                raise
                    else:  # noqa: E722 - re-raise original
                        raise
                if inspect.isawaitable(result):
                    # background refresh for async function is not handled in sync path
                    return
                if (result is None) and not cache_none:
                    return
                if condition is not None and not condition(result):
                    return
                effective_ttl = _compute_effective_ttl(args, kwargs)
                rc_cached = _resolve_cache()
                if rc_cached is not None:
                    _store_value(key, result, effective_ttl, rc_cached)
                    # attach tags
                    final_tags = _finalize_tags(result, args, kwargs)
                    if final_tags and hasattr(rc_cached, "add_tags"):
                        try:
                            rc_cached.add_tags(key, final_tags, ttl=tag_ttl)
                        except Exception:
                            pass
            finally:
                _sf.release(key)

        def _compute_effective_ttl(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Optional[int | float]:
            """Compute the effective TTL for this call.

            Args:
                args: Function positional arguments.
                kwargs: Function keyword arguments.

            Returns:
                The TTL value (int/float) or None.
            """
            if ttl is None:
                return None
            if callable(ttl):
                try:
                    # Try calling with args/kwargs
                    return ttl(*args, **kwargs)
                except TypeError:
                    # Try without kwargs if signature mismatch
                    try:
                        return ttl(*args)
                    except Exception:
                        # Fall back to None on any error
                        _logger.warning("ttl callable failed for %r; falling back to None", fn)
                        return None
                except Exception:
                    _logger.warning("ttl callable failed for %r; falling back to None", fn)
                    return None
            return ttl

        def _call_enabled_predicate(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
            """Evaluate the enabled predicate for this call.

            Args:
                args: Function positional arguments.
                kwargs: Function keyword arguments.

            Returns:
                True if caching is enabled, False otherwise.
            """
            if enabled is None:
                return True
            if isinstance(enabled, bool):
                return enabled
            # At this point, enabled must be callable (checked above: not None, not bool)
            try:
                # Try calling with args/kwargs
                return bool(enabled(*args, **kwargs))
            except TypeError:
                # Try without kwargs if signature mismatch
                try:
                    return bool(enabled(*args))
                except Exception:
                    # Fall back to True on any error
                    _logger.warning("enabled callable failed for %r; falling back to True", fn)
                    return True
            except Exception:
                _logger.warning("enabled callable failed for %r; falling back to True", fn)
                return True

        if is_coro:

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:  # pylint: disable=too-many-branches
                # Early predicate: optionally bypass cache entirely
                if not _call_enabled_predicate(args, kwargs):
                    _logger.debug("Cache SKIP (disabled) for %s", fn.__qualname__)
                    return await fn(*args, **kwargs)
                # Resolve cache lazily; if unavailable, pass through
                rc = _resolve_cache()
                if rc is None:
                    _logger.debug("Cache SKIP (no cache) for %s", fn.__qualname__)
                    return await fn(*args, **kwargs)
                key = build_cache_key(fn, key_builder, version, args, kwargs)
                hit, value, fresh_until = await _aget_cached_entry(key)
                now = time.time()
                if hit:
                    if fresh_until is None or now <= fresh_until:
                        _logger.debug("Cache HIT (fresh) for %s, key=%s", fn.__name__, key)
                        return value
                    # stale
                    if stale_ttl is not None and now <= fresh_until + int(stale_ttl):
                        _logger.debug("Cache HIT (stale, refreshing) for %s, key=%s", fn.__name__, key)
                        # kick off background refresh if not already running
                        if singleflight:
                            leader, ev = _sf.acquire(key)
                            if leader:
                                # spawn task to refresh
                                async def _refresh() -> None:
                                    try:
                                        try:
                                            result = await fn(*args, **kwargs)
                                        except TypeError:
                                            if sig is not None:
                                                try:
                                                    ba = sig.bind_partial(*args, **kwargs)
                                                    result = await fn(**ba.arguments)
                                                except Exception:
                                                    # Attempt KEYWORD_ONLY mapping
                                                    kwonly = [
                                                        p.name for p in sig.parameters.values() if p.kind == inspect.Parameter.KEYWORD_ONLY
                                                    ]
                                                    if len(args) <= len(kwonly):
                                                        merged = dict(kwargs)
                                                        for i, name in enumerate(kwonly[: len(args)]):
                                                            merged[name] = args[i]
                                                        result = await fn(**merged)
                                                    else:
                                                        raise
                                            else:  # noqa: E722 - re-raise original
                                                raise
                                        if (result is None) and not cache_none:
                                            return
                                        if condition is not None and not condition(result):
                                            return
                                        effective_ttl = _compute_effective_ttl(args, kwargs)
                                        store_ttl, _, fresh_until2 = _compute_ttls(effective_ttl, jitter, stale_ttl)
                                        envelope = {"__cachine__": 1, "v": result, "fu": fresh_until2}
                                        maybe_set = rc.set(key, envelope, ttl=store_ttl)
                                        if inspect.isawaitable(maybe_set):
                                            await cast(Any, maybe_set)
                                        final_tags = _finalize_tags(result, args, kwargs)
                                        if final_tags and hasattr(rc, "add_tags"):
                                            maybe = rc.add_tags(key, final_tags, ttl=tag_ttl)
                                            if inspect.isawaitable(maybe):
                                                await cast(Any, maybe)
                                    finally:
                                        _sf.release(key)

                                try:
                                    import asyncio

                                    asyncio.create_task(_refresh())
                                except Exception:
                                    _sf.release(key)
                        return value
                    # fully expired -> compute
                _logger.debug("Cache MISS for %s, key=%s", fn.__name__, key)
                if singleflight:
                    leader, ev = _sf.acquire(key)
                    if not leader:
                        try:
                            import asyncio

                            await asyncio.to_thread(ev.wait)
                        except Exception:
                            ev.wait()
                        # read from cache after leader done
                        hit2, value2, _ = await _aget_cached_entry(key)
                        if hit2:
                            return value2
                try:
                    try:
                        result = await fn(*args, **kwargs)
                    except TypeError:
                        if sig is not None:
                            try:
                                ba = sig.bind_partial(*args, **kwargs)
                                result = await fn(**ba.arguments)
                            except Exception:
                                # Attempt KEYWORD_ONLY mapping
                                kwonly = [p.name for p in sig.parameters.values() if p.kind == inspect.Parameter.KEYWORD_ONLY]
                                if len(args) <= len(kwonly):
                                    merged = dict(kwargs)
                                    for i, name in enumerate(kwonly[: len(args)]):
                                        merged[name] = args[i]
                                    result = await fn(**merged)
                                else:
                                    raise
                        else:  # noqa: E722 - re-raise original
                            raise
                    if (result is None) and not cache_none:
                        return result
                    if condition is not None and not condition(result):
                        return result
                    effective_ttl = _compute_effective_ttl(args, kwargs)
                    store_ttl, _, fresh_until3 = _compute_ttls(effective_ttl, jitter, stale_ttl)
                    if effective_ttl is None or stale_ttl is None:
                        ttl_arg = int(effective_ttl) if isinstance(effective_ttl, float) else effective_ttl
                        maybe_set2 = rc.set(key, result, ttl=ttl_arg)
                        if inspect.isawaitable(maybe_set2):
                            await cast(Any, maybe_set2)
                    else:
                        envelope = {"__cachine__": 1, "v": result, "fu": fresh_until3}
                        maybe_set3 = rc.set(key, envelope, ttl=store_ttl)
                        if inspect.isawaitable(maybe_set3):
                            await cast(Any, maybe_set3)
                    final_tags = _finalize_tags(result, args, kwargs)
                    if final_tags and hasattr(rc, "add_tags"):
                        maybe = rc.add_tags(key, final_tags, ttl=tag_ttl)
                        try:
                            if inspect.isawaitable(maybe):
                                await cast(Any, maybe)
                        except Exception:
                            pass
                    return result
                finally:
                    if singleflight:
                        _sf.release(key)

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _call_enabled_predicate(args, kwargs):
                _logger.debug("Cache SKIP (disabled) for %s", fn.__name__)
                return fn(*args, **kwargs)
            rc = _resolve_cache()
            if rc is None:
                _logger.debug("Cache SKIP (no cache) for %s", fn.__name__)
                return fn(*args, **kwargs)
            key = build_cache_key(fn, key_builder, version, args, kwargs)
            hit, value, fresh_until = _get_cached_entry(key)
            now = time.time()
            if hit:
                if fresh_until is None or now <= fresh_until:
                    _logger.debug("Cache HIT (fresh) for %s, key=%s", fn.__name__, key)
                    return value
                if stale_ttl is not None and now <= fresh_until + int(stale_ttl):
                    _logger.debug("Cache HIT (stale, refreshing) for %s, key=%s", fn.__name__, key)
                    # trigger background refresh
                    if singleflight:
                        # attempt leader acquire for background refresh
                        t = threading.Thread(target=_background_refresh, args=(key, args, kwargs), daemon=True)
                        t.start()
                    return value
                # fully expired -> compute
            _logger.debug("Cache MISS for %s, key=%s", fn.__name__, key)
            if singleflight:
                leader, ev = _sf.acquire(key)
                if not leader:
                    ev.wait()
                    hit2, value2, _ = _get_cached_entry(key)
                    if hit2:
                        return value2
            try:
                try:
                    result = fn(*args, **kwargs)
                except TypeError:
                    if sig is not None:
                        try:
                            ba = sig.bind_partial(*args, **kwargs)
                            result = fn(**ba.arguments)
                        except Exception:
                            # Attempt KEYWORD_ONLY mapping
                            kwonly = [p.name for p in sig.parameters.values() if p.kind == inspect.Parameter.KEYWORD_ONLY]
                            if len(args) <= len(kwonly):
                                merged = dict(kwargs)
                                for i, name in enumerate(kwonly[: len(args)]):
                                    merged[name] = args[i]
                                result = fn(**merged)
                            else:
                                raise
                    else:
                        raise
                if (result is None) and not cache_none:
                    return result
                if condition is not None and not condition(result):
                    return result
                effective_ttl = _compute_effective_ttl(args, kwargs)
                _store_value(key, result, effective_ttl, rc)
                final_tags = _finalize_tags(result, args, kwargs)
                if final_tags and hasattr(rc, "add_tags"):
                    try:
                        rc.add_tags(key, final_tags, ttl=tag_ttl)
                    except Exception:
                        pass
                return result
            finally:
                if singleflight:
                    _sf.release(key)

        return sync_wrapper

    return decorator
