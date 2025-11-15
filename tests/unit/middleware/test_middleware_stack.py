import pprint

import pytest

from cachine import InMemoryCache
from cachine.middleware import CompressionMiddleware, EncryptionMiddleware, MetricsMiddleware
from cachine.serializers import JSONSerializer, PickleSerializer


def test_middleware_stack_inmemory_basic():
    """Test basic middleware stacking with compression, encryption, and metrics."""
    base = InMemoryCache(namespace="mw")
    cache = CompressionMiddleware(base, algorithm="gzip", min_size=0)
    cache = EncryptionMiddleware(cache, key="secret", key_id="v1")
    cache = MetricsMiddleware(cache)

    data = {"a": 1, "b": [2, 3]}
    cache.set("k", data, ttl=5)
    assert cache.get("k") == data

    # exercise ttl funcs through the stack
    t = cache.ttl("k")
    assert t is None or (isinstance(t, int) and t >= 0)
    assert cache.persist("k") in (True, False)
    assert cache.delete("k") in (True, False)

    # metrics available
    stats = cache.get_stats()
    assert set(["hits", "misses"]).issubset(stats.keys())
    pprint.pprint(stats)


def test_middleware_forwards_invalidate_tags():
    """Test that middleware properly forwards invalidate_tags to underlying cache."""
    base = InMemoryCache(namespace="mw2")
    cache = MetricsMiddleware(base)

    cache.set("user:1", {"id": 1})
    # add tags via backend helper and use invalidate through middleware
    base.add_tags("user:1", ["users", "user:1"])  # type: ignore[attr-defined]
    stats = cache.get_stats()
    pprint.pprint(stats)
    removed = cache.invalidate_tags(["users"])  # forwarded
    assert removed >= 1
    assert cache.get("user:1") is None


def test_compression_middleware_gzip():
    """Test compression middleware with gzip algorithm."""
    base = InMemoryCache(namespace="comp_gzip")
    cache = CompressionMiddleware(base, algorithm="gzip", min_size=0)

    # Small data
    cache.set("small", "hello")
    assert cache.get("small") == "hello"

    # Large data that benefits from compression
    large_data = "a" * 1000
    cache.set("large", large_data)
    assert cache.get("large") == large_data


def test_compression_middleware_zlib():
    """Test compression middleware with zlib algorithm."""
    base = InMemoryCache(namespace="comp_zlib")
    cache = CompressionMiddleware(base, algorithm="zlib", min_size=0)

    data = "test data" * 100
    cache.set("key", data)
    assert cache.get("key") == data


def test_compression_middleware_min_size():
    """Test compression middleware with min_size threshold."""
    base = InMemoryCache(namespace="comp_min")
    cache = CompressionMiddleware(base, algorithm="gzip", min_size=100)

    # Small data - should not be compressed
    small_data = "x" * 50
    cache.set("small", small_data)
    # Check that it was NOT compressed (no __compressed__ marker)
    raw = base.get("small")
    assert not (isinstance(raw, dict) and raw.get("__compressed__"))

    # Large data - should be compressed
    large_data = "y" * 200
    cache.set("large", large_data)
    # Check that it WAS compressed
    raw = base.get("large")
    assert isinstance(raw, dict) and raw.get("__compressed__")

    # Both should return correct values
    assert cache.get("small") == small_data
    assert cache.get("large") == large_data


def test_compression_middleware_with_serializer():
    """Test compression middleware with JSON serializer."""
    base = InMemoryCache(namespace="comp_ser", serializer=JSONSerializer())
    cache = CompressionMiddleware(base, algorithm="gzip", min_size=0)

    data = {"users": [{"id": i, "name": f"user{i}"} for i in range(100)]}
    cache.set("data", data)
    result = cache.get("data")
    assert result == data


def test_encryption_middleware_basic():
    """Test basic encryption and decryption."""
    base = InMemoryCache(namespace="enc_basic")
    cache = EncryptionMiddleware(base, key="my-secret-key", key_id="v1")

    # String data
    cache.set("key1", "sensitive data")
    assert cache.get("key1") == "sensitive data"

    # Verify data is actually encrypted in storage
    raw = base.get("key1")
    assert isinstance(raw, dict)
    assert raw.get("__encrypted__") is True
    assert raw.get("key_id") == "v1"
    assert "data" in raw


