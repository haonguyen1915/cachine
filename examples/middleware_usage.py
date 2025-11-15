import asyncio

from cachine import AsyncRedisCache
from cachine.middleware import CompressionMiddleware, MetricsMiddleware


async def main() -> None:
    cache = AsyncRedisCache(host="localhost")
    cache = CompressionMiddleware(cache, min_size=1024)
    cache = MetricsMiddleware(cache)
    await cache.set("k", "v")
    _ = await cache.get("k")
    print(cache.get_stats())


if __name__ == "__main__":
    asyncio.run(main())

