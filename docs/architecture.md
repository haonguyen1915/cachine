## Cachine Architecture (Scaffold)

- InMemoryCache (sync-only) for fast local caching.
- RedisCache (sync) and AsyncRedisCache (async) for networked caching.
- Decorator `cached` supports ttl, jitter, condition, key_builder, version, cache_none,
  stale_ttl, singleflight, tags, and tags_from_result.
- Serializers (JSON, Pickle, MsgPack) for value encoding.
- Middleware (compression, encryption, metrics) wraps caches.
- Strategies include tag-based invalidation helper and eviction policies.
- Factory `create_cache` builds caches from config or env; `mode` applies to Redis.

This is a scaffold; fill in backends and strategies to match INTERFACE.md semantics.
