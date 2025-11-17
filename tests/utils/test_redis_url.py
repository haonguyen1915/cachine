"""Tests for Redis URL parsing utilities."""

import pytest

from cachine.models import (
    RedisClusterConfig,
    RedisSentinelConfig,
    RedisSingleConfig,
)
from cachine.utils.redis_url import RedisURLParseError, parse_redis_url


class TestParseSingleRedisURL:
    """Tests for parsing single Redis instance URLs."""

    def test_basic_url(self) -> None:
        """Test parsing a basic Redis URL."""
        config = parse_redis_url("redis://localhost:6379/0")
        assert isinstance(config, RedisSingleConfig)
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.ssl is False

    def test_url_with_password(self) -> None:
        """Test parsing Redis URL with password."""
        config = parse_redis_url("redis://:mypassword@localhost:6379/0")
        assert isinstance(config, RedisSingleConfig)
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password == "mypassword"
        assert config.ssl is False

    def test_url_with_username_and_password(self) -> None:
        """Test parsing Redis URL with username and password (ACL)."""
        config = parse_redis_url("redis://myuser:mypassword@localhost:6379/0")
        assert isinstance(config, RedisSingleConfig)
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.username == "myuser"
        assert config.password == "mypassword"
        assert config.ssl is False

    def test_url_with_ssl(self) -> None:
        """Test parsing Redis SSL URL."""
        config = parse_redis_url("rediss://localhost:6379/0")
        assert isinstance(config, RedisSingleConfig)
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.ssl is True

    def test_url_with_custom_port(self) -> None:
        """Test parsing Redis URL with custom port."""
        config = parse_redis_url("redis://localhost:7000/0")
        assert isinstance(config, RedisSingleConfig)
        assert config.port == 7000

    def test_url_with_different_db(self) -> None:
        """Test parsing Redis URL with different database number."""
        config = parse_redis_url("redis://localhost:6379/5")
        assert isinstance(config, RedisSingleConfig)
        assert config.db == 5

    def test_url_without_db(self) -> None:
        """Test parsing Redis URL without explicit database (defaults to 0)."""
        config = parse_redis_url("redis://localhost:6379")
        assert isinstance(config, RedisSingleConfig)
        assert config.db == 0

    def test_url_with_query_params(self) -> None:
        """Test parsing Redis URL with query parameters."""
        config = parse_redis_url("redis://localhost:6379/0?socket_timeout=5&socket_connect_timeout=3")
        assert isinstance(config, RedisSingleConfig)
        assert config.socket_timeout == 5.0
        assert config.socket_connect_timeout == 3.0

    def test_url_with_boolean_param(self) -> None:
        """Test parsing Redis URL with boolean parameters."""
        config = parse_redis_url("redis://localhost:6379/0?retry_on_timeout=true&decode_responses=1")
        assert isinstance(config, RedisSingleConfig)
        assert config.retry_on_timeout is True
        assert config.decode_responses is True

    def test_url_with_float_param(self) -> None:
        """Test parsing Redis URL with float parameters."""
        config = parse_redis_url("redis://localhost:6379/0?socket_timeout=2.5")
        assert isinstance(config, RedisSingleConfig)
        assert config.socket_timeout == 2.5

    def test_url_default_port(self) -> None:
        """Test parsing Redis URL without port (defaults to 6379)."""
        config = parse_redis_url("redis://localhost/0")
        assert isinstance(config, RedisSingleConfig)
        assert config.port == 6379

    def test_url_default_host(self) -> None:
        """Test parsing Redis URL without host (defaults to localhost)."""
        config = parse_redis_url("redis://:6379/0")
        assert isinstance(config, RedisSingleConfig)
        assert config.host == "localhost"


class TestParseClusterRedisURL:
    """Tests for parsing Redis Cluster URLs."""

    def test_cluster_url_basic(self) -> None:
        """Test parsing basic Redis Cluster URL."""
        config = parse_redis_url("redis://node1:7000,node2:7001,node3:7002")
        assert isinstance(config, RedisClusterConfig)
        assert len(config.nodes) == 3
        assert config.nodes[0].host == "node1"
        assert config.nodes[0].port == 7000
        assert config.nodes[1].host == "node2"
        assert config.nodes[1].port == 7001
        assert config.nodes[2].host == "node3"
        assert config.nodes[2].port == 7002
        assert config.password is None
        assert config.ssl is False

    def test_cluster_url_with_password(self) -> None:
        """Test parsing Redis Cluster URL with password."""
        config = parse_redis_url("redis://:mypassword@node1:7000,node2:7001,node3:7002")
        assert isinstance(config, RedisClusterConfig)
        assert config.password == "mypassword"
        assert len(config.nodes) == 3

    def test_cluster_url_with_username(self) -> None:
        """Test parsing Redis Cluster URL with username and password."""
        config = parse_redis_url("redis://user:pass@node1:7000,node2:7001")
        assert isinstance(config, RedisClusterConfig)
        assert config.username == "user"
        assert config.password == "pass"

    def test_cluster_url_with_ssl(self) -> None:
        """Test parsing Redis Cluster SSL URL."""
        config = parse_redis_url("rediss://node1:7000,node2:7001,node3:7002")
        assert isinstance(config, RedisClusterConfig)
        assert config.ssl is True

    def test_cluster_url_default_ports(self) -> None:
        """Test parsing Redis Cluster URL with default ports."""
        config = parse_redis_url("redis://node1,node2,node3")
        assert isinstance(config, RedisClusterConfig)
        assert len(config.nodes) == 3
        assert config.nodes[0].port == 6379
        assert config.nodes[1].port == 6379
        assert config.nodes[2].port == 6379

    def test_cluster_url_mixed_ports(self) -> None:
        """Test parsing Redis Cluster URL with mixed explicit and default ports."""
        config = parse_redis_url("redis://node1:7000,node2,node3:7002")
        assert isinstance(config, RedisClusterConfig)
        assert config.nodes[0].port == 7000
        assert config.nodes[1].port == 6379
        assert config.nodes[2].port == 7002

    def test_cluster_url_with_query_params(self) -> None:
        """Test parsing Redis Cluster URL with query parameters."""
        config = parse_redis_url("redis://node1:7000,node2:7001?socket_timeout=10")
        assert isinstance(config, RedisClusterConfig)
        assert config.extra["socket_timeout"] == 10.0


