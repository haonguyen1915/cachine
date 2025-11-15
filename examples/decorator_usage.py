import asyncio

from cachine import AsyncRedisCache, InMemoryCache, cached


@cached(InMemoryCache(), ttl=60)
def add(a: int, b: int) -> int:
    return a + b


@cached(AsyncRedisCache(host="localhost"), ttl=60)
async def fetch_user(user_id: int) -> dict:
    return {"id": user_id}


async def main() -> None:
    print(add(1, 2))
    print(await fetch_user(42))


if __name__ == "__main__":
    asyncio.run(main())
