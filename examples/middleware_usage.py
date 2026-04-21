"""Middleware composition using AsyncCacheBuilder with kwargs forwarding."""

import asyncio

from cachine import AsyncCacheBuilder, AsyncRedisCache
from cachine.middleware import CompressionMiddleware, MetricsMiddleware


async def main() -> None:
    cache = (
        AsyncCacheBuilder(AsyncRedisCache(host="localhost"))
        .add_middleware(CompressionMiddleware, min_size=1024)
        .add_middleware(MetricsMiddleware)  # mapped to AsyncMetricsMiddleware automatically
        .build()
    )

    await cache.set("k", "v")
    _ = await cache.get("k")
    print(cache.get_stats())


if __name__ == "__main__":
    asyncio.run(main())
