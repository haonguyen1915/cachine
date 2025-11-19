"""Test tag TTL functionality with @cached decorator."""

import time

import pytest

from cachine.backends.redis.sync import RedisCache
from cachine.decorators.cached import cached


def test_cached_with_tag_ttl(redis_cache: RedisCache):
    """Test that @cached decorator properly uses tag_ttl parameter."""
    call_count = 0

    @cached(
        cache=redis_cache,
        ttl=5,  # Cache value expires in 5 seconds
        tags=["test_tag"],
        tag_ttl=10,  # Tag persists for 10 seconds
    )
    def get_user(user_id):
        nonlocal call_count
        call_count += 1
        return {"id": user_id, "name": f"User {user_id}"}

    # First call - cache miss
    result = get_user(123)
    assert result == {"id": 123, "name": "User 123"}
    assert call_count == 1

    # Second call - cache hit
    result = get_user(123)
    assert result == {"id": 123, "name": "User 123"}
    assert call_count == 1

    # Wait for cache value to expire but tag still valid
    time.sleep(6)

    # Cache should be expired, function called again
    result = get_user(123)
    assert result == {"id": 123, "name": "User 123"}
    assert call_count == 2

    # Tag should still exist (can verify by invalidating after re-caching)
    result = get_user(123)  # Cache again
    assert call_count == 2

    # Invalidate by tag should work
    count = redis_cache.invalidate_tags(["test_tag"])
    assert count == 1

    # After invalidation, function should be called again
    result = get_user(123)
    assert call_count == 3


def test_cached_tag_ttl_shorter_than_value(redis_cache: RedisCache) -> None:
    """Test when tag TTL is shorter than value TTL."""
    call_count = 0

    @cached(
        cache=redis_cache,
        ttl=10,  # Cache value expires in 10 seconds
        tags=["short_tag"],
        tag_ttl=3,  # Tag expires in 3 seconds
    )
    def get_data(key):
        nonlocal call_count
        call_count += 1
        return {"key": key, "data": "value"}

    # Cache the value
    result = get_data("test")
    assert call_count == 1

    # Wait for tag to expire
    time.sleep(4)

    # Tag should be expired, invalidation should not find anything
    count = redis_cache.invalidate_tags(["short_tag"])
    assert count == 0

    # But the cached value should still exist
    result = get_data("test")
    assert call_count == 1  # Cache hit


def test_cached_without_tag_ttl(redis_cache: RedisCache) -> None:
    """Test that tags without TTL persist indefinitely."""
    call_count = 0

    @cached(
        cache=redis_cache,
        ttl=5,  # Cache value expires in 5 seconds
        tags=["persistent_tag"],
        # No tag_ttl specified - tags should persist
    )
    def get_data(key):
        nonlocal call_count
        call_count += 1
        return {"key": key}

    # Cache the value
    get_data("test")
    assert call_count == 1

    # Wait for cache value to expire
    time.sleep(6)

    # Value should be expired
    get_data("test")
    assert call_count == 2

    # But tag should still work - cache again and invalidate
    get_data("test")
    assert call_count == 2

    count = redis_cache.invalidate_tags(["persistent_tag"])
    assert count == 1


def test_cached_with_tag_ttl_timedelta(redis_cache: RedisCache) -> None:
    """Test tag_ttl with timedelta object."""
    from datetime import timedelta

    call_count = 0

    @cached(
        cache=redis_cache,
        ttl=60,
        tags=["timedelta_tag"],
        tag_ttl=timedelta(seconds=3),
    )
    def get_data(key):
        nonlocal call_count
        call_count += 1
        return {"key": key}

    # Cache the value
    get_data("test")
    assert call_count == 1

    # Tag should work immediately
    count = redis_cache.invalidate_tags(["timedelta_tag"])
    assert count == 1

    # Wait for tag to expire
    get_data("test")  # Re-cache
    assert call_count == 2

    time.sleep(4)

    # Tag should be expired
    count = redis_cache.invalidate_tags(["timedelta_tag"])
    assert count == 0


def test_cached_multiple_tags_with_ttl(redis_cache: RedisCache) -> None:
    """Test multiple functions with different tag TTLs."""
    count_a = 0
    count_b = 0

    @cached(
        cache=redis_cache,
        ttl=60,
        tags=["tag_a"],
        tag_ttl=5,
    )
    def func_a(x):
        nonlocal count_a
        count_a += 1
        return x * 2

    @cached(
        cache=redis_cache,
        ttl=60,
        tags=["tag_b"],
        tag_ttl=10,
    )
    def func_b(x):
        nonlocal count_b
        count_b += 1
        return x * 3

    # Cache both
    assert func_a(5) == 10
    assert func_b(5) == 15
    assert count_a == 1
    assert count_b == 1

    # Wait for tag_a to expire
    time.sleep(6)

    # tag_a should be expired
    count = redis_cache.invalidate_tags(["tag_a"])
    assert count == 0

    # tag_b should still work
    count = redis_cache.invalidate_tags(["tag_b"])
    assert count == 1

    # func_a should still return cached value (tag expired but value exists)
    assert func_a(5) == 10
    assert count_a == 1

    # func_b should need recalculation (invalidated)
    assert func_b(5) == 15
    assert count_b == 2


def test_cached_with_callable_tags_and_tag_ttl(redis_cache: RedisCache) -> None:
    """Test tag_ttl works with callable tags."""
    call_count = 0

    def get_tags(user_id):
        return [f"user:{user_id}", "all_users"]

    @cached(
        cache=redis_cache,
        ttl=60,
        tags=get_tags,
        tag_ttl=5,
    )
    def get_user(user_id):
        nonlocal call_count
        call_count += 1
        return {"id": user_id}

    # Cache the value
    get_user(123)
    assert call_count == 1

    # Invalidate by specific user tag
    count = redis_cache.invalidate_tags(["user:123"])
    assert count == 1

    # Re-cache
    get_user(123)
    assert call_count == 2

    # Wait for tag TTL
    time.sleep(6)

    # Tag should be expired
    count = redis_cache.invalidate_tags(["user:123"])
    assert count == 0


def test_cached_enabled_false_no_tags(redis_cache: RedisCache) -> None:
    """Test that tags are not added when caching is disabled."""
    call_count = 0

    @cached(
        cache=redis_cache,
        ttl=60,
        tags=["disabled_tag"],
        tag_ttl=10,
        enabled=False,
    )
    def get_data(key):
        nonlocal call_count
        call_count += 1
        return {"key": key}

    # Function should be called each time (no caching)
    get_data("test")
    get_data("test")
    assert call_count == 2

    # Tags should not have been added
    count = redis_cache.invalidate_tags(["disabled_tag"])
    assert count == 0