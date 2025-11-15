# Cachine - Interface Documentation

## Basic Usage

### 1. In-Memory Cache (Sync)

```python
from cachine import InMemoryCache

# Create an in-memory cache (sync)
cache = InMemoryCache()

# Basic operations
cache.set("user:123", {"name": "John", "age": 30})
user = cache.get("user:123")

# With TTL (time-to-live)
cache.set("session:abc", "data", ttl=3600)  # expires in 1 hour

# Delete
cache.delete("user:123")

# Check existence
exists = cache.exists("user:123")

# Clear current namespace
cache.clear()

# Admin-only: clear everything (dangerous)
# cache.clear(dangerously_clear_all=True)
```

### 2a. Redis Cache (Async)

```python
from cachine import AsyncRedisCache

# Create a Redis cache
cache = AsyncRedisCache(host="localhost", port=6379, db=0)

# Same interface as in-memory
await cache.set("user:123", {"name": "John", "age": 30})
user = await cache.get("user:123")

# Close connection when done
await cache.close()
```

### 2b. Redis Cache (Sync)

```python
from cachine import RedisCache

# Create a Redis cache (sync/blocking)
cache = RedisCache(host="localhost", port=6379, db=0)

# Same interface as async, without awaits
cache.set("user:123", {"name": "John", "age": 30})
user = cache.get("user:123")

# Close connection when done
cache.close()
```

### 3a. Context Manager Support (Async)

```python
from cachine import AsyncRedisCache

async with AsyncRedisCache(host="localhost") as cache:
    await cache.set("key", "value")
    value = await cache.get("key")
# Automatically closes connection
```

### 3b. Context Manager Support (Sync)

```python
from cachine import RedisCache

with RedisCache(host="localhost") as cache:
    cache.set("key", "value")
    value = cache.get("key")
# Automatically closes connection
```

## Semantics

- get: `cache.get(key, default=None)` returns `default` on miss; use `exists(key)` to disambiguate missing vs stored `None`.
 - Keys: `str` keys only; normalized as provided (no implicit lowercasing). Recommend a stable prefix/namespace per app. The decorator’s default auto‑key includes the fully qualified function name (`module.qualname`) plus normalized args/kwargs.
- TTL: accepts `int` seconds or `datetime.timedelta`. A `ttl <= 0` deletes the key (no-op if missing). TTL rounding is to whole seconds.
- Deletes: `cache.delete(key)` returns `bool` indicating if the key existed.
- Counters: `cache.incr(key, delta=1, ttl_on_create=None)` returns the new integer value. `decr(key, delta=1)` is an alias for `incr(delta=-delta)`.
- Namespaces: pass `namespace="..."` at construction, or use `cache.with_namespace(ns)` to derive a scoped view. `clear()` only affects the current namespace; a full clear requires `dangerously_clear_all=True`.
- Ping: `cache.ping()` returns a structured status dict (`{"healthy": bool, "latency_ms": float, "backend": str}`), and `cache.ping_ok()` returns a simple bool.
- Modes: Redis supports both async and sync (`AsyncRedisCache` and `RedisCache`). In-memory is sync-only (`InMemoryCache`). Async usage mirrors sync but with `await` and `async with`.
- Tags: entries can be tagged at write/decorator time; invalidate with `cache.invalidate_tags([..])`. Tag indexes never outlive the entry TTL; duplicates are deduped. Cross-instance invalidations propagate via pub/sub.

## Advanced Operations

### Get Or Set

```python
# Populate on miss with singleflight + optional TTL jitter
value = await cache.get_or_set(
    "product:42",
    factory=lambda: db.fetch_product(42),
    ttl=300,
    jitter=30,  # randomize TTL to avoid herd refresh
)

# Sync variant
# value = cache.get_or_set(
#     "product:42",
#     factory=lambda: db.fetch_product(42),
#     ttl=300,
#     jitter=30,
# )
```

### Counters

```python
# Increment
views = await cache.incr("page:views")  # returns 1
views = await cache.incr("page:views", delta=5)  # returns 6

# Decrement (alias)
remaining = await cache.decr("rate_limit:user:123")
```

### TTL Management

