"""Example: constructing Redis caches from URLs.

Use ``RedisCache.from_url`` (or ``AsyncRedisCache.from_url``) when your
connection string comes from an environment variable or secret manager.
"""

from __future__ import annotations

import os

from cachine import RedisCache
from cachine.serializers import JSONSerializer
from cachine.utils import parse_redis_url


def example_parse_urls() -> None:
    """Demonstrate parsing different Redis URL formats."""

    configs = {
        "Single": parse_redis_url("redis://localhost:6379/0"),
        "SSL + auth": parse_redis_url("rediss://user:mypassword@localhost:6379/1?socket_timeout=5"),
        "Cluster": parse_redis_url("redis://node1:7000,node2:7001,node3:7002"),
        "Sentinel": parse_redis_url("redis+sentinel://mymaster/0?sentinels=sentinel1:26379,sentinel2:26379,sentinel3:26379"),
    }

    for title, config in configs.items():
        print(f"--- {title} ---")
        print(type(config).__name__, config)
        print()


def example_build_cache() -> None:
    """Build a RedisCache straight from a URL with namespace + serializer."""

    try:
        cache = RedisCache.from_url(
            "redis://localhost:6379/0",
            namespace="myapp",
            serializer=JSONSerializer(),
        )
    except RuntimeError as exc:
        print(f"Redis client unavailable: {exc}")
        return

    try:
        cache.set("test_key", {"message": "Hello from URL-created cache!"}, ttl=60)
        print("Retrieved:", cache.get("test_key"))
    except Exception as exc:  # connection errors, auth, etc.
        print(f"Could not talk to Redis ({type(exc).__name__}) — that's OK for this demo")
    finally:
        cache.close()


def example_env_based() -> None:
    """Read the URL from an environment variable."""

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    namespace = os.getenv("CACHE_NAMESPACE", "default")

    try:
        cache = RedisCache.from_url(redis_url, namespace=namespace, serializer=JSONSerializer())
    except RuntimeError as exc:
        print(f"Redis client unavailable: {exc}")
        return

    print(f"Created cache ({type(cache).__name__}) for {redis_url!r} namespace={namespace!r}")
    cache.close()


def main() -> None:
    example_parse_urls()
    example_build_cache()
    example_env_based()

    print("Supported URL formats:")
    print("  Single:    redis://[:password@]host:port[/db][?param=value]")
    print("  SSL:       rediss://[:password@]host:port[/db][?param=value]")
    print("  Cluster:   redis://host1:port1,host2:port2,host3:port3")
    print("  Sentinel:  redis+sentinel://service_name[/db]?sentinels=host1:port1,host2:port2")


if __name__ == "__main__":
    main()
