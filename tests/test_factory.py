"""Tests for cache factory functions."""

import pytest

from cachine import async_cache_from_url, cache_from_url
from cachine.backends.redis.async_ import AsyncRedisCache
from cachine.backends.redis.sync import RedisCache
from cachine.exceptions import RedisURLParseError


class TestCacheFromURL:
    """Tests for cache_from_url factory function (sync)."""

    def test_redis_single_url(self) -> None:
        """Test creating sync Redis cache from single instance URL."""
        cache = cache_from_url("redis://localhost:6379/0", namespace="test")
        assert isinstance(cache, RedisCache)
        assert cache._ns == "test:"

    def test_redis_ssl_url(self) -> None:
        """Test creating sync Redis cache from SSL URL."""
        cache = cache_from_url("rediss://localhost:6379/0", namespace="test")
        assert isinstance(cache, RedisCache)

    def test_redis_cluster_url(self) -> None:
        """Test parsing cluster URL (connection verification only)."""
        from cachine.models import RedisClusterConfig
        from cachine.utils.redis_url import parse_redis_url

        # Just verify URL parsing works correctly
        config = parse_redis_url(
            "redis://localhost:7000,localhost:7001,localhost:7002"
        )
        assert isinstance(config, RedisClusterConfig)
        assert len(config.nodes) == 3
        assert config.nodes[0].host == "localhost"
        assert config.nodes[0].port == 7000

    def test_redis_sentinel_url(self) -> None:
        """Test creating sync Redis cache from sentinel URL."""
        cache = cache_from_url(
            "redis+sentinel://mymaster/0?sentinels=sentinel1:26379,sentinel2:26379",
            namespace="test",
        )
        assert isinstance(cache, RedisCache)

    def test_redis_url_with_params(self) -> None:
        """Test creating sync Redis cache from URL with query parameters."""
        from cachine.models import RedisSingleConfig

        cache = cache_from_url(
            "redis://localhost:6379/0?socket_timeout=5&retry_on_timeout=true",
            namespace="test",
        )
        assert isinstance(cache, RedisCache)
        assert isinstance(cache._config, RedisSingleConfig)
        assert cache._config.socket_timeout == 5.0
        assert cache._config.retry_on_timeout is True

    def test_empty_url_raises_error(self) -> None:
        """Test that empty URL raises RedisURLParseError."""
        with pytest.raises(RedisURLParseError, match="URL cannot be empty"):
            cache_from_url("")

    def test_unsupported_scheme_raises_error(self) -> None:
        """Test that unsupported scheme raises RedisURLParseError."""
        with pytest.raises(RedisURLParseError, match="Unsupported cache URL scheme"):
            cache_from_url("memcached://localhost:11211")

    def test_cache_from_url_with_serializer(self) -> None:
        """Test creating sync cache from URL with custom serializer."""
        from cachine.serializers import JSONSerializer

        serializer = JSONSerializer()
        cache = cache_from_url(
            "redis://localhost:6379/0", namespace="test", serializer=serializer
        )
        assert isinstance(cache, RedisCache)

    def test_cache_from_url_with_all_timeout_params(self) -> None:
        """Test creating cache with all timeout configuration parameters."""
        from cachine.models import RedisSingleConfig

        cache = cache_from_url(
            "redis://localhost:6379/0?"
            "socket_timeout=5.5&"
            "socket_connect_timeout=3.0&"
            "retry_on_timeout=true&"
            "decode_responses=yes",
            namespace="test",
        )
        assert isinstance(cache, RedisCache)
        assert isinstance(cache._config, RedisSingleConfig)
        assert cache._config.socket_timeout == 5.5
        assert cache._config.socket_connect_timeout == 3.0
        assert cache._config.retry_on_timeout is True
        assert cache._config.decode_responses is True

    def test_cache_from_url_with_credentials(self) -> None:
        """Test creating cache with username and password from URL."""
        from cachine.models import RedisSingleConfig

        cache = cache_from_url(
            "redis://myuser:mypassword@localhost:6379/0",
            namespace="test",
        )
        assert isinstance(cache, RedisCache)
        assert isinstance(cache._config, RedisSingleConfig)
        assert cache._config.username == "myuser"
        assert cache._config.password == "mypassword"

    def test_cache_from_url_cluster_with_ssl_and_timeouts(self) -> None:
        """Test creating cluster cache with SSL and timeout parameters."""
        from cachine.models import RedisClusterConfig
        from cachine.utils.redis_url import parse_redis_url

        # Parse URL to verify config (avoid cluster connection)
        config = parse_redis_url(
            "rediss://user:pass@node1:7000,node2:7001,node3:7002?"
            "socket_timeout=10&"
            "retry_on_timeout=1"
        )
        assert isinstance(config, RedisClusterConfig)
        assert config.ssl is True
        assert config.username == "user"
        assert config.password == "pass"
        assert config.socket_timeout == 10.0
        assert config.retry_on_timeout is True
        assert len(config.nodes) == 3

    def test_cache_from_url_sentinel_with_full_config(self) -> None:
        """Test creating sentinel cache with full configuration."""
        from cachine.models import RedisSentinelConfig

        cache = cache_from_url(
            "rediss+sentinel://user:pass@mymaster/2?"
            "sentinels=s1:26379,s2:26379,s3:26379&"
            "socket_timeout=5&"
            "socket_connect_timeout=2&"
            "decode_responses=true",
            namespace="test",
        )
        assert isinstance(cache, RedisCache)
        assert isinstance(cache._config, RedisSentinelConfig)
        assert cache._config.ssl is True
        assert cache._config.username == "user"
        assert cache._config.password == "pass"
        assert cache._config.service_name == "mymaster"
        assert cache._config.db == 2
        assert len(cache._config.sentinels) == 3
        assert cache._config.socket_timeout == 5.0
        assert cache._config.socket_connect_timeout == 2.0
        assert cache._config.decode_responses is True