```python
# Set/update expiration by TTL
await cache.expire("session:abc", ttl=1800)  # 30 minutes

# Extend TTL without rewriting value
await cache.touch("session:abc", ttl=600)  # add 10 minutes

# Get remaining TTL
remaining = await cache.ttl("session:abc")  # returns seconds remaining

# Set absolute expiration
from datetime import datetime, timedelta, timezone
await cache.expire_at("session:abc", datetime.now(timezone.utc) + timedelta(hours=1))

# Remove expiration, make key persistent
await cache.persist("session:abc")

# Sync variant
# cache.expire("session:abc", ttl=1800)
# cache.touch("session:abc", ttl=600)
# remaining = cache.ttl("session:abc")
# cache.expire_at("session:abc", datetime.now(timezone.utc) + timedelta(hours=1))
# cache.persist("session:abc")
```

### Locks

```python
# Cross-process critical section
async with cache.lock("locks:reindex", ttl=30):
    await do_reindex()

# Sync variant
# with cache.lock("locks:reindex", ttl=30):
#     do_reindex()
```

## Configuration

### In-Memory Cache Options

```python
from cachine import InMemoryCache
from cachine.strategies import LRUEviction, LFUEviction

# LRU cache with max size
cache = InMemoryCache(
    max_size=1000,
    eviction_policy=LRUEviction(),
    namespace="myapp"
)

# LFU cache
cache = InMemoryCache(
    max_size=1000,
    eviction_policy=LFUEviction(),
    namespace="myapp"
)
```

### Redis Cache Options

```python
from cachine import RedisCache

# Basic configuration
cache = RedisCache(
    host="localhost",
    port=6379,
    db=0,
    password="secret",
    ssl=True,
    namespace="myapp"
)

# Redis Cluster
from cachine import RedisClusterCache

cache = RedisClusterCache(
    nodes=[
        {"host": "localhost", "port": 7000},
        {"host": "localhost", "port": 7001},
        {"host": "localhost", "port": 7002},
    ]
)

# Redis Sentinel
from cachine import RedisSentinelCache

cache = RedisSentinelCache(
    sentinels=[
        ("localhost", 26379),
        ("localhost", 26380),
    ],
    service_name="mymaster"
)
```

## Serialization

```python
from cachine import AsyncRedisCache
from cachine.serializers import JSONSerializer, PickleSerializer, MsgPackSerializer

# Use JSON serializer (for simple types)
cache = AsyncRedisCache(
    host="localhost",
    serializer=JSONSerializer()
)

# Use Pickle serializer (for complex Python objects)
cache = AsyncRedisCache(
    host="localhost",
    serializer=PickleSerializer()
)

# Use MessagePack serializer (fast and compact)
cache = AsyncRedisCache(
    host="localhost",
    serializer=MsgPackSerializer()
)

# Per-call override (async)
await cache.set("k", some_value, serializer=JSONSerializer())

# Sync variant
# from cachine import RedisCache
# cache = RedisCache(host="localhost")
# cache.set("k", some_value, serializer=JSONSerializer())
```

## Decorators

### Basic Caching Decorator

```python
# Async example
from cachine import cached, AsyncRedisCache

cache = AsyncRedisCache(host="localhost")

# By default, the auto-key includes module + function name + normalized args/kwargs
@cached(cache, ttl=300)
async def get_user(user_id: int):
    # This will be cached for 5 minutes
    user = await db.fetch_user(user_id)
    return user

# First call - fetches from database
user = await get_user(123)

# Second call - returns from cache
user = await get_user(123)

# Sync example with in-memory
from cachine import InMemoryCache

sync_cache = InMemoryCache()

@cached(sync_cache, ttl=300)
def get_user_sync(user_id: int):
    return db.fetch_user(user_id)

user = get_user_sync(123)
```

### Custom Key Builder

```python
from cachine import cached

@cached(cache, key_builder=lambda user_id, role: f"user:{user_id}:{role}")
async def get_user_by_role(user_id: int, role: str):
    return await db.fetch_user(user_id, role)

# You can also receive a KeyContext as first argument:
# from cachine.decorators.cached import KeyContext
# @cached(cache, key_builder=lambda ctx, user_id, role: f"{ctx.full_name}:{user_id}:{role}")
# async def get_user_by_role(user_id: int, role: str):
#     ...
```

