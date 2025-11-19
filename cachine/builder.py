from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional, Union, cast

from cachine.serializers.base import Serializer

from .core.types import AsyncCache, Cache
from .factory import async_cache_from_url, cache_from_url

CacheFactory = Callable[[], Cache]
AsyncCacheFactory = Callable[[], AsyncCache]

SyncMiddlewareSpec = Union[
    type[Any],  # class with signature __init__(cache, ...)
    Callable[[Cache], Cache],  # factory that accepts cache and returns wrapped cache
]
AsyncMiddlewareSpec = Union[
    type[Any],  # class with signature __init__(cache, ...)
    Callable[[AsyncCache], AsyncCache],  # factory that accepts async cache and returns wrapped cache
]


def _is_middleware_class(obj: Any) -> bool:
    try:
        return inspect.isclass(obj)
    except Exception:  # pragma: no cover - defensive
        return False


@dataclass
class CacheBuilder:
    """Fluent builder for composing sync cache + middleware.

    Usage:
        cache = (
            CacheBuilder.from_url("redis://localhost:6379/0", namespace="app")
            .add_middleware(MetricsMiddleware)
            .build()
        )
    """

    _base_factory: Optional[CacheFactory] = None
    _base_instance: Optional[Cache] = None
    _middlewares: list[SyncMiddlewareSpec] = field(default_factory=list)

    @staticmethod
    def from_url(url: str, namespace: str | None = None, serializer: Serializer | None = None, **kwargs: Any) -> CacheBuilder:
        """Create a synchronous cache instance from a URL.

        Supported URL schemes:
            - redis:// or rediss:// - Single Redis instance
            - redis://host1:port1,host2:port2 - Redis Cluster
            - redis+sentinel:// or rediss+sentinel:// - Redis Sentinel

        Args:
            url: Connection URL string
            namespace: Cache key namespace
            serializer: Custom serializer instance
            **kwargs: Additional arguments passed to cache constructor:
                - For Redis: pubsub_channel, auto_publish_invalidations, etc.

        Returns:
            Synchronous Cache instance

        Raises:
            RedisURLParseError: If URL scheme is not supported or URL is invalid
        """

        # Lazy factory to avoid early network/init
        def _factory() -> Cache:
            return cache_from_url(url, namespace=namespace, serializer=serializer, **kwargs)

        return CacheBuilder(_base_factory=_factory)

    @staticmethod
    def from_cache(cache: Cache | CacheFactory) -> CacheBuilder:
        if callable(cache):
            return CacheBuilder(_base_factory=cache)
        return CacheBuilder(_base_instance=cache)

    def add_middleware(self, mw: SyncMiddlewareSpec) -> CacheBuilder:
        """Add a middleware layer.

        Accepts either a middleware class (constructed with the wrapped cache)
        or a factory ``lambda cache: Wrapper(cache)``.
        The first added becomes the inner-most layer; the last added is outer-most.
        """
        self._middlewares.append(mw)
        return self

    def build(self) -> Cache:
        """Build the cache with all configured middleware applied.

        Returns:
            Cache: A cache instance implementing the Cache protocol.
        """
        base: Cache
        if self._base_instance is not None:
            base = self._base_instance
        elif self._base_factory is not None:
            base = self._base_factory()
        else:  # pragma: no cover - misconfiguration
            raise RuntimeError("CacheBuilder requires a base cache via from_url or from_cache")

        # Apply middleware in the order added (first = inner)
        wrapped: Cache = base
        for spec in self._middlewares:
            if _is_middleware_class(spec):
                wrapped = spec(wrapped)
            else:
                wrapped = spec(wrapped)
        return wrapped

    def as_factory(self) -> CacheFactory:
        """Return a factory that builds the wrapped cache lazily when called."""

        def _f() -> Cache:
            return self.build()

        return _f


_ASYNC_MW_REGISTRY: dict[type, type] = {}


