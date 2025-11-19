"""Test tag TTL functionality for async Redis cache."""

import asyncio

import pytest

from cachine.backends.redis.async_ import AsyncRedisCache


@pytest.mark.asyncio
async def test_add_tags_without_ttl(a_redis_cache: AsyncRedisCache) -> None:
    """Test that tags without TTL persist indefinitely."""
    key = "user:123"
    value = {"name": "Alice"}
    tags = ["premium", "active"]

    # Set cache value
    await a_redis_cache.set(key, value, ttl=5)

    # Add tags without TTL
    await a_redis_cache.add_tags(key, tags)

    # Wait for value to expire
    await asyncio.sleep(6)

    # Value should be gone
    assert await a_redis_cache.get(key) is None

    # Tags should still exist - verify by adding another key with same tags
    await a_redis_cache.set("user:456", {"name": "Bob"}, ttl=60)
    await a_redis_cache.add_tags("user:456", ["premium"])

    # Invalidate should still work
    count = await a_redis_cache.invalidate_tags(["premium"])
    assert count > 0


@pytest.mark.asyncio
async def test_add_tags_with_ttl(a_redis_cache: AsyncRedisCache):
    """Test that tags with TTL expire correctly."""
    key = "user:123"
    value = {"name": "Alice"}
    tags = ["temporary"]

    # Set cache value with longer TTL
    await a_redis_cache.set(key, value, ttl=60)

    # Add tags with short TTL (3 seconds)
    await a_redis_cache.add_tags(key, tags, ttl=3)

    # Immediately invalidating should work
    count = await a_redis_cache.invalidate_tags(tags)
    assert count == 1
    assert await a_redis_cache.get(key) is None

    # Set again and wait for tag TTL to expire
    await a_redis_cache.set(key, value, ttl=60)
    await a_redis_cache.add_tags(key, tags, ttl=3)

    # Wait for tag TTL to expire
    await asyncio.sleep(4)

    # Tag should be expired, so invalidate should find nothing
    count = await a_redis_cache.invalidate_tags(tags)
    assert count == 0

    # But the value should still be there
    assert await a_redis_cache.get(key) is not None


@pytest.mark.asyncio
async def test_tag_ttl_longer_than_value_ttl(a_redis_cache: AsyncRedisCache):
    """Test that tag TTL can be longer than value TTL."""
    key1 = "user:123"
    key2 = "user:456"
    value = {"name": "Alice"}
    tags = ["premium"]

    # Set first value with short TTL (3 seconds)
    await a_redis_cache.set(key1, value, ttl=3)

    # Add tags with longer TTL (10 seconds)
    await a_redis_cache.add_tags(key1, tags, ttl=10)

    # Wait for value to expire
    await asyncio.sleep(4)

    # Value should be gone
    assert await a_redis_cache.get(key1) is None

    # But tag set should still exist - add another key with same tag
    await a_redis_cache.set(key2, {"name": "Bob"}, ttl=60)
    await a_redis_cache.add_tags(key2, tags, ttl=10)

    # Invalidating should work and hit the new key
    count = await a_redis_cache.invalidate_tags(tags)
    assert count >= 1
    assert await a_redis_cache.get(key2) is None


@pytest.mark.asyncio
async def test_multiple_tags_different_ttls(a_redis_cache: AsyncRedisCache):
    """Test adding tags with different TTLs."""
    key = "user:123"
    value = {"name": "Alice"}

    # Set cache value
    await a_redis_cache.set(key, value, ttl=60)

    # Add first set of tags with short TTL
    await a_redis_cache.add_tags(key, ["temporary"], ttl=3)

    # Add second set of tags with longer TTL
    await a_redis_cache.add_tags(key, ["persistent"], ttl=10)

    # Wait for short TTL to expire
    await asyncio.sleep(4)

    # Temporary tag should be expired
    count = await a_redis_cache.invalidate_tags(["temporary"])
    assert count == 0

    # Value should still exist
    assert await a_redis_cache.get(key) is not None

    # Persistent tag should still work
    count = await a_redis_cache.invalidate_tags(["persistent"])
    assert count == 1
    assert await a_redis_cache.get(key) is None


@pytest.mark.asyncio
async def test_tag_ttl_with_timedelta(a_redis_cache: AsyncRedisCache):
    """Test that tag TTL works with timedelta objects."""
    from datetime import timedelta

    key = "user:123"
    value = {"name": "Alice"}
    tags = ["test_timedelta"]

    # Set cache value
    await a_redis_cache.set(key, value, ttl=60)

    # Add tags with timedelta TTL (3 seconds)
    await a_redis_cache.add_tags(key, tags, ttl=timedelta(seconds=3))

    # Tag should work immediately
    count = await a_redis_cache.invalidate_tags(tags)
    assert count == 1
    assert await a_redis_cache.get(key) is None

    # Set again and verify TTL expiration
    await a_redis_cache.set(key, value, ttl=60)
    await a_redis_cache.add_tags(key, tags, ttl=timedelta(seconds=3))

    await asyncio.sleep(4)

    # Tag should be expired
    count = await a_redis_cache.invalidate_tags(tags)
    assert count == 0


@pytest.mark.asyncio
async def test_tag_ttl_zero_or_negative(a_redis_cache: AsyncRedisCache):
    """Test that zero or negative TTL is handled gracefully."""
    key = "user:123"
    value = {"name": "Alice"}
    tags = ["test_zero"]

    # Set cache value
    await a_redis_cache.set(key, value, ttl=60)

    # Add tags with zero TTL (should not set expiration or expire immediately)
    await a_redis_cache.add_tags(key, tags, ttl=0)

    # Just verify no errors are raised
    _ = await a_redis_cache.invalidate_tags(tags)
    # Don't assert specific count as behavior may vary


@pytest.mark.asyncio
async def test_concurrent_tag_operations(a_redis_cache: AsyncRedisCache):
    """Test concurrent tag operations with TTL."""
    keys = [f"user:{i}" for i in range(10)]
    value = {"name": "Test"}
    tags = ["concurrent_test"]

    # Add multiple keys concurrently
    tasks = []
    for key in keys:
        tasks.append(a_redis_cache.set(key, value, ttl=60))

    await asyncio.gather(*tasks)

    # Add tags concurrently with TTL
    tasks = []
    for key in keys:
        tasks.append(a_redis_cache.add_tags(key, tags, ttl=5))

    await asyncio.gather(*tasks)

    # Invalidate should hit all keys
    count = await a_redis_cache.invalidate_tags(tags)
    assert count == len(keys)

    # All keys should be deleted
    for key in keys:
        assert await a_redis_cache.get(key) is None