def test_encryption_middleware_with_serializer():
    """Test encryption middleware with serializer."""
    base = InMemoryCache(namespace="enc_ser", serializer=JSONSerializer())
    cache = EncryptionMiddleware(base, key="secret123", key_id="v2")

    data = {"password": "secret", "api_key": "12345"}
    cache.set("credentials", data)
    result = cache.get("credentials")
    assert result == data


def test_encryption_middleware_different_keys():
    """Test encryption with different key IDs."""
    base = InMemoryCache(namespace="enc_keys")
    cache1 = EncryptionMiddleware(base, key="key1", key_id="v1")
    cache2 = EncryptionMiddleware(base, key="key2", key_id="v2")

    cache1.set("data1", "encrypted with key1")
    cache2.set("data2", "encrypted with key2")

    assert cache1.get("data1") == "encrypted with key1"
    assert cache2.get("data2") == "encrypted with key2"


def test_metrics_middleware_hit_miss():
    """Test metrics middleware tracks hits and misses correctly."""
    base = InMemoryCache(namespace="metrics")
    cache = MetricsMiddleware(base)

    # Initial stats
    stats = cache.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0

    # Miss
    result = cache.get("nonexistent")
    assert result is None
    stats = cache.get_stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 0

    # Set and hit
    cache.set("key", "value")
    result = cache.get("key")
    assert result == "value"
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1

    # Another hit
    cache.get("key")
    stats = cache.get_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1


def test_metrics_middleware_hit_rate():
    """Test hit rate calculation in metrics."""
    base = InMemoryCache(namespace="metrics_rate")
    cache = MetricsMiddleware(base)

    cache.set("k1", "v1")
    cache.set("k2", "v2")

    # 2 hits, 0 misses
    cache.get("k1")
    cache.get("k2")
    stats = cache.get_stats()
    assert stats["hit_rate"] == 1.0

    # 2 hits, 1 miss
    cache.get("nonexistent")
    stats = cache.get_stats()
    assert stats["hit_rate"] == pytest.approx(2.0 / 3.0)


def test_full_middleware_stack():
    """Test full stack: Compression -> Encryption -> Metrics."""
    base = InMemoryCache(namespace="full_stack", serializer=PickleSerializer())
    cache = CompressionMiddleware(base, algorithm="gzip", min_size=50)
    cache = EncryptionMiddleware(cache, key="super-secret", key_id="prod-v1")
    cache = MetricsMiddleware(cache)

    # Complex data that will be serialized, compressed, and encrypted
    data = {
        "users": [{"id": i, "name": f"User {i}", "data": "x" * 100} for i in range(10)],
        "metadata": {"timestamp": 1234567890, "version": "1.0"},
    }

    # Set and get through full stack
    cache.set("complex_data", data, ttl=60)
    result = cache.get("complex_data")
    assert result == data

    # Verify metrics
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0
    assert stats["avg_latency_ms"] > 0


def test_middleware_get_default_value():
    """Test that default values work through middleware stack."""
    base = InMemoryCache(namespace="defaults")
    cache = CompressionMiddleware(base, algorithm="gzip")
    cache = EncryptionMiddleware(cache, key="key")
    cache = MetricsMiddleware(cache)

    # Get non-existent key with default
    result = cache.get("nonexistent", default="default_value")
    assert result == "default_value"

    # Verify it was counted as a miss
    stats = cache.get_stats()
    assert stats["misses"] == 1


def test_middleware_delete_through_stack():
    """Test delete operation through middleware stack."""
    base = InMemoryCache(namespace="delete_test")
    cache = CompressionMiddleware(base, algorithm="gzip")
    cache = EncryptionMiddleware(cache, key="key")

    cache.set("key", "value")
    assert cache.get("key") == "value"

    # Delete through stack
    result = cache.delete("key")
    assert result is True

    # Verify deleted
    assert cache.get("key") is None


def test_middleware_exists_through_stack():
    """Test exists operation through middleware stack."""
    base = InMemoryCache(namespace="exists_test")
    cache = CompressionMiddleware(base, algorithm="gzip")
    cache = EncryptionMiddleware(cache, key="key")

    assert cache.exists("key") is False

    cache.set("key", "value")
    assert cache.exists("key") is True

    cache.delete("key")
    assert cache.exists("key") is False


def test_compression_invalid_algorithm():
    """Test that invalid compression algorithm raises error."""
    base = InMemoryCache(namespace="invalid_algo")
    cache = CompressionMiddleware(base, algorithm="invalid")

    with pytest.raises(ValueError, match="Unsupported compression algorithm"):
        cache.set("key", "value")