class TestParseSentinelRedisURL:
    """Tests for parsing Redis Sentinel URLs."""

    def test_sentinel_url_basic(self) -> None:
        """Test parsing basic Redis Sentinel URL."""
        config = parse_redis_url("redis+sentinel://mymaster/0?sentinels=sentinel1:26379,sentinel2:26379")
        assert isinstance(config, RedisSentinelConfig)
        assert config.service_name == "mymaster"
        assert config.db == 0
        assert len(config.sentinels) == 2
        assert config.sentinels[0] == ("sentinel1", 26379)
        assert config.sentinels[1] == ("sentinel2", 26379)
        assert config.password is None
        assert config.ssl is False

    def test_sentinel_url_with_password(self) -> None:
        """Test parsing Redis Sentinel URL with password."""
        config = parse_redis_url("redis+sentinel://:mypassword@mymaster/0?sentinels=sentinel1:26379")
        assert isinstance(config, RedisSentinelConfig)
        assert config.service_name == "mymaster"
        assert config.password == "mypassword"

    def test_sentinel_url_with_username(self) -> None:
        """Test parsing Redis Sentinel URL with username and password."""
        config = parse_redis_url("redis+sentinel://user:pass@mymaster/0?sentinels=sentinel1:26379")
        assert isinstance(config, RedisSentinelConfig)
        assert config.username == "user"
        assert config.password == "pass"

    def test_sentinel_url_with_ssl(self) -> None:
        """Test parsing Redis Sentinel SSL URL."""
        config = parse_redis_url("rediss+sentinel://mymaster/0?sentinels=sentinel1:26379")
        assert isinstance(config, RedisSentinelConfig)
        assert config.ssl is True

    def test_sentinel_url_without_db(self) -> None:
        """Test parsing Redis Sentinel URL without explicit database."""
        config = parse_redis_url("redis+sentinel://mymaster?sentinels=sentinel1:26379")
        assert isinstance(config, RedisSentinelConfig)
        assert config.db == 0

    def test_sentinel_url_default_ports(self) -> None:
        """Test parsing Redis Sentinel URL with default sentinel ports."""
        config = parse_redis_url("redis+sentinel://mymaster/0?sentinels=sentinel1,sentinel2")
        assert isinstance(config, RedisSentinelConfig)
        assert config.sentinels[0] == ("sentinel1", 26379)
        assert config.sentinels[1] == ("sentinel2", 26379)

    def test_sentinel_url_different_db(self) -> None:
        """Test parsing Redis Sentinel URL with different database."""
        config = parse_redis_url("redis+sentinel://mymaster/3?sentinels=sentinel1:26379")
        assert isinstance(config, RedisSentinelConfig)
        assert config.db == 3

    def test_sentinel_url_with_extra_params(self) -> None:
        """Test parsing Redis Sentinel URL with extra query parameters."""
        config = parse_redis_url("redis+sentinel://mymaster/0?sentinels=sentinel1:26379&socket_timeout=5")
        assert isinstance(config, RedisSentinelConfig)
        assert config.extra["socket_timeout"] == 5.0


