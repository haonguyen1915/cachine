"""Example usage of Redis URL parsing utilities."""

from cachine.utils import create_cache_from_url, parse_redis_url
from cachine.serializers import JSONSerializer


def example_parse_urls() -> None:
    """Demonstrate parsing different Redis URL formats."""

    # Single Redis instance
    print("=" * 60)
    print("Single Redis Instance")
    print("=" * 60)
    config = parse_redis_url("redis://localhost:6379/0")
    print(f"Type: {config['type']}")
    print(f"Host: {config['host']}")
    print(f"Port: {config['port']}")
    print(f"DB: {config['db']}")
    print()

    # Redis with password and SSL
    print("=" * 60)
    print("Redis with Password and SSL")
    print("=" * 60)
    config = parse_redis_url("rediss://user:mypassword@localhost:6379/1?socket_timeout=5")
    print(f"Type: {config['type']}")
    print(f"Host: {config['host']}")
    print(f"Username: {config.get('username')}")
    print(f"Password: {config['password']}")
    print(f"SSL: {config['ssl']}")
    print(f"Socket Timeout: {config.get('socket_timeout')}")
    print()

    # Redis Cluster
    print("=" * 60)
    print("Redis Cluster")
    print("=" * 60)
    config = parse_redis_url("redis://node1:7000,node2:7001,node3:7002")
    print(f"Type: {config['type']}")
    print(f"Nodes: {config['nodes']}")
    print()

    # Redis Sentinel
    print("=" * 60)
    print("Redis Sentinel")
    print("=" * 60)
    config = parse_redis_url(
        "redis+sentinel://mymaster/0?sentinels=sentinel1:26379,sentinel2:26379,sentinel3:26379"
    )
    print(f"Type: {config['type']}")
    print(f"Service Name: {config['service_name']}")
    print(f"Sentinels: {config['sentinels']}")
    print(f"DB: {config['db']}")
    print()


def example_create_cache() -> None:
    """Demonstrate creating cache instances from URLs."""

    print("=" * 60)
    print("Creating Cache from URL")
    print("=" * 60)

    try:
        # Create a single Redis cache from URL
        cache = create_cache_from_url(
            "redis://localhost:6379/0",
            namespace="myapp",
            serializer=JSONSerializer(),
        )

        print("✓ Successfully created cache instance")
        print(f"  Type: {type(cache).__name__}")
        print(f"  Has get method: {hasattr(cache, 'get')}")
        print(f"  Has set method: {hasattr(cache, 'set')}")

        # Example usage (may fail if Redis requires authentication)
        try:
            cache.set("test_key", {"message": "Hello from URL-created cache!"}, ttl=60)
            value = cache.get("test_key")
            print(f"  Retrieved value: {value}")
        except Exception as e:
            print(f"  Note: Could not connect to Redis: {type(e).__name__}")
            print(f"        This is expected if Redis is not running or requires authentication")
        finally:
            cache.close()

    except RuntimeError as e:
        print(f"✗ Redis not available: {e}")
        print("  Install redis-py to use Redis caching: pip install redis")

    print()


def example_environment_based_config() -> None:
    """Demonstrate using environment variables for configuration."""
    import os

    print("=" * 60)
    print("Environment-Based Configuration")
    print("=" * 60)

    # In real applications, read from environment variables
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"Redis URL from environment: {redis_url}")

    config = parse_redis_url(redis_url)
    print(f"Parsed config: {config}")

    # You can override specific parameters
    try:
        cache = create_cache_from_url(
            redis_url,
            namespace=os.getenv("CACHE_NAMESPACE", "default"),
            serializer=JSONSerializer(),
        )
        print("✓ Cache created successfully from environment config")
        cache.close()
    except RuntimeError:
        print("✗ Redis not available")

    print()


def main() -> None:
    """Run all examples."""
    example_parse_urls()
    example_create_cache()
    example_environment_based_config()

    print("=" * 60)
    print("Supported URL Formats:")
    print("=" * 60)
    print("Single:    redis://[:password@]host:port[/db][?param=value]")
    print("SSL:       rediss://[:password@]host:port[/db][?param=value]")
    print("Cluster:   redis://host1:port1,host2:port2,host3:port3")
    print("Sentinel:  redis+sentinel://service_name[/db]?sentinels=host1:port1,host2:port2")
    print()


if __name__ == "__main__":
    main()