def _register_default_async_middleware() -> None:
    # Lazy import to avoid import cycles and optional deps
    try:
        from .middleware.fail_open import AsyncFailOpenMiddleware, FailOpenMiddleware
        from .middleware.metrics import AsyncMetricsMiddleware, MetricsMiddleware

        _ASYNC_MW_REGISTRY[MetricsMiddleware] = AsyncMetricsMiddleware
        _ASYNC_MW_REGISTRY[FailOpenMiddleware] = AsyncFailOpenMiddleware
    except Exception:  # pragma: no cover - optional
        pass


@dataclass
class AsyncCacheBuilder:
    """Fluent builder for composing async cache + middleware.

    Supports mapping known sync middlewares to their async counterparts when possible.
    """

    _base_factory: Optional[AsyncCacheFactory] = None
    _base_instance: Optional[AsyncCache] = None
    _middlewares: list[AsyncMiddlewareSpec] = field(default_factory=list)

    @staticmethod
    def from_url(url: str, namespace: str | None = None, serializer: Serializer | None = None, **kwargs: Any) -> AsyncCacheBuilder:
        """Create an asynchronous cache instance from a URL.

        Supported URL schemes:
            - redis:// or rediss:// - Single Redis instance
            - redis://host1:port1,host2:port2 - Redis Cluster
            - redis+sentinel:// or rediss+sentinel:// - Redis Sentinel

        Args:
            url: Connection URL string
            namespace: Cache key namespace
            serializer: Custom serializer instance
            **kwargs: Additional arguments passed to cache constructor:
                - For Redis: pubsub_channel, auto_publish_invalidations, etc.
        """

        def _factory() -> AsyncCache:
            return async_cache_from_url(url, namespace=namespace, serializer=serializer, **kwargs)

        return AsyncCacheBuilder(_base_factory=_factory)

    @staticmethod
    def from_cache(cache: AsyncCache | AsyncCacheFactory) -> AsyncCacheBuilder:
        if callable(cache):
            return AsyncCacheBuilder(_base_factory=cache)
        return AsyncCacheBuilder(_base_instance=cache)

    def add_middleware(self, mw: AsyncMiddlewareSpec | SyncMiddlewareSpec) -> AsyncCacheBuilder:
        """Add a middleware layer.

        - If ``mw`` is an async middleware class or factory, it is used as-is.
        - If ``mw`` is a known sync middleware class, it is mapped to its async counterpart.
        """
        # Ensure default mappings are registered
        if not _ASYNC_MW_REGISTRY:
            _register_default_async_middleware()

        spec: AsyncMiddlewareSpec
        if _is_middleware_class(mw):
            mw_cls = cast(type[Any], mw)
            # Map known sync classes to async equivalents
            mapped = _ASYNC_MW_REGISTRY.get(mw_cls)
            spec = cast(AsyncMiddlewareSpec, mapped or mw_cls)
        else:
            spec = cast(AsyncMiddlewareSpec, mw)

        self._middlewares.append(spec)
        return self

    def build(self) -> AsyncCache:
        """Build the async cache with all configured middleware applied.

        Returns:
            AsyncCache: An async cache instance implementing the AsyncCache protocol.
        """
        base: AsyncCache
        if self._base_instance is not None:
            base = self._base_instance
        elif self._base_factory is not None:
            base = self._base_factory()
        else:  # pragma: no cover - misconfiguration
            raise RuntimeError("AsyncCacheBuilder requires a base cache via from_url or from_cache")

        # Apply middleware in the order added (first = inner)
        wrapped: AsyncCache = base
        for spec in self._middlewares:
            if _is_middleware_class(spec):
                wrapped = spec(wrapped)
            else:
                wrapped = spec(wrapped)
        return wrapped

    def as_factory(self) -> AsyncCacheFactory:
        """Return a factory that builds the wrapped async cache lazily when called."""

        def _f() -> AsyncCache:
            return self.build()

        return _f


__all__ = [
    "CacheBuilder",
    "AsyncCacheBuilder",
]
