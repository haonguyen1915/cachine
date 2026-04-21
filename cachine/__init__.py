"""Cachine public API exports.

This module exposes the cache backends, builders, protocols, and URL
factories that make up cachine's public surface.

For decorators, import from :mod:`cachine.decorators`::

    from cachine.decorators import cached

For middleware and serializers, import from their respective subpackages::

    from cachine.middleware import MetricsMiddleware
    from cachine.serializers import JSONSerializer
"""

from .backends.inmemory.cache import InMemoryCache
from .backends.redis.async_ import AsyncRedisCache
from .backends.redis.sync import RedisCache
from .backends.sqlite.async_ import AsyncSQLiteCache
from .backends.sqlite.sync import SQLiteCache
from .builder import AsyncCacheBuilder, CacheBuilder
from .core.types import (
    AsyncCache as AsyncCacheType,
)
from .core.types import (
    AsyncCounterCache,
    AsyncObservableCache,
    AsyncTaggedCache,
    CacheLike,
    CounterCache,
    MinimalAsyncCache,
    MinimalCache,
    ObservableCache,
    TaggedCache,
)
from .core.types import (
    Cache as CacheType,
)
from .factory import async_cache_from_url, cache_from_url
from .models.redis_config import (
    RedisClusterConfig,
    RedisConfig,
    RedisNodeConfig,
    RedisSentinelConfig,
    RedisSingleConfig,
)
from .models.sqlite_config import SQLiteConfig
from .utils.logging_utils import logger_setup

__all__ = [
    # Backends
    "InMemoryCache",
    "RedisCache",
    "AsyncRedisCache",
    "SQLiteCache",
    "AsyncSQLiteCache",
    # Builders
    "CacheBuilder",
    "AsyncCacheBuilder",
    # Protocols
    "CacheType",
    "AsyncCacheType",
    "CacheLike",
    "MinimalCache",
    "MinimalAsyncCache",
    "CounterCache",
    "AsyncCounterCache",
    "TaggedCache",
    "AsyncTaggedCache",
    "ObservableCache",
    "AsyncObservableCache",
    # Config models
    "RedisConfig",
    "RedisSingleConfig",
    "RedisClusterConfig",
    "RedisSentinelConfig",
    "RedisNodeConfig",
    "SQLiteConfig",
    # Deprecated URL factories
    "cache_from_url",
    "async_cache_from_url",
    # Utilities
    "logger_setup",
]