class TestRedisURLErrors:
    """Tests for error handling in Redis URL parsing."""

    def test_empty_url(self) -> None:
        """Test parsing empty URL raises error."""
        with pytest.raises(RedisURLParseError, match="URL cannot be empty"):
            parse_redis_url("")

    def test_invalid_scheme(self) -> None:
        """Test parsing URL with invalid scheme raises error."""
        with pytest.raises(RedisURLParseError, match="Unsupported scheme"):
            parse_redis_url("http://localhost:6379/0")

    def test_invalid_db_number(self) -> None:
        """Test parsing URL with invalid database number raises error."""
        with pytest.raises(RedisURLParseError, match="Invalid database number"):
            parse_redis_url("redis://localhost:6379/abc")

    def test_invalid_cluster_port(self) -> None:
        """Test parsing cluster URL with invalid port raises error."""
        with pytest.raises(RedisURLParseError, match="Invalid port in node"):
            parse_redis_url("redis://node1:abc,node2:7001")

    def test_sentinel_without_sentinels_param(self) -> None:
        """Test parsing sentinel URL without sentinels parameter raises error."""
        with pytest.raises(RedisURLParseError, match="must include 'sentinels' query parameter"):
            parse_redis_url("redis+sentinel://mymaster/0")

    def test_sentinel_without_service_name(self) -> None:
        """Test parsing sentinel URL without service name raises error."""
        with pytest.raises(RedisURLParseError, match="Service name .* is required"):
            parse_redis_url("redis+sentinel:///0?sentinels=sentinel1:26379")

    def test_sentinel_invalid_sentinel_port(self) -> None:
        """Test parsing sentinel URL with invalid sentinel port raises error."""
        with pytest.raises(RedisURLParseError, match="Invalid port in sentinel"):
            parse_redis_url("redis+sentinel://mymaster/0?sentinels=sentinel1:abc")

    def test_sentinel_empty_sentinels(self) -> None:
        """Test parsing sentinel URL with empty sentinels raises error."""
        with pytest.raises(RedisURLParseError, match="Sentinel URL must include 'sentinels' query parameter"):
            parse_redis_url("redis+sentinel://mymaster/0?sentinels=")

    def test_cluster_empty_nodes(self) -> None:
        """Test parsing cluster URL with no valid nodes raises error."""
        with pytest.raises(RedisURLParseError, match="No nodes found"):
            parse_redis_url("redis://,,,")


class TestCreateCacheFromURL:
    """Tests for creating cache instances from URLs."""

    def test_create_single_cache_from_url(self) -> None:
        """Test creating single Redis cache from URL."""
        from cachine.utils.redis_url import create_cache_from_url

        # Mock test - just verify it doesn't crash and returns correct type
        try:
            cache = create_cache_from_url("redis://localhost:6379/0", namespace="test")
            assert cache is not None
            assert hasattr(cache, "get")
            assert hasattr(cache, "set")
        except RuntimeError:
            # Redis not installed or not available
            pytest.skip("Redis not available")

    def test_create_cache_with_kwargs_override(self) -> None:
        """Test that kwargs override URL parameters."""
        from cachine.utils.redis_url import create_cache_from_url

        try:
            cache = create_cache_from_url(
                "redis://localhost:6379/0",
                namespace="myapp",
                db=5,  # Override db from URL
            )
            assert cache is not None
        except RuntimeError:
            pytest.skip("Redis not available")


class TestComplexURLs:
    """Tests for complex real-world URL scenarios."""

    def test_url_with_special_characters_in_password(self) -> None:
        """Test parsing URL with special characters in password."""
        # Note: urlparse doesn't decode percent-encoded characters automatically
        # Users should use urllib.parse.unquote if needed
        config = parse_redis_url("redis://:p@ss%40word@localhost:6379/0")
        assert config.password == "p@ss%40word"  # Still URL-encoded

    def test_url_with_ipv4_host(self) -> None:
        """Test parsing URL with IPv4 address."""
        config = parse_redis_url("redis://192.168.1.100:6379/0")
        assert isinstance(config, RedisSingleConfig)
        assert config.host == "192.168.1.100"

    def test_url_with_multiple_query_params(self) -> None:
        """Test parsing URL with multiple query parameters."""
        config = parse_redis_url(
            "redis://localhost:6379/0?socket_timeout=5&socket_connect_timeout=3&retry_on_timeout=true"
        )
        assert isinstance(config, RedisSingleConfig)
        assert config.socket_timeout == 5.0
        assert config.socket_connect_timeout == 3.0
        assert config.retry_on_timeout is True

    def test_cluster_url_production_like(self) -> None:
        """Test parsing production-like cluster URL."""
        config = parse_redis_url(
            "rediss://user:pass@prod-redis-01.example.com:7000,"
            "prod-redis-02.example.com:7001,"
            "prod-redis-03.example.com:7002"
        )
        assert isinstance(config, RedisClusterConfig)
        assert config.ssl is True
        assert config.username == "user"
        assert config.password == "pass"
        assert len(config.nodes) == 3
        assert config.nodes[0].host == "prod-redis-01.example.com"

    def test_sentinel_url_production_like(self) -> None:
        """Test parsing production-like sentinel URL."""
        config = parse_redis_url(
            "rediss+sentinel://user:pass@mymaster/1?"
            "sentinels=sentinel1.example.com:26379,sentinel2.example.com:26379,sentinel3.example.com:26379"
        )
        assert isinstance(config, RedisSentinelConfig)
        assert config.ssl is True
        assert config.username == "user"
        assert config.password == "pass"
        assert config.service_name == "mymaster"
        assert config.db == 1
        assert len(config.sentinels) == 3
