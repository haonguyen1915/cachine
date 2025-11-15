from __future__ import annotations

import functools
import inspect
import logging
import random
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any, NamedTuple, Optional

from ..utils.key_builder import default_key_builder, template_key_builder

_logger = logging.getLogger(__name__)


class KeyContext(NamedTuple):
    """Context passed to user key builders.

    Attributes:
        module (str): Module name containing the function.
        qualname (str): Qualified function name (may include class).
        full_name (str): Fully qualified path ``module.qualname``.
        version (str | None): Decorator version string, if provided.
    """

    module: str
    qualname: str
    full_name: str
    version: Optional[str]


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


def _build_key(  # pylint: disable=too-many-branches,too-many-nested-blocks
    fn: Callable[..., Any], key_builder: Optional[Any], version: Optional[str], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> str:
    """Build a stable cache key for a function call.

    Args:
        fn (Callable[..., Any]): Wrapped function.
        key_builder (Callable[..., str] | None): Optional custom key builder.
        version (str | None): Optional version string to append.
        args (tuple[Any, ...]): Positional arguments.
        kwargs (dict[str, Any]): Keyword arguments.

    Returns:
        str: Cache key string.
    """
    if key_builder is not None:
        # Support string templates directly; bind positional args to names for convenience
        template_builder = None
        bound_kwargs: Optional[dict[str, Any]] = None
        if isinstance(key_builder, str):
            template_builder = template_key_builder(key_builder)
            # Try to bind positional/keyword args to parameter names so templates like {uid}
            # work even when the function was called positionally, including kw-only params.
            try:
                sig = inspect.signature(fn)
                ba = sig.bind_partial(*args, **kwargs)
                merged = dict(ba.arguments)
                merged.update(kwargs)  # explicit kwargs precedence
                bound_kwargs = merged
            except Exception:  # pylint: disable=try-except-raise
                # Fallback: map positional args to KEYWORD_ONLY parameter names in order
                try:
                    sig = inspect.signature(fn)
                    kwonly_names = [
                        p.name for p in sig.parameters.values() if p.kind == inspect.Parameter.KEYWORD_ONLY and p.name not in kwargs
                    ]
                    if kwonly_names and len(args) <= len(kwonly_names):
                        mapped = {kwonly_names[i]: args[i] for i in range(len(args))}
                        merged = dict(kwargs)
                        merged.update(mapped)
                        bound_kwargs = merged
                    else:
                        bound_kwargs = None
                except Exception:
                    bound_kwargs = None
            # Use the wrapped builder moving forward
            key_builder = template_builder
        module = fn.__module__
        qualname = fn.__qualname__ if hasattr(fn, "__qualname__") else fn.__name__
        ctx = KeyContext(module=module, qualname=qualname, full_name=f"{module}.{qualname}", version=version)
        k = None
        try:
            # Prefer calling with context first
            if bound_kwargs is not None:
                k = key_builder(ctx, *args, **bound_kwargs)
            else:
                k = key_builder(ctx, *args, **kwargs)
        except TypeError as e:
            _logger.warning("key_builder(ctx, ...) failed for %r: %s; retrying without ctx", fn, e)
            try:
                k = key_builder(*args, **kwargs)
            except TypeError as e2:
                _logger.warning("key_builder(*args, **kwargs) failed for %r: %s; retrying args-only", fn, e2)
                try:
                    k = key_builder(*args)
                except Exception as e3:  # pragma: no cover - rare path
                    _logger.warning("key_builder final attempt failed for %r: %s; using default key", fn, e3)
                    k = None
        if k is None:
            func_name = f"{module}.{qualname}"
            k = default_key_builder(func_name, *args, **kwargs)
    else:
        module = fn.__module__
        qualname = fn.__qualname__ if hasattr(fn, "__qualname__") else fn.__name__
        func_name = f"{module}.{qualname}"

        # Smart handling for methods: avoid raw self/cls repr in keys
        norm_args: list[Any] = list(args)
        if "." in qualname and args:
            first = args[0]
            if inspect.isclass(first):
                cls = first
                norm_args[0] = f"cls:{cls.__module__}.{cls.__qualname__}"
            else:
                # Heuristic: treat as instance method only if first arg looks like an object instance
                primitive_types = (int, float, str, bytes, bytearray, bool, tuple, list, dict, set, frozenset)
                if not isinstance(first, primitive_types):
                    ident: Optional[str] = None
                    if hasattr(first, "__cache_key__") and callable(first.__cache_key__):
                        try:
                            ident = str(first.__cache_key__())
                        except Exception:
                            ident = None
                    elif hasattr(first, "cache_key"):
                        ck = first.cache_key
                        try:
                            ident = str(ck() if callable(ck) else ck)
                        except Exception:
                            ident = None
                    if not ident:
                        inst_id = getattr(first, "__cachine_id", None)
                        if not inst_id:
                            inst_id = uuid.uuid4().hex
                            try:
                                setattr(first, "__cachine_id", inst_id)
                            except Exception:
                                pass
                        ident = f"inst:{inst_id}"
                    norm_args[0] = ident

        k = default_key_builder(func_name, *norm_args, **kwargs)
    if version:
        k = f"{k}|v:{version}"
    _logger.debug(f"Built cache key: '{k}'")
    return k


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
    cache: Any,
    ttl: Optional[int | float] = None,
    *,
    jitter: Optional[int] = None,
    key_builder: Optional[Any] = None,
    condition: Optional[Callable[[Any], bool]] = None,
    version: Optional[str] = None,
    cache_none: bool = False,
    stale_ttl: Optional[int] = None,
    singleflight: bool = False,
    tags: Optional[Callable[..., list[str]] | list[str]] = None,
    tags_from_result: Optional[Callable[[Any], list[str]]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Cache-aside decorator with SWR, tags, and singleflight.

    Transparently caches function results using a provided cache. Works with both
    sync and async callables.

    Args:
        cache (Any): Cache instance implementing the sync or async interface.
        ttl (int | float | None): Freshness period in seconds.
        jitter (int | None): Max random seconds added to ``ttl`` to stagger refreshes.
        key_builder (Callable[..., str] | str | None): Custom key builder; either a callable
            receiving ``(ctx, *args, **kwargs)`` or a template string using ``str.format`` with
            placeholders like ``{0}``, ``{uid}``, and ``{ctx.full_name}``. Defaults to a stable
            key derived from function identity and normalized args/kwargs.
        condition (Callable[[Any], bool] | None): Predicate applied to the result; cache only if True.
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
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        is_coro = inspect.iscoroutinefunction(fn)
        sig = None
        try:
            sig = inspect.signature(fn)
        except Exception:
            sig = None

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

        def _store_value(key: str, value: Any) -> None:
            store_ttl, _fresh_ttl, fresh_until = _compute_ttls(ttl, jitter, stale_ttl)
            if ttl is None or stale_ttl is None:
                # No stale logic: store raw value
                cache.set(key, value, ttl=ttl)
            else:
                envelope = {"__cachine__": 1, "v": value, "fu": fresh_until}
                cache.set(key, envelope, ttl=store_ttl)

        def _get_cached_entry(key: str) -> tuple[bool, Any, Optional[float]]:
            """Read cached entry and freshness info.

            Args:
                key (str): Cache key.

            Returns:
                tuple[bool, Any, float | None]: ``(hit, value, fresh_until_ts)``.
            """
            val = cache.get(key, default=_MISSING)
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
            val = await cache.get(key, default=_MISSING)
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
                _store_value(key, result)
                # attach tags
                final_tags = _finalize_tags(result, args, kwargs)
                if final_tags and hasattr(cache, "add_tags"):
                    try:
                        cache.add_tags(key, final_tags)
                    except Exception:
                        pass
            finally:
                _sf.release(key)

        if is_coro:

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:  # pylint: disable=too-many-branches
                key = _build_key(fn, key_builder, version, args, kwargs)
                hit, value, fresh_until = await _aget_cached_entry(key)
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
                                        store_ttl, _, fresh_until2 = _compute_ttls(ttl, jitter, stale_ttl)
                                        envelope = {"__cachine__": 1, "v": result, "fu": fresh_until2}
                                        await cache.set(key, envelope, ttl=store_ttl)
                                        final_tags = _finalize_tags(result, args, kwargs)
                                        if final_tags and hasattr(cache, "add_tags"):
                                            maybe = cache.add_tags(key, final_tags)
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
                    store_ttl, _, fresh_until3 = _compute_ttls(ttl, jitter, stale_ttl)
                    if ttl is None or stale_ttl is None:
                        await cache.set(key, result, ttl=ttl)
                    else:
                        envelope = {"__cachine__": 1, "v": result, "fu": fresh_until3}
                        await cache.set(key, envelope, ttl=store_ttl)
                    final_tags = _finalize_tags(result, args, kwargs)
                    if final_tags and hasattr(cache, "add_tags"):
                        maybe = cache.add_tags(key, final_tags)
                        if inspect.isawaitable(maybe):
                            await maybe
                    return result
                finally:
                    if singleflight:
                        _sf.release(key)

            return async_wrapper

        @functools.wraps(fn)
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
                _store_value(key, result)
                final_tags = _finalize_tags(result, args, kwargs)
                if final_tags and hasattr(cache, "add_tags"):
                    try:
                        cache.add_tags(key, final_tags)
                    except Exception:
                        pass
                return result
            finally:
                if singleflight:
                    _sf.release(key)

        return sync_wrapper

    return decorator
