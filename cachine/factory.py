"""Cache factory functions for creating cache instances."""

from __future__ import annotations

from typing import Any

from cachine.serializers import Serializer

from .core.types import AsyncCache, Cache
from .exceptions import RedisURLParseError


def cache_from_url(url: str, namespace: str | None = None, serializer: Serializer | None = None, **kwargs: Any) -> Cache:
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

    Examples:
        >>> # Single Redis instance
        >>> cache = cache_from_url("redis://localhost:6379/0", namespace="myapp")

        >>> # Redis with SSL and timeout
        >>> cache = cache_from_url("rediss://localhost:6379/0?socket_timeout=5&retry_on_timeout=true", namespace="myapp")

        >>> # Redis Cluster
        >>> cache = cache_from_url("redis://node1:7000,node2:7001,node3:7002", namespace="myapp")

        >>> # Redis Sentinel
        >>> cache = cache_from_url("redis+sentinel://mymaster/0?sentinels=sentinel1:26379,sentinel2:26379", namespace="myapp")
    """
    if not url:
        raise RedisURLParseError("URL cannot be empty")

    # Extract scheme
    scheme = url.split("://")[0].lower()

    # Route to appropriate backend
    if scheme in ("redis", "rediss", "redis+sentinel", "rediss+sentinel"):
        from .utils.redis_url import parse_redis_url

        config = parse_redis_url(url)

        # Warn about unknown kwargs
        if kwargs:
            import warnings

            warnings.warn(f"Unknown arguments ignored: {list(kwargs.keys())}", stacklevel=2)

        from .backends.redis.sync import RedisCache

        return RedisCache(config, namespace=namespace, serializer=serializer)
    raise RedisURLParseError(
        f"Unsupported cache URL scheme: {scheme}. " f"Supported schemes: redis://, rediss://, redis+sentinel://, rediss+sentinel://"
    )


def async_cache_from_url(url: str, namespace: str | None = None, serializer: Serializer | None = None, **kwargs: Any) -> AsyncCache:
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

    Returns:
        Asynchronous AsyncCache instance

    Raises:
        RedisURLParseError: If URL scheme is not supported or URL is invalid

    Examples:
        >>> # Single Redis instance (async)
        >>> cache = async_cache_from_url("redis://localhost:6379/0", namespace="myapp")

        >>> # Redis Cluster (async)
        >>> cache = async_cache_from_url("redis://node1:7000,node2:7001,node3:7002", namespace="myapp")
    """
    if not url:
        raise RedisURLParseError("URL cannot be empty")

    # Extract scheme
    scheme = url.split("://")[0].lower()

    # Route to appropriate backend
    if scheme in ("redis", "rediss", "redis+sentinel", "rediss+sentinel"):
        from .utils.redis_url import parse_redis_url

        config = parse_redis_url(url)

        # Warn about unknown kwargs
        if kwargs:
            import warnings

            warnings.warn(f"Unknown arguments ignored: {list(kwargs.keys())}", stacklevel=2)

        from .backends.redis.async_ import AsyncRedisCache

        return AsyncRedisCache(config, namespace=namespace, serializer=serializer)
    raise RedisURLParseError(
        f"Unsupported cache URL scheme: {scheme}. " f"Supported schemes: redis://, rediss://, redis+sentinel://, rediss+sentinel://"
    )


__all__ = [
    "cache_from_url",
    "async_cache_from_url",
]
