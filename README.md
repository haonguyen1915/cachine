# Cachine

**A simple, powerful caching library for Python that makes your applications faster.**

Stop waiting for slow API calls, database queries, and expensive computations. Cache the results and reuse them instantly.

## Why Cachine?

- ⚡ **2-10x faster responses** - Cache expensive operations and serve results in microseconds
- 🎯 **Dead simple** - One decorator is all you need: `@cached(cache, ttl=60)`
- 🔧 **Start small, scale big** - Begin with in-memory, upgrade to Redis when you need distributed caching
- 🚀 **Production-ready** - Encryption, compression, metrics, clustering, and high-availability out of the box
- 🐍 **Modern Python** - Full type hints, sync & async support, Python 3.9+

**Perfect for:** API response caching, database query caching, expensive computations, rate limiting, session storage.

---

## Table of Contents

- [What is Caching?](#what-is-caching)
- [Installation](#installation)
- [Quickstart](#quickstart)
  - [Step 1: Your First Cache](#step-1-your-first-cache)
  - [Step 2: Cache Expensive Functions](#step-2-cache-expensive-functions)
  - [Step 3: Scale to Redis](#step-3-scale-to-redis)
  - [Step 4: Async Support](#step-4-async-support)
- [Common Use Cases](#common-use-cases)
  - [🌐 Caching API Responses](#-caching-api-responses)
  - [🗄️ Caching Database Queries](#️-caching-database-queries)
  - [🔄 Preventing Duplicate Work](#-preventing-duplicate-work-singleflight)
  - [📊 Rate Limiting](#-rate-limiting-with-counters)
  - [🔖 Tag-Based Invalidation](#-tag-based-invalidation)
- [Choosing the Right Backend](#choosing-the-right-backend)
  - [📦 InMemoryCache](#-inmemorycache)
  - [🔴 RedisCache](#-rediscache-single-instance)
  - [🔴🔴🔴 Redis Cluster](#-redis-cluster)
  - [🛡️ Redis Sentinel](#️-redis-sentinel-high-availability)
- [Advanced Decorator Features](#advanced-decorator-features)
  - [Custom Key Generation](#custom-key-generation)
  - [Stale-While-Revalidate](#stale-while-revalidate-swr)
  - [Conditional Caching](#conditional-caching)
  - [Don't Cache None](#dont-cache-none)
  - [Add Jitter](#add-jitter-to-prevent-stampedes)
- [Middleware](#middleware-optional-power-features)
  - [📊 Track Cache Performance](#-track-cache-performance)
  - [🗜️ Compress Large Values](#️-compress-large-values)
  - [🔐 Encrypt Sensitive Data](#-encrypt-sensitive-data)
  - [🛟 Fail-Open (Keep Running if Redis Fails)](#-fail-open-keep-running-if-redis-fails)
  - [🔗 Stack Multiple Middleware](#-stack-multiple-middleware)
- [Serializers](#serializers)
- [Configuration & Factory](#configuration--factory)
- [Glossary](#glossary)
- [Performance Tips](#performance-tips)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)
- [Examples & Recipes](#examples--recipes)
- [Contributing](#contributing)
- [License](#license)

---

## What is Caching?

Caching stores the results of expensive operations so you don't have to repeat them.

**Without caching:**
```python
def get_user(user_id):
    return database.query(f"SELECT * FROM users WHERE id={user_id}")  # 50ms every time ❌
```

**With caching:**
```python
@cached(cache, ttl=300)
def get_user(user_id):
    return database.query(f"SELECT * FROM users WHERE id={user_id}")  # 50ms first time, <1ms after ✅
```

First call: Fetches from database (50ms)
Cached calls: Returns from cache (<1ms) - **50x faster!**

---

## Installation

**Basic installation** (in-memory caching):
```bash
pip install cachine
```

**With Redis** (for distributed caching):
```bash
pip install cachine redis
```

**Optional extras:**
```bash
pip install msgpack       # Fast binary serialization
pip install cryptography  # Encryption middleware
```

**Requirements:** Python 3.9+, redis-py 4.0+ (optional)

---

## Quickstart

### Step 1: Your First Cache

Start with simple get/set operations:

```python
from cachine import InMemoryCache

# Create a cache
cache = InMemoryCache()

# Store a value (expires after 60 seconds)
cache.set("user:123", {"name": "Alice", "role": "admin"}, ttl=60)

# Retrieve it
user = cache.get("user:123")
print(user)  # {'name': 'Alice', 'role': 'admin'}

# Check if it exists
if cache.exists("user:123"):
    print("User is cached!")

# Remove it
cache.delete("user:123")
```

### Step 2: Cache Expensive Functions

The `@cached` decorator automatically caches function results:

```python
from cachine import InMemoryCache
from cachine.decorators import cached
import time

cache = InMemoryCache()

@cached(cache=cache, ttl=60)
def expensive_computation(x):
    print(f"Computing {x}...")
    time.sleep(2)  # Simulate slow operation
    return x * 2

# First call: takes 2 seconds
result = expensive_computation(21)  # Prints "Computing 21..." and waits
# => 42

# Subsequent calls: instant! (returns from cache)
result = expensive_computation(21)  # Returns immediately
# => 42 (no print, no wait)
```

### Step 3: Scale to Redis

Share cache across multiple servers with Redis:

```python
from cachine import cache_from_url
from cachine.decorators import cached
from cachine.serializers import JSONSerializer

# Create Redis cache from URL
cache = cache_from_url(
    "redis://localhost:6379/0",
    namespace="myapp",  # Prefix all keys with "myapp:"
    serializer=JSONSerializer()
)

@cached(cache=cache, ttl=300)  # Cache for 5 minutes
def get_user(user_id):
    # Now cached across ALL your servers!
    return database.query_user(user_id)

user = get_user(123)
```

### Step 4: Async Support

Full async/await support for async applications:

```python
import asyncio
from cachine import async_cache_from_url
from cachine.decorators import cached

# Create async Redis cache from URL
cache = async_cache_from_url("redis://localhost:6379/0", namespace="myapp")

@cached(cache=cache, ttl=60)
async def fetch_data(item_id):
    # Simulate async API call
    await asyncio.sleep(1)
    return {"id": item_id, "data": "..."}

async def main():
    result = await fetch_data(1)  # Slow first time
    result = await fetch_data(1)  # Fast from cache

asyncio.run(main())
```

---

## Common Use Cases

### 🌐 Caching API Responses

```python
import requests

@cached(cache=cache, ttl=300)  # Cache for 5 minutes
def fetch_weather(city):
    response = requests.get(f"https://api.weather.com/forecast/{city}")
    return response.json()

# First call: hits the API (slow)
weather = fetch_weather("London")

# Next 5 minutes: instant responses from cache
weather = fetch_weather("London")  # ⚡ Fast!
```

### 🗄️ Caching Database Queries

```python
from sqlalchemy.orm import Session

@cached(cache=cache, ttl=3600, tags=lambda user_id: [f"user:{user_id}"])
def get_user_profile(user_id: int):
    db: Session = get_db()
    user = db.query(User).filter_by(id=user_id).first()
    return user.to_dict() if user else None

# Cache for 1 hour, invalidate with tags
profile = get_user_profile(123)

# When user updates, invalidate their cache
cache.invalidate_tags(["user:123"])
```

### 🔄 Preventing Duplicate Work (Singleflight)

When many requests come in at once, only compute once:

```python
@cached(cache=cache, ttl=60, singleflight=True)
def generate_report():
    # Only ONE server generates this, even if 1000 requests come in
    # Others wait and get the same result
    time.sleep(10)  # Expensive operation
    return create_monthly_report()

# 1000 concurrent requests = 1 computation
```

### 📊 Rate Limiting with Counters

```python
from datetime import timedelta

def check_rate_limit(user_id: str, max_requests: int = 100):
    key = f"ratelimit:{user_id}"

    # Increment counter, set TTL on first request
    count = cache.incr(key, delta=1, ttl_on_create=60)

    if count > max_requests:
        raise Exception(f"Rate limit exceeded: {count}/{max_requests}")

    return count

# Allow 100 requests per minute per user
check_rate_limit("user123", max_requests=100)
```

### 🔖 Tag-Based Invalidation

Invalidate related cache entries together:

```python
@cached(
    cache=cache,
    ttl=3600,
    tags=lambda user_id: ["users", f"user:{user_id}"]
)
def get_user(user_id):
    return fetch_from_db(user_id)

@cached(
    cache=cache,
    ttl=3600,
    tags=lambda user_id: ["users", f"user:{user_id}"]
)
def get_user_orders(user_id):
    return fetch_orders_from_db(user_id)

# Both functions tagged with "users" and "user:123"
user = get_user(123)
orders = get_user_orders(123)

# Invalidate ALL user-related cache at once
removed = cache.invalidate_tags(["user:123"])
# Both get_user(123) and get_user_orders(123) are now cleared
```

---

## Choosing the Right Backend

### 📦 InMemoryCache

**When to use:**
- ✅ Single server/process application
- ✅ Maximum performance needed (<1μs access)
- ✅ Cache can be lost on restart (transient data)
- ✅ Limited memory usage

**When NOT to use:**
- ❌ Multiple servers need to share cache
- ❌ Cache must survive restarts
- ❌ Cache size > available RAM

**Example:**
```python
from cachine import InMemoryCache
from cachine.strategies import LRUEviction

cache = InMemoryCache(
    max_size=10000,           # Limit to 10k entries
    eviction_policy=LRUEviction(),  # Evict least-recently-used
    namespace="myapp"         # Prefix all keys
)

cache.set("key", "value", ttl=300)
```

### 🔴 RedisCache (Single Instance)

**When to use:**
- ✅ Multiple servers need shared cache
- ✅ Cache should survive restarts
- ✅ Simple deployment (single Redis server)

**When NOT to use:**
- ❌ Need high availability (use Sentinel)
- ❌ Cache size > single server RAM (use Cluster)

**Example:**
```python
from cachine import RedisCache
from cachine.serializers import JSONSerializer

cache = RedisCache(
    host="localhost",
    port=6379,
    db=0,
    password="your-password",  # Optional
    namespace="myapp",
    serializer=JSONSerializer()
)
```

### 🔴🔴🔴 Redis Cluster

**When to use:**
- ✅ Need horizontal scaling
- ✅ High availability required
- ✅ Cache size > single server RAM
- ✅ Production workloads

**Example:**
```python
from cachine.backends.redis import RedisCache
from cachine.models.redis_config import RedisClusterConfig, RedisNodeConfig

config = RedisClusterConfig(
    nodes=[
        RedisNodeConfig(host="redis1.example.com", port=7000),
        RedisNodeConfig(host="redis2.example.com", port=7001),
        RedisNodeConfig(host="redis3.example.com", port=7002),
    ]
)

cache = RedisCache(config, namespace="myapp")
```

### 🛡️ Redis Sentinel (High Availability)

**When to use:**
- ✅ Need automatic failover
- ✅ Master goes down → automatic promotion
- ✅ Production reliability critical

**Example:**
```python
from cachine.backends.redis import RedisCache
from cachine.models.redis_config import RedisSentinelConfig

config = RedisSentinelConfig(
    service_name="mymaster",
    sentinels=[
        ("sentinel1.example.com", 26379),
        ("sentinel2.example.com", 26379),
        ("sentinel3.example.com", 26379),
    ]
)

cache = RedisCache(config, namespace="myapp")
```

---

## Advanced Decorator Features

### Custom Key Generation

Control exactly how cache keys are created:

```python
from cachine.decorators.cached import KeyContext

def my_key_builder(ctx: KeyContext, user_id: int, include_details: bool = False):
    # ctx.full_name = "mymodule.myfunction"
    # ctx.version = "v2" (if specified)
    return f"user:{user_id}:details={include_details}:version={ctx.version}"

@cached(
    cache=cache,
    ttl=300,
    key_builder=my_key_builder,
    version="v2"  # Change version to invalidate all old cache
)
def get_user(user_id: int, include_details: bool = False):
    return fetch_user_data(user_id, include_details)
```

### Stale-While-Revalidate (SWR)

Serve stale data while refreshing in background:

```python
@cached(
    cache=cache,
    ttl=60,         # Fresh for 60 seconds
    stale_ttl=120   # Serve stale for additional 60s while refreshing
)
def get_dashboard_data():
    # Users ALWAYS get fast response:
    # - Within 60s: fresh data
    # - 60-120s: stale data + background refresh started
    # - After 120s: cache miss, compute new
    return expensive_dashboard_computation()
```

### Conditional Caching

Cache only when certain conditions are met:

```python
@cached(
    cache=cache,
    ttl=300,
    condition=lambda result: result is not None and result.get("status") == "success"
)
def fetch_api_data(endpoint):
    response = requests.get(endpoint)
    # Only cache successful responses
    return response.json()
```

### Don't Cache None

```python
@cached(cache=cache, ttl=60, cache_none=False)
def find_user(email):
    user = database.find_by_email(email)
    return user  # None is NOT cached, forces fresh lookup
```

### Add Jitter to Prevent Stampedes

```python
@cached(
    cache=cache,
    ttl=60,
    jitter=10  # Adds 0-10 seconds randomly to TTL
)
def popular_data():
    # If 1000 entries expire at same time → 1000 cache misses
    # With jitter: they expire at different times
    return expensive_operation()
```

---

## Middleware (Optional Power Features)

Add compression, encryption, or metrics by wrapping your cache:

### 📊 Track Cache Performance

```python
from cachine import InMemoryCache
from cachine.middleware import MetricsMiddleware

base = InMemoryCache()
cache = MetricsMiddleware(base)

# Use cache normally
cache.set("key1", "value1")
cache.get("key1")
cache.get("key2")  # Miss

# Check performance
stats = cache.get_stats()
print(stats)
# {
#   'hits': 1,
#   'misses': 1,
#   'hit_rate': 0.5,
#   'errors': 0,
#   'avg_latency_ms': 0.023
# }
```

Async usage:
```python
from cachine import async_cache_from_url
from cachine.middleware import AsyncMetricsMiddleware

base = async_cache_from_url("redis://localhost:6379/0")
cache = AsyncMetricsMiddleware(base)

async def main():
    await cache.set("k", "v")
    await cache.get("k")
    await cache.get("missing", default=None)
    print(cache.get_stats())
```

### 🗜️ Compress Large Values

```python
from cachine.middleware import CompressionMiddleware

base = InMemoryCache()
cache = CompressionMiddleware(
    base,
    algorithm="gzip",  # or "zlib"
    min_size=1024      # Only compress values > 1KB
)

# Large values automatically compressed
large_json = {"data": "x" * 10000}
cache.set("big_data", large_json, serializer=JSONSerializer())

# Automatically decompressed on get
result = cache.get("big_data", serializer=JSONSerializer())
```

### 🔐 Encrypt Sensitive Data

```python
from cachine.middleware import EncryptionMiddleware

base = InMemoryCache()
cache = EncryptionMiddleware(
    base,
    key="your-32-character-secret-key!!",  # Keep this secret!
    key_id="v1"  # For key rotation
)

# Data encrypted at rest
cache.set("user_ssn", "123-45-6789")
cache.set("api_key", "secret-api-key-xyz")

# Automatically decrypted on get
ssn = cache.get("user_ssn")  # "123-45-6789"
```

### 🛟 Fail-Open (Keep Running if Redis Fails)

Ensure your app still works when Redis is down. Wrap caches with a fail‑open middleware; reads return defaults and writes become no‑ops during outages.

Sync:
```python
from cachine import cache_from_url
from cachine.decorators import cached
from cachine.middleware.fail_open import FailOpenMiddleware

base = cache_from_url("redis://localhost:6379/0", namespace="myapp")
cache = FailOpenMiddleware(base)

@cached(cache=cache, ttl=60)
def compute(x):
    return x * 2  # still runs even if Redis errors
```

Async:
```python
from cachine import async_cache_from_url
from cachine.decorators import cached
from cachine.middleware.fail_open import AsyncFailOpenMiddleware

base = async_cache_from_url("redis://localhost:6379/0", namespace="myapp")
cache = AsyncFailOpenMiddleware(base)

@cached(cache=cache, ttl=60)
async def fetch(uid):
    return {"id": uid}
```

### 🔗 Stack Multiple Middleware

Order matters! Stack from inside-out:

```python
from cachine.middleware import CompressionMiddleware, EncryptionMiddleware, MetricsMiddleware
from cachine.serializers import JSONSerializer

# Layer 1: Base cache
base = InMemoryCache(namespace="secure")

# Layer 2: Compress (first, before encryption)
cache = CompressionMiddleware(base, algorithm="gzip", min_size=128)

# Layer 3: Encrypt (second, encrypts compressed data)
cache = EncryptionMiddleware(cache, key="your-secret-key-here!!", key_id="v1")

# Layer 4: Metrics (outer layer, tracks everything)
cache = MetricsMiddleware(cache)

# Now you have: Metrics → Encryption → Compression → InMemory
# Data flow on SET: value → compress → encrypt → store
# Data flow on GET: fetch → decrypt → decompress → return

cache.set("sensitive_data", {"secret": "data"}, serializer=JSONSerializer())
value = cache.get("sensitive_data", serializer=JSONSerializer())
print(cache.get_stats())  # See metrics
```

### 🧱 Build Caches Fluently (Builder)

Compose middleware layers clearly and lazily:

Sync:
```python
from cachine import CacheBuilder
from cachine.middleware import MetricsMiddleware

cache = (
    CacheBuilder.from_url("redis://localhost:6379/0", namespace="myapp")
    .add_middleware(MetricsMiddleware)  # first added = inner; last = outer
    .build()
)
```

Async:
```python
from cachine import AsyncCacheBuilder
from cachine.middleware import AsyncMetricsMiddleware, MetricsMiddleware

# You can add async middleware directly, or add a known sync middleware
# and the builder will map it to its async counterpart where available.
acache = (
    AsyncCacheBuilder.from_url("redis://localhost:6379/0", namespace="myapp")
    .add_middleware(MetricsMiddleware)        # mapped to AsyncMetricsMiddleware
    # .add_middleware(AsyncMetricsMiddleware) # explicit async class also works
    .build()
)
```

Use with the decorator lazily without early initialization:
```python
from cachine.decorators import cached

builder = CacheBuilder.from_url("redis://localhost:6379/0")

@cached(cache=builder.as_factory(), ttl=60)
def compute(x):
    return x * 2
```

---

## Serializers

Convert Python objects to bytes for Redis storage:

```python
from cachine.serializers import JSONSerializer, PickleSerializer, MsgPackSerializer
from caching.backends.redis.sync import RedisCache

# JSON: Safe, human-readable, limited types
cache = RedisCache(host="localhost", serializer=JSONSerializer())
cache.set("data", {"a": 1, "b": [2, 3]})

# MsgPack: Fast, compact, binary
cache = RedisCache(host="localhost", serializer=MsgPackSerializer())
cache.set("data", {"complex": "object"})

# Pickle: All Python types, but UNSAFE for untrusted data
cache = RedisCache(host="localhost", serializer=PickleSerializer())
cache.set("data", any_python_object)
```

**Comparison:**

| Serializer | Speed | Size | Safe? | Types Supported |
|------------|-------|------|-------|-----------------|
| JSON | Medium | Large | ✅ Yes | Basic (dict, list, str, int, float, bool, None) |
| MsgPack | Fast | Small | ✅ Yes | Similar to JSON + bytes, datetime |
| Pickle | Medium | Medium | ❌ No* | All Python objects |

*Pickle can execute arbitrary code during deserialization. Only use with trusted data.

---

## Configuration & Factory

### Factory Functions from URLs

Create cache instances using connection URLs:

```python
from cachine import cache_from_url, async_cache_from_url

# Sync Redis cache
cache = cache_from_url("redis://localhost:6379/0", namespace="myapp")

# Async Redis cache
async_cache = async_cache_from_url("redis://localhost:6379/0", namespace="myapp")

# With authentication
cache = cache_from_url("redis://user:password@localhost:6379/0", namespace="myapp")

# With SSL/TLS
cache = cache_from_url("rediss://localhost:6379/0", namespace="myapp")

# Redis Cluster
cache = cache_from_url(
    "redis://node1:7000,node2:7001,node3:7002",
    namespace="myapp"
)

# Redis Sentinel
cache = cache_from_url(
    "redis+sentinel://mymaster/0?sentinels=s1:26379,s2:26379",
    namespace="myapp"
)
```

### URL Parameters

Configure connection behavior via URL query parameters:

```python
from cachine import cache_from_url

# Timeout configuration
cache = cache_from_url(
    "redis://localhost:6379/0?"
    "socket_timeout=5.0&"              # Read/write timeout (seconds)
    "socket_connect_timeout=2.0&"      # Initial connection timeout
    "retry_on_timeout=true&"           # Retry on timeout
    "decode_responses=true",           # Decode Redis responses to str
    namespace="myapp"
)

# Cluster with SSL and timeouts
cache = cache_from_url(
    "rediss://user:pass@node1:7000,node2:7001?"
    "socket_timeout=10&"
    "retry_on_timeout=1",
    namespace="myapp"
)
```

---

## Glossary

### Key Terms

**Cache Hit**: When requested data is found in cache (fast ✅)
**Cache Miss**: When requested data is NOT in cache, must fetch from source (slow ❌)
**TTL (Time To Live)**: How long cached data stays fresh before expiring (in seconds)
**Namespace**: Prefix for all cache keys to prevent collisions (e.g., `"prod:"` vs `"dev:"`)

### Advanced Terms

**Cache-Aside Pattern**: Your code checks cache first, fetches from source on miss, then stores in cache

**Singleflight**: When multiple requests arrive for the same uncached key, only one computation runs. Others wait and share the result. Prevents "thundering herd".

**Stale-While-Revalidate (SWR)**: Serve slightly old cached data while refreshing it in the background. Users always get fast responses.

**Jitter**: Random delay (0 to N seconds) added to TTL so cache entries don't all expire at the exact same time.

**Tag-Based Invalidation**: Group related cache entries with tags (like `"user:123"` or `"products"`), then invalidate all entries with a tag at once.

**Eviction Policy**: When cache is full, which entries to remove? LRU = remove least-recently-used, LFU = remove least-frequently-used.

**Serialization**: Converting Python objects to bytes for storage (and back). Required for Redis.

**Middleware**: Wrapper that adds functionality (compression, encryption, metrics) without changing cache API.

---

## Performance Tips

### 1. Prevent Thundering Herd

**Problem**: 1000 requests hit expired cache at once → 1000 database queries

**Solutions:**
```python
# Solution A: Add jitter
@cached(cache=cache, ttl=60, jitter=10)  # Expires between 60-70 seconds

# Solution B: Stale-while-revalidate
@cached(cache=cache, ttl=60, stale_ttl=120)  # Serve stale, refresh in background

# Solution C: Singleflight
@cached(cache=cache, ttl=60, singleflight=True)  # Only one computes
```

### 2. Choose Right Serializer

```python
# Small data, human-readable: JSON
cache = RedisCache(serializer=JSONSerializer())

# Large data, need speed: MsgPack
cache = RedisCache(serializer=MsgPackSerializer())  # 2-3x faster than JSON

# Complex Python objects (trusted): Pickle
cache = RedisCache(serializer=PickleSerializer())  # Supports all Python types
```

### 3. Compress Only Large Data

```python
cache = CompressionMiddleware(
    base_cache,
    algorithm="gzip",
    min_size=1024  # Only compress > 1KB (avoid overhead on small values)
)
```

### 4. Set Appropriate TTL

```python
# Frequently changing data: Short TTL
@cached(cache=cache, ttl=60)  # 1 minute

# Rarely changing data: Long TTL
@cached(cache=cache, ttl=86400)  # 24 hours

# Static data: Very long TTL
@cached(cache=cache, ttl=604800)  # 1 week
```

### 5. Use Namespaces

```python
# Development
dev_cache = InMemoryCache(namespace="dev")

# Production
prod_cache = RedisCache(host="prod-redis", namespace="prod")

# Easy to clear: cache.clear() only affects your namespace
```

---

## Troubleshooting

### Redis Connection Issues

```python
# Test connection
if cache.ping_ok():
    print("✅ Connected to Redis")
else:
    print("❌ Cannot connect to Redis")

# Full health check
health = cache.ping()
print(health)  # {'healthy': True, 'latency_ms': 1.2, 'backend': 'redis'}

# Tune client timeouts (sync/async)
from cachine import RedisCache, AsyncRedisCache

rc = RedisCache(host="localhost", socket_timeout=2.5, socket_connect_timeout=1.0, retry_on_timeout=True)
arc = AsyncRedisCache(host="localhost", socket_timeout=2.5, socket_connect_timeout=1.0, retry_on_timeout=True)
```

### Serialization Errors

**Error:** `JSONDecodeError` or `PickleError`

**Solution:** Make sure you use the same serializer for get/set:

```python
# ❌ Wrong: Different serializers
cache.set("key", data, serializer=JSONSerializer())
result = cache.get("key", serializer=PickleSerializer())  # Error!

# ✅ Correct: Same serializer
cache.set("key", data, serializer=JSONSerializer())
result = cache.get("key", serializer=JSONSerializer())
```

### Missing Dependencies

```bash
# ModuleNotFoundError: No module named 'redis'
pip install redis

# ModuleNotFoundError: No module named 'cryptography'
pip install cryptography

# ModuleNotFoundError: No module named 'msgpack'
pip install msgpack
```

### Cache Not Clearing

```python
# Requires namespace OR dangerously_clear_all=True
cache = InMemoryCache(namespace="myapp")
cache.clear()  # ✅ Works

cache = InMemoryCache()  # No namespace
cache.clear()  # ❌ Raises error (safety check)
cache.clear(dangerously_clear_all=True)  # ✅ Works but clears EVERYTHING
```

---

## API Reference

### Cache Operations

```python
# Get/Set
cache.get(key, default=None)
cache.set(key, value, ttl=None)
cache.delete(key)
cache.exists(key)
cache.clear()

# TTL Management
cache.ttl(key)                    # Get remaining TTL in seconds
cache.expire(key, ttl=60)         # Set new TTL (seconds or timedelta)
cache.expire_at(key, when=datetime)  # Set absolute expiration
cache.persist(key)                # Remove TTL (never expires)
cache.touch(key, ttl=None)        # Update last access time, optionally set TTL

# Counters
cache.incr(key, delta=1, ttl_on_create=None)
cache.decr(key, delta=1)

# Tags
cache.invalidate_tags(tags)       # Remove all entries with these tags
cache.add_tags(key, tags)         # Add tags to existing entry

# Utility
cache.get_or_set(key, factory, ttl=None)  # Get cached or compute & cache
cache.ping()                      # Health check
cache.ping_ok()                   # Boolean health check
cache.close()                     # Close connections
```

### Decorator Parameters

```python
@cached(
    cache,                  # Cache instance (required)
    ttl=None,              # Seconds to cache (int or timedelta)
    key_builder=None,      # Custom key function
    condition=None,        # Cache only if condition(result) is True
    cache_none=False,      # Cache None results?
    jitter=None,           # Random 0-N seconds added to TTL
    stale_ttl=None,        # Stale-while-revalidate window
    singleflight=False,    # Prevent duplicate computations
    tags=None,             # Function to generate tags from args
    tags_from_result=None, # Function to generate tags from result
    version=None,          # Version string for cache busting
)
```

---

## Examples & Recipes

Check out real-world examples:

- 📁 [examples/api_caching.py](examples/api_caching.py) - Cache API responses
- 📁 [examples/database_caching.py](examples/database_caching.py) - Cache database queries
- 📁 [examples/rate_limiting.py](examples/rate_limiting.py) - Rate limiting with counters
- 📁 [examples/multi_level_cache.py](examples/multi_level_cache.py) - L1 (memory) + L2 (Redis)
- 📁 [examples/microservices.py](examples/microservices.py) - Distributed caching

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Running tests
- Code style guidelines
- Pull request process

---

## License

Apache-2.0 OR MIT - choose whichever works best for your project.

See [LICENSE-APACHE](LICENSE-APACHE) and [LICENSE-MIT](LICENSE-MIT) for details.

---

## Acknowledgments

Built with ❤️ using:
- [redis-py](https://github.com/redis/redis-py) - Redis client for Python
- [cryptography](https://github.com/pyca/cryptography) - Encryption support
- [msgpack](https://github.com/msgpack/msgpack-python) - Fast serialization

---

## Support & Community

- 📖 [Full Documentation](https://docs.cachine.dev)
- 💬 [GitHub Discussions](https://github.com/yourusername/cachine/discussions)
- 🐛 [Report Issues](https://github.com/yourusername/cachine/issues)
- ⭐ Star us on [GitHub](https://github.com/yourusername/cachine)

---

**Happy caching! 🚀**
