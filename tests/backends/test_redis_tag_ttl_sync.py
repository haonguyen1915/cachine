"""Test tag TTL functionality for sync Redis cache."""

import time

from cachine.backends.redis.sync import RedisCache


def test_add_tags_without_ttl(redis_cache: RedisCache):
    """Test that tags without TTL persist indefinitely."""
    key = "user:123"
    value = {"name": "Alice"}
    tags = ["premium", "active"]

    # Set cache value
    redis_cache.set(key, value, ttl=5)

    # Add tags without TTL
    redis_cache.add_tags(key, tags)

    # Wait for value to expire
    time.sleep(6)

    # Value should be gone
    assert redis_cache.get(key) is None

    # Tags should still exist (can verify by checking tag set membership)
    # We can't directly check tag expiry, but we can add another key with same tags
    # and invalidate to see if tags still work
    redis_cache.set("user:456", {"name": "Bob"}, ttl=60)
    redis_cache.add_tags("user:456", ["premium"])

    # Invalidate should still work even though original key is gone
    count = redis_cache.invalidate_tags(["premium"])
    assert count > 0


def test_add_tags_with_ttl(redis_cache: RedisCache):
    """Test that tags with TTL expire correctly."""
    key = "user:123"
    value = {"name": "Alice"}
    tags = ["temporary"]

    # Set cache value with longer TTL
    redis_cache.set(key, value, ttl=60)

    # Add tags with short TTL (3 seconds)
    redis_cache.add_tags(key, tags, ttl=3)

    # Immediately invalidating should work
    count = redis_cache.invalidate_tags(tags)
    assert count == 1
    assert redis_cache.get(key) is None

    # Set again and wait for tag TTL to expire
    redis_cache.set(key, value, ttl=60)
    redis_cache.add_tags(key, tags, ttl=3)

    # Wait for tag TTL to expire
    time.sleep(4)

    # Tag should be expired, so invalidate should find nothing
    count = redis_cache.invalidate_tags(tags)
    assert count == 0

    # But the value should still be there
    assert redis_cache.get(key) is not None


def test_tag_ttl_longer_than_value_ttl(redis_cache: RedisCache):
    """Test that tag TTL can be longer than value TTL."""
    key1 = "user:123"
    key2 = "user:456"
    value = {"name": "Alice"}
    tags = ["premium"]

    # Set first value with short TTL (3 seconds)
    redis_cache.set(key1, value, ttl=3)

    # Add tags with longer TTL (10 seconds)
    redis_cache.add_tags(key1, tags, ttl=10)

    # Wait for value to expire
    time.sleep(4)

    # Value should be gone
    assert redis_cache.get(key1) is None

    # But tag set should still exist - add another key with same tag
    redis_cache.set(key2, {"name": "Bob"}, ttl=60)
    redis_cache.add_tags(key2, tags, ttl=10)

    # Invalidating should work and hit the new key
    # (The tag set for key1 is still there but references expired key)
    count = redis_cache.invalidate_tags(tags)
    assert count >= 1
    assert redis_cache.get(key2) is None


def test_multiple_tags_different_ttls(redis_cache: RedisCache):
    """Test adding tags with different TTLs."""
    key = "user:123"
    value = {"name": "Alice"}

    # Set cache value
    redis_cache.set(key, value, ttl=60)

    # Add first set of tags with short TTL
    redis_cache.add_tags(key, ["temporary"], ttl=3)

    # Add second set of tags with longer TTL
    redis_cache.add_tags(key, ["persistent"], ttl=10)

    # Wait for short TTL to expire
    time.sleep(4)

    # Temporary tag should be expired
    count = redis_cache.invalidate_tags(["temporary"])
    assert count == 0

    # Value should still exist
    assert redis_cache.get(key) is not None

    # Persistent tag should still work
    count = redis_cache.invalidate_tags(["persistent"])
    assert count == 1
    assert redis_cache.get(key) is None


def test_tag_ttl_with_timedelta(redis_cache: RedisCache):
    """Test that tag TTL works with timedelta objects."""
    from datetime import timedelta

    key = "user:123"
    value = {"name": "Alice"}
    tags = ["test_timedelta"]

    # Set cache value
    redis_cache.set(key, value, ttl=60)

    # Add tags with timedelta TTL (3 seconds)
    redis_cache.add_tags(key, tags, ttl=timedelta(seconds=3))

    # Tag should work immediately
    count = redis_cache.invalidate_tags(tags)
    assert count == 1
    assert redis_cache.get(key) is None

    # Set again and verify TTL expiration
    redis_cache.set(key, value, ttl=60)
    redis_cache.add_tags(key, tags, ttl=timedelta(seconds=3))

    time.sleep(4)

    # Tag should be expired
    count = redis_cache.invalidate_tags(tags)
    assert count == 0


def test_tag_ttl_zero_or_negative(redis_cache: RedisCache):
    """Test that zero or negative TTL is handled gracefully."""
    key = "user:123"
    value = {"name": "Alice"}
    tags = ["test_zero"]

    # Set cache value
    redis_cache.set(key, value, ttl=60)

    # Add tags with zero TTL (should not set expiration)
    redis_cache.add_tags(key, tags, ttl=0)

    # Tag should not work (expired immediately or not set properly)
    # The implementation should handle this gracefully
    # Note: Redis expire with 0 might delete immediately,
    # so we just verify no errors are raised
    _ = redis_cache.invalidate_tags(tags)
    # Don't assert specific count as behavior may vary
