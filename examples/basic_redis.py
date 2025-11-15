import asyncio

from cachine import AsyncRedisCache


async def main() -> None:
    cache = AsyncRedisCache(host="localhost", port=6379)
    await cache.set("hello", "world", ttl=60)
    print(await cache.get("hello"))


if __name__ == "__main__":
    asyncio.run(main())
