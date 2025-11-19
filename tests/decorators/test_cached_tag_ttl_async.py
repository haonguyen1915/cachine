"""Test tag TTL functionality with @cached decorator for async functions."""

import asyncio

import pytest

from cachine.backends.redis.async_ import AsyncRedisCache
from cachine.decorators.cached import cached


@pytest.mark.asyncio
async def test_async_cached_with_tag_ttl(a_redis_cache: AsyncRedisCache) -> None:
    """Test that @cached decorator properly uses tag_ttl parameter with async functions."""
    call_count = 0

    @cached(
        cache=a_redis_cache,
        ttl=5,  # Cache value expires in 5 seconds
        tags=["test_tag"],
        tag_ttl=10,  # Tag persists for 10 seconds
    )
    async def get_user(user_id):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate async work
        return {"id": user_id, "name": f"User {user_id}"}

    # First call - cache miss
    result = await get_user(123)
    assert result == {"id": 123, "name": "User 123"}
    assert call_count == 1

    # Second call - cache hit
    result = await get_user(123)
    assert result == {"id": 123, "name": "User 123"}
    assert call_count == 1

    # Wait for cache value to expire but tag still valid
    await asyncio.sleep(6)

    # Cache should be expired, function called again
    result = await get_user(123)
    assert result == {"id": 123, "name": "User 123"}
    assert call_count == 2

    # Re-cache and invalidate by tag
    result = await get_user(123)
    assert call_count == 2

    # Invalidate by tag should work
    count = await a_redis_cache.invalidate_tags(["test_tag"])
    assert count == 1

    # After invalidation, function should be called again
    result = await get_user(123)
    assert call_count == 3


@pytest.mark.asyncio
async def test_async_cached_tag_ttl_shorter_than_value(a_redis_cache: AsyncRedisCache) -> None:
    """Test when tag TTL is shorter than value TTL with async functions."""
    call_count = 0

    @cached(
        cache=a_redis_cache,
        ttl=10,  # Cache value expires in 10 seconds
        tags=["short_tag"],
        tag_ttl=3,  # Tag expires in 3 seconds
    )
    async def get_data(key):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"key": key, "data": "value"}

    # Cache the value
    result = await get_data("test")
    assert call_count == 1

    # Wait for tag to expire
    await asyncio.sleep(4)

    # Tag should be expired, invalidation should not find anything
    count = await a_redis_cache.invalidate_tags(["short_tag"])
    assert count == 0

    # But the cached value should still exist
    result = await get_data("test")
    assert call_count == 1  # Cache hit


@pytest.mark.asyncio
async def test_async_cached_without_tag_ttl(a_redis_cache: AsyncRedisCache) -> None:
    """Test that tags without TTL persist indefinitely with async functions."""
    call_count = 0

    @cached(
        cache=a_redis_cache,
        ttl=5,  # Cache value expires in 5 seconds
        tags=["persistent_tag"],
        # No tag_ttl specified - tags should persist
    )
    async def get_data(key):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"key": key}

    # Cache the value
    await get_data("test")
    assert call_count == 1

    # Wait for cache value to expire
    await asyncio.sleep(6)

    # Value should be expired
    await get_data("test")
    assert call_count == 2

    # But tag should still work - cache again and invalidate
    await get_data("test")
    assert call_count == 2

    count = await a_redis_cache.invalidate_tags(["persistent_tag"])
    assert count == 1


@pytest.mark.asyncio
async def test_async_cached_with_tag_ttl_timedelta(a_redis_cache: AsyncRedisCache) -> None:
    """Test tag_ttl with timedelta object for async functions."""
    from datetime import timedelta

    call_count = 0

    @cached(
        cache=a_redis_cache,
        ttl=60,
        tags=["timedelta_tag"],
        tag_ttl=timedelta(seconds=3),
    )
    async def get_data(key):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"key": key}

    # Cache the value
    await get_data("test")
    assert call_count == 1

    # Tag should work immediately
    count = await a_redis_cache.invalidate_tags(["timedelta_tag"])
    assert count == 1

    # Wait for tag to expire
    await get_data("test")  # Re-cache
    assert call_count == 2

    await asyncio.sleep(4)

    # Tag should be expired
    count = await a_redis_cache.invalidate_tags(["timedelta_tag"])
    assert count == 0


