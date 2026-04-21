"""Cache middleware builders.

The builder's single responsibility is to compose middleware layers around a
base cache instance. URL parsing lives on the backend classes themselves
(``RedisCache.from_url``, ``SQLiteCache.from_url``).

Example::

    from cachine import CacheBuilder, RedisCache
    from cachine.middleware import MetricsMiddleware, CompressionMiddleware

    cache = (
        CacheBuilder(RedisCache.from_url("redis://localhost:6379/0", namespace="app"))
        .add_middleware(MetricsMiddleware)
        .add_middleware(CompressionMiddleware, algorithm="gzip", min_size=1024)
        .build()
    )
"""

from __future__ import annotations

import inspect
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Union, cast

from .core.types import AsyncCache, Cache

CacheFactory = Callable[[], Cache]
AsyncCacheFactory = Callable[[], AsyncCache]


MiddlewareFactory = Callable[[Any], Any]


@dataclass
class _MiddlewareSpec:
    """Internal record of a middleware to apply."""

    factory: MiddlewareFactory


def _is_middleware_class(obj: Any) -> bool:
    try:
        return inspect.isclass(obj)
    except Exception:  # pragma: no cover
        return False


def _build_spec(mw: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> _MiddlewareSpec:
    if _is_middleware_class(mw):
        if args or kwargs:
            mw_cls = mw

            def _factory(cache: Any) -> Any:
                return mw_cls(cache, *args, **kwargs)

            return _MiddlewareSpec(factory=_factory)

        mw_cls_simple = mw

        def _factory_simple(cache: Any) -> Any:
            return mw_cls_simple(cache)

        return _MiddlewareSpec(factory=_factory_simple)

    # Callable factory form ``lambda cache: Wrapper(cache)``.
    if args or kwargs:
        raise TypeError(
            "add_middleware: positional/keyword arguments are only supported when passing a middleware class. "
            "For factories, bind arguments in the callable itself (e.g. lambda c: Wrapper(c, ...))."
        )
    return _MiddlewareSpec(factory=mw)


@dataclass
class CacheBuilder:
    """Fluent builder for composing a sync cache + middleware chain.

    Construction accepts a base cache instance or a zero-arg factory that
    returns one. Use :meth:`add_middleware` to stack layers (first added is
    the inner-most; last added is outer-most).
    """

    _base_instance: Cache | None = None
    _base_factory: CacheFactory | None = None
    _middlewares: list[_MiddlewareSpec] = field(default_factory=list)

    def __init__(self, cache: Cache | CacheFactory) -> None:
        """Create a builder around ``cache``.

        Args:
            cache: Either a :class:`Cache` instance or a zero-arg factory
                ``() -> Cache`` for lazy construction.
        """
        self._middlewares = []
        if callable(cache) and not hasattr(cache, "get"):
            self._base_factory = cast(CacheFactory, cache)
            self._base_instance = None
        else:
            self._base_instance = cast(Cache, cache)
            self._base_factory = None

    # ---- Deprecated classmethods ----
    @staticmethod
    def from_url(url: str, *args: Any, **kwargs: Any) -> CacheBuilder:
        """Deprecated: use ``<Backend>.from_url(url)`` + ``CacheBuilder(cache)``.

        Kept temporarily for backward compatibility. Infers the backend from
        the URL scheme and builds a lazy factory.
        """
        warnings.warn(
            "CacheBuilder.from_url is deprecated since v0.2; use <Backend>.from_url(...) "
            "directly and pass the result to CacheBuilder(cache) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        def _factory() -> Cache:
            scheme = url.split("://", 1)[0].lower() if "://" in url else ""
            if scheme.startswith("redis"):
                from .backends.redis.sync import RedisCache

                return RedisCache.from_url(url, *args, **kwargs)
            if scheme == "sqlite":
                from .backends.sqlite.sync import SQLiteCache

                return SQLiteCache.from_url(url, *args, **kwargs)
            raise ValueError(f"Unsupported URL scheme: {scheme!r}")

        return CacheBuilder(_factory)

    @staticmethod
    def from_cache(cache: Cache | CacheFactory) -> CacheBuilder:
        """Deprecated alias for ``CacheBuilder(cache)``."""
        warnings.warn(
            "CacheBuilder.from_cache is deprecated since v0.2; call CacheBuilder(cache) directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        return CacheBuilder(cache)

    # ---- Middleware ----
    def add_middleware(self, mw: Any, /, *args: Any, **kwargs: Any) -> CacheBuilder:
        """Add a middleware layer.

        Accepts:
            - A middleware class: ``add_middleware(MetricsMiddleware)``
            - A class with constructor kwargs:
              ``add_middleware(CompressionMiddleware, algorithm="gzip", min_size=1024)``
            - A factory ``(cache) -> cache``: ``add_middleware(lambda c: Wrapper(c))``

        The first added middleware becomes the inner-most layer; the last
        added is the outer-most.
        """
        self._middlewares.append(_build_spec(mw, args, kwargs))
        return self

    def build(self) -> Cache:
        """Build the cache with all configured middleware applied."""
        if self._base_instance is not None:
            base: Cache = self._base_instance
        elif self._base_factory is not None:
            base = self._base_factory()
        else:
            raise RuntimeError("CacheBuilder has no base cache")

        wrapped: Cache = base
        for spec in self._middlewares:
            wrapped = spec.factory(wrapped)
        return wrapped

    def as_factory(self) -> CacheFactory:
        """Return a zero-arg factory that builds the wrapped cache lazily."""

        def _f() -> Cache:
            return self.build()

        return _f


# ---------------------------------------------------------------------------
# Async builder
# ---------------------------------------------------------------------------


_ASYNC_MW_REGISTRY: dict[type, type] = {}


def _register_default_async_middleware() -> None:
    try:
        from .middleware.fail_open import AsyncFailOpenMiddleware, FailOpenMiddleware
        from .middleware.metrics import AsyncMetricsMiddleware, MetricsMiddleware

        _ASYNC_MW_REGISTRY[MetricsMiddleware] = AsyncMetricsMiddleware
        _ASYNC_MW_REGISTRY[FailOpenMiddleware] = AsyncFailOpenMiddleware
    except Exception:  # pragma: no cover
        pass


def _resolve_async_middleware(mw: Any) -> Any:
    """Map known sync middleware classes to their async counterparts."""
    if not _ASYNC_MW_REGISTRY:
        _register_default_async_middleware()
    if _is_middleware_class(mw):
        return _ASYNC_MW_REGISTRY.get(mw, mw)
    return mw


@dataclass
class AsyncCacheBuilder:
    """Async counterpart of :class:`CacheBuilder`.

    Auto-maps known sync middleware classes (``MetricsMiddleware``,
    ``FailOpenMiddleware``) to their async variants. Pass the async class
    directly for custom middleware.
    """

    _base_instance: AsyncCache | None = None
    _base_factory: AsyncCacheFactory | None = None
    _middlewares: list[_MiddlewareSpec] = field(default_factory=list)

    def __init__(self, cache: AsyncCache | AsyncCacheFactory) -> None:
        self._middlewares = []
        if callable(cache) and not hasattr(cache, "get"):
            self._base_factory = cast(AsyncCacheFactory, cache)
            self._base_instance = None
        else:
            self._base_instance = cast(AsyncCache, cache)
            self._base_factory = None

    # ---- Deprecated classmethods ----
    @staticmethod
    def from_url(url: str, *args: Any, **kwargs: Any) -> AsyncCacheBuilder:
        """Deprecated: use ``<Backend>.from_url(url)`` + ``AsyncCacheBuilder(cache)``."""
        warnings.warn(
            "AsyncCacheBuilder.from_url is deprecated since v0.2; use <Backend>.from_url(...) "
            "directly and pass the result to AsyncCacheBuilder(cache).",
            DeprecationWarning,
            stacklevel=2,
        )

        def _factory() -> AsyncCache:
            scheme = url.split("://", 1)[0].lower() if "://" in url else ""
            if scheme.startswith("redis"):
                from .backends.redis.async_ import AsyncRedisCache

                return AsyncRedisCache.from_url(url, *args, **kwargs)
            if scheme == "sqlite":
                from .backends.sqlite.async_ import AsyncSQLiteCache

                return AsyncSQLiteCache.from_url(url, *args, **kwargs)
            raise ValueError(f"Unsupported URL scheme: {scheme!r}")

        return AsyncCacheBuilder(_factory)

    @staticmethod
    def from_cache(cache: AsyncCache | AsyncCacheFactory) -> AsyncCacheBuilder:
        """Deprecated alias for ``AsyncCacheBuilder(cache)``."""
        warnings.warn(
            "AsyncCacheBuilder.from_cache is deprecated since v0.2; call AsyncCacheBuilder(cache) directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        return AsyncCacheBuilder(cache)

    # ---- Middleware ----
    def add_middleware(self, mw: Any, /, *args: Any, **kwargs: Any) -> AsyncCacheBuilder:
        """Add a middleware layer (maps known sync classes to async variants)."""
        resolved = _resolve_async_middleware(mw)
        self._middlewares.append(_build_spec(resolved, args, kwargs))
        return self

    def build(self) -> AsyncCache:
        """Build the async cache with all middleware applied."""
        if self._base_instance is not None:
            base: AsyncCache = self._base_instance
        elif self._base_factory is not None:
            base = self._base_factory()
        else:
            raise RuntimeError("AsyncCacheBuilder has no base cache")

        wrapped: AsyncCache = base
        for spec in self._middlewares:
            wrapped = spec.factory(wrapped)
        return wrapped

    def as_factory(self) -> AsyncCacheFactory:
        def _f() -> AsyncCache:
            return self.build()

        return _f


# Backwards-compatibility type aliases preserved for consumers that imported
# the union types from earlier versions.
SyncMiddlewareSpec = Union[type[Any], Callable[[Cache], Cache]]
AsyncMiddlewareSpec = Union[type[Any], Callable[[AsyncCache], AsyncCache]]


__all__ = [
    "CacheBuilder",
    "AsyncCacheBuilder",
    "SyncMiddlewareSpec",
    "AsyncMiddlewareSpec",
]