class TestAsyncCacheFromURL:
    """Tests for async_cache_from_url factory function (async)."""

    def test_async_redis_single_url(self) -> None:
        """Test creating async Redis cache from single instance URL."""
        cache = async_cache_from_url("redis://localhost:6379/0", namespace="test")
        assert isinstance(cache, AsyncRedisCache)
        assert cache._ns == "test:"

    def test_async_redis_ssl_url(self) -> None:
        """Test creating async Redis cache from SSL URL."""
        cache = async_cache_from_url("rediss://localhost:6379/0", namespace="test")
        assert isinstance(cache, AsyncRedisCache)

    def test_async_redis_cluster_url(self) -> None:
        """Test creating async Redis cache from cluster URL."""
        cache = async_cache_from_url(
            "redis://localhost:7000,localhost:7001,localhost:7002", namespace="test"
        )
        assert isinstance(cache, AsyncRedisCache)
        # Verify cluster config was created
        from cachine.models import RedisClusterConfig

        assert isinstance(cache._config, RedisClusterConfig)
        assert len(cache._config.nodes) == 3

    def test_async_redis_sentinel_url(self) -> None:
        """Test creating async Redis cache from sentinel URL."""
        cache = async_cache_from_url(
            "redis+sentinel://mymaster/0?sentinels=sentinel1:26379,sentinel2:26379",
            namespace="test",
        )
        assert isinstance(cache, AsyncRedisCache)

    def test_async_redis_url_with_params(self) -> None:
        """Test creating async Redis cache from URL with query parameters."""
        from cachine.models import RedisSingleConfig

        cache = async_cache_from_url(
            "redis://localhost:6379/0?socket_timeout=5&retry_on_timeout=true",
            namespace="test",
        )
        assert isinstance(cache, AsyncRedisCache)
        assert isinstance(cache._config, RedisSingleConfig)
        assert cache._config.socket_timeout == 5.0
        assert cache._config.retry_on_timeout is True

    def test_async_empty_url_raises_error(self) -> None:
        """Test that empty URL raises RedisURLParseError."""
        with pytest.raises(RedisURLParseError, match="URL cannot be empty"):
            async_cache_from_url("")

    def test_async_unsupported_scheme_raises_error(self) -> None:
        """Test that unsupported scheme raises RedisURLParseError."""
        with pytest.raises(RedisURLParseError, match="Unsupported cache URL scheme"):
            async_cache_from_url("memcached://localhost:11211")

    def test_async_cache_from_url_with_serializer(self) -> None:
        """Test creating async cache from URL with custom serializer."""
        from cachine.serializers import JSONSerializer

        serializer = JSONSerializer()
        cache = async_cache_from_url(
            "redis://localhost:6379/0", namespace="test", serializer=serializer
        )
        assert isinstance(cache, AsyncRedisCache)

    def test_async_cache_from_url_with_all_timeout_params(self) -> None:
        """Test creating async cache with all timeout configuration parameters."""
        from cachine.models import RedisSingleConfig

        cache = async_cache_from_url(
            "redis://localhost:6379/0?"
            "socket_timeout=5.5&"
            "socket_connect_timeout=3.0&"
            "retry_on_timeout=true&"
            "decode_responses=yes",
            namespace="test",
        )
        assert isinstance(cache, AsyncRedisCache)
        assert isinstance(cache._config, RedisSingleConfig)
        assert cache._config.socket_timeout == 5.5
        assert cache._config.socket_connect_timeout == 3.0
        assert cache._config.retry_on_timeout is True
        assert cache._config.decode_responses is True

    def test_async_cache_from_url_with_credentials(self) -> None:
        """Test creating async cache with username and password from URL."""
        from cachine.models import RedisSingleConfig

        cache = async_cache_from_url(
            "redis://myuser:mypassword@localhost:6379/0",
            namespace="test",
        )
        assert isinstance(cache, AsyncRedisCache)
        assert isinstance(cache._config, RedisSingleConfig)
        assert cache._config.username == "myuser"
        assert cache._config.password == "mypassword"

    def test_async_cache_from_url_cluster_with_ssl_and_timeouts(self) -> None:
        """Test creating async cluster cache with SSL and timeout parameters."""
        from cachine.models import RedisClusterConfig

        cache = async_cache_from_url(
            "rediss://user:pass@localhost:7000,localhost:7001,localhost:7002?"
            "socket_timeout=10&"
            "retry_on_timeout=1",
            namespace="test",
        )
        assert isinstance(cache, AsyncRedisCache)
        assert isinstance(cache._config, RedisClusterConfig)
        assert cache._config.ssl is True
        assert cache._config.username == "user"
        assert cache._config.password == "pass"
        assert cache._config.socket_timeout == 10.0
        assert cache._config.retry_on_timeout is True
        assert len(cache._config.nodes) == 3

    def test_async_cache_from_url_sentinel_with_full_config(self) -> None:
        """Test creating async sentinel cache with full configuration."""
        from cachine.models import RedisSentinelConfig

        cache = async_cache_from_url(
            "rediss+sentinel://user:pass@mymaster/2?"
            "sentinels=s1:26379,s2:26379,s3:26379&"
            "socket_timeout=5&"
            "socket_connect_timeout=2&"
            "decode_responses=true",
            namespace="test",
        )
        assert isinstance(cache, AsyncRedisCache)
        assert isinstance(cache._config, RedisSentinelConfig)
        assert cache._config.ssl is True
        assert cache._config.username == "user"
        assert cache._config.password == "pass"
        assert cache._config.service_name == "mymaster"
        assert cache._config.db == 2
        assert len(cache._config.sentinels) == 3
        assert cache._config.socket_timeout == 5.0
        assert cache._config.socket_connect_timeout == 2.0
        assert cache._config.decode_responses is True


class TestFactoryIntegration:
    """Integration tests for factory functions."""

    def test_cache_from_url_vs_direct_creation(self) -> None:
        """Test that cache_from_url creates equivalent cache to direct creation."""
        # Create via URL
        cache1 = cache_from_url("redis://localhost:6379/0", namespace="test")

        # Create directly
        from cachine.models import RedisSingleConfig

        config = RedisSingleConfig(host="localhost", port=6379, db=0)
        cache2 = RedisCache(config, namespace="test")

        # Both should be RedisCache with same namespace
        assert isinstance(cache1, RedisCache)
        assert isinstance(cache2, RedisCache)
        assert cache1._ns == cache2._ns

    def test_cache_from_url_exports(self) -> None:
        """Test that cache_from_url is properly exported from main package."""
        from cachine import cache_from_url as imported_factory

        assert imported_factory is cache_from_url