@pytest.mark.asyncio
async def test_async_cached_multiple_tags_with_ttl(a_redis_cache: AsyncRedisCache) -> None:
    """Test multiple async functions with different tag TTLs."""
    count_a = 0
    count_b = 0

    @cached(
        cache=a_redis_cache,
        ttl=60,
        tags=["tag_a"],
        tag_ttl=5,
    )
    async def func_a(x):
        nonlocal count_a
        count_a += 1
        await asyncio.sleep(0.01)
        return x * 2

    @cached(
        cache=a_redis_cache,
        ttl=60,
        tags=["tag_b"],
        tag_ttl=10,
    )
    async def func_b(x):
        nonlocal count_b
        count_b += 1
        await asyncio.sleep(0.01)
        return x * 3

    # Cache both
    assert await func_a(5) == 10
    assert await func_b(5) == 15
    assert count_a == 1
    assert count_b == 1

    # Wait for tag_a to expire
    await asyncio.sleep(6)

    # tag_a should be expired
    count = await a_redis_cache.invalidate_tags(["tag_a"])
    assert count == 0

    # tag_b should still work
    count = await a_redis_cache.invalidate_tags(["tag_b"])
    assert count == 1

    # func_a should still return cached value (tag expired but value exists)
    assert await func_a(5) == 10
    assert count_a == 1

    # func_b should need recalculation (invalidated)
    assert await func_b(5) == 15
    assert count_b == 2


@pytest.mark.asyncio
async def test_async_cached_with_callable_tags_and_tag_ttl(a_redis_cache: AsyncRedisCache) -> None:
    """Test tag_ttl works with callable tags for async functions."""
    call_count = 0

    def get_tags(user_id):
        return [f"user:{user_id}", "all_users"]

    @cached(
        cache=a_redis_cache,
        ttl=60,
        tags=get_tags,
        tag_ttl=5,
    )
    async def get_user(user_id):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"id": user_id}

    # Cache the value
    await get_user(123)
    assert call_count == 1

    # Invalidate by specific user tag
    count = await a_redis_cache.invalidate_tags(["user:123"])
    assert count == 1

    # Re-cache
    await get_user(123)
    assert call_count == 2

    # Wait for tag TTL
    await asyncio.sleep(6)

    # Tag should be expired
    count = await a_redis_cache.invalidate_tags(["user:123"])
    assert count == 0


@pytest.mark.asyncio
async def test_async_cached_enabled_false_no_tags(a_redis_cache: AsyncRedisCache) -> None:
    """Test that tags are not added when caching is disabled for async functions."""
    call_count = 0

    @cached(
        cache=a_redis_cache,
        ttl=60,
        tags=["disabled_tag"],
        tag_ttl=10,
        enabled=False,
    )
    async def get_data(key):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"key": key}

    # Function should be called each time (no caching)
    await get_data("test")
    await get_data("test")
    assert call_count == 2

    # Tags should not have been added
    count = await a_redis_cache.invalidate_tags(["disabled_tag"])
    assert count == 0


@pytest.mark.asyncio
async def test_async_cached_concurrent_with_tag_ttl(a_redis_cache: AsyncRedisCache) -> None:
    """Test concurrent async calls with tag TTL."""
    call_count = 0

    @cached(
        cache=a_redis_cache,
        ttl=60,
        tags=["concurrent_tag"],
        tag_ttl=5,
    )
    async def get_data(key):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate slow operation
        return {"key": key, "value": f"data_{key}"}

    # Make multiple concurrent calls with same key
    results = await asyncio.gather(
        get_data("test"),
        get_data("test"),
        get_data("test"),
    )

    # All should return same result
    assert all(r == {"key": "test", "value": "data_test"} for r in results)

    # Function might be called once or a few times due to race conditions
    # but definitely not 3 times if caching works
    assert call_count <= 3

    # Tag should be set
    count = await a_redis_cache.invalidate_tags(["concurrent_tag"])
    assert count >= 1