### Conditional Caching

```python
from cachine import cached

@cached(
    cache,
    condition=lambda result: result is not None,  # Only cache non-None results
    ttl=3600
)
async def find_user(email: str):
    return await db.find_user_by_email(email)
```

### Tagged Caching

```python
from cachine import cached

@cached(
    cache,
    ttl=300,
    tags=lambda user_id: [f"user:{user_id}", "users"],
    tags_from_result=lambda u: [f"role:{u['role']}"] if u else [],
)
async def get_user(user_id: int):
    return await db.fetch_user(user_id)

# Later: invalidate by tag
await cache.invalidate_tags(["users"])          # invalidate all users
await cache.invalidate_tags(["user:123"])       # invalidate a single user

# Sync variant
# cache.invalidate_tags(["users"])  # no await
```

### Decorator Options

- ttl: expiration in seconds or timedelta.
- key_builder: function to generate custom keys. It may accept either the function's args/kwargs, or a first positional KeyContext followed by args/kwargs: `key_builder(ctx, *args, **kwargs)`. `KeyContext` fields: `module`, `qualname`, `full_name`, `version`.
- version: string/number appended to keys to bust old entries on logic change.
- cache_none: whether to cache None results (default False recommended).
- stale_ttl: serve stale entries for up to N seconds while refreshing in background.
- singleflight: de-duplicate concurrent identical calls.
- Works with both sync and async functions.
- tags: list of strings or callable(args, kwargs) -> list[str] to tag entries for later invalidation.
- tags_from_result: callable(result) -> list[str]; merged with `tags` after a miss and successful compute.

## Middleware

### Compression

```python
from cachine import AsyncRedisCache
from cachine.middleware import CompressionMiddleware

cache = AsyncRedisCache(host="localhost")
cache = CompressionMiddleware(cache, algorithm="gzip", min_size=1024)

# Values are automatically compressed/decompressed (async)
await cache.set("large_data", huge_object)

# Sync variant
# from cachine import RedisCache
# cache = RedisCache(host="localhost")
# cache = CompressionMiddleware(cache, algorithm="gzip", min_size=1024)
# cache.set("large_data", huge_object)
```

### Encryption

```python
from cachine import AsyncRedisCache
from cachine.middleware import EncryptionMiddleware

cache = AsyncRedisCache(host="localhost")
cache = EncryptionMiddleware(cache, key="your-secret-key", key_id="v1")

# Values are automatically encrypted/decrypted (async)
await cache.set("sensitive", {"ssn": "123-45-6789"})

# Sync variant
# from cachine import RedisCache
# cache = RedisCache(host="localhost")
# cache = EncryptionMiddleware(cache, key="your-secret-key", key_id="v1")
# cache.set("sensitive", {"ssn": "123-45-6789"})
```

### Metrics

```python
from cachine import AsyncRedisCache
from cachine.middleware import MetricsMiddleware

cache = AsyncRedisCache(host="localhost")
cache = MetricsMiddleware(cache)

# Track cache hits, misses, latency (async)
await cache.set("key", "value")
await cache.get("key")  # Hit
await cache.get("missing")  # Miss

# Get metrics
stats = cache.get_stats()
# Returns: {"hits": 1, "misses": 1, "hit_rate": 0.5, "avg_latency_ms": 1.2}

# Sync variant
# from cachine import RedisCache
# cache = MetricsMiddleware(RedisCache(host="localhost"))
# cache.set("key", "value")
# cache.get("key")
```

## Cache Invalidation

### Invalidate by Tags (direct)

```python
# Async
await cache.invalidate_tags(["user:123", "role:admin"])  # returns count of keys invalidated (optional)

# Sync
# cache.invalidate_tags(["user:123", "role:admin"])  
```

### Strategy-based (optional)

```python
from cachine import AsyncRedisCache
from cachine.strategies import TagBasedInvalidation

cache = AsyncRedisCache(host="localhost")
invalidator = TagBasedInvalidation(cache)

# Tag cache entries (async)
await invalidator.set("user:123", user_data, tags=["user", "profile"])
await invalidator.set("user:456", other_user, tags=["user", "admin"])

# Invalidate by tag
await invalidator.invalidate_tag("admin")  # Removes user:456
await invalidator.invalidate_tag("user")   # Removes all users

# Sync variant
# from cachine import RedisCache
# invalidator = TagBasedInvalidation(RedisCache(host="localhost"))
# invalidator.set("user:123", user_data, tags=["user", "profile"])
# invalidator.invalidate_tag("admin")
```

## Health Checks

```python
# Structured health
status = await cache.ping()  # {"healthy": True, "latency_ms": 0.8, "backend": "redis"}

if not status["healthy"]:
    # Fallback to database or alternative cache
    pass

# Convenience boolean
ok = await cache.ping_ok()

# Sync variant
# status = cache.ping()
# ok = cache.ping_ok()
```

## Error Handling

```python
from cachine.exceptions import (
    CacheError,
    ConnectionError,
    SerializationError,
    DeserializationError,
    EvictionError
)

try:
    await cache.set("key", "value")
except ConnectionError:
    # Handle connection failures
    logger.error("Cache unavailable, using fallback")
except SerializationError:
    # Handle serialization issues
    logger.error("Failed to serialize value")
```

## Complete Example

```python
from cachine import AsyncRedisCache, cached
from cachine.serializers import MsgPackSerializer
from cachine.middleware import MetricsMiddleware, CompressionMiddleware

# Setup cache with middleware
cache = AsyncRedisCache(
    host="localhost",
    port=6379,
    serializer=MsgPackSerializer()
)
cache = CompressionMiddleware(cache)
cache = MetricsMiddleware(cache)

# Use as decorator with extended options
@cached(
    cache,
    ttl=300,
    version="v1",          # bust keys when logic changes
    cache_none=False,       # skip caching None results
    stale_ttl=60,           # serve stale for 60s while refreshing
    singleflight=True       # de-dupe concurrent calls
)
async def get_product(product_id: int):
    return await db.fetch_product(product_id)

# Use directly
async def main():
    async with cache:
        # Cache operations
        await cache.set("config", {"debug": True}, ttl=3600)
        config = await cache.get("config")

        # Populate on miss
        product = await cache.get_or_set(
            "product:42",
            factory=lambda: db.fetch_product(42),
            ttl=300,
            jitter=30,
        )

        # Counters
        await cache.incr("api:requests")

        # Health
        status = await cache.ping()

        # Get metrics
        stats = cache.get_stats()
        print(f"Cache hit rate: {stats['hit_rate']:.2%}")
```

### Complete Example (Sync)

```python
from cachine import RedisCache, cached
from cachine.serializers import MsgPackSerializer
from cachine.middleware import MetricsMiddleware, CompressionMiddleware

# Setup cache with middleware (sync)
cache = RedisCache(
    host="localhost",
    port=6379,
    serializer=MsgPackSerializer()
)
cache = CompressionMiddleware(cache)
cache = MetricsMiddleware(cache)

@cached(cache, ttl=300)
def get_product(product_id: int):
    return db.fetch_product(product_id)

def main():
    with cache:
        cache.set("config", {"debug": True}, ttl=3600)
        config = cache.get("config")

        product = cache.get_or_set(
            "product:42",
            factory=lambda: db.fetch_product(42),
            ttl=300,
            jitter=30,
        )

        cache.incr("api:requests")

        status = cache.ping()

        stats = cache.get_stats()
        print(f"Cache hit rate: {stats['hit_rate']:.2%}")
```

## Factory Pattern

```python
from cachine import create_cache

# Create from config
cache = create_cache({
    "backend": "redis",
    "host": "localhost",
    "port": 6379,
    "serializer": "msgpack",
    "namespace": "myapp",
    "middleware": ["compression", "metrics"]
}, mode="async")

# Or use environment-based config
cache = create_cache.from_env(mode="sync")  # Reads from CACHE_* env vars
```

Note: The `mode` parameter applies to Redis backends. In-memory always returns the sync `InMemoryCache`.
