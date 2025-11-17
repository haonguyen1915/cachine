"""Redis URL parsing utilities.

Supports parsing Redis connection URLs for:
- Single Redis instances
- Redis Cluster
- Redis Sentinel

URL Formats:
    Single: redis://[:password@]host:port[/db][?param=value]
    SSL: rediss://[:password@]host:port[/db][?param=value]
    Cluster: redis://host1:port1,host2:port2,host3:port3[?param=value]
    Sentinel: redis+sentinel://[:password@]service_name[/db]?sentinels=host1:port1,host2:port2

Examples:
    >>> parse_redis_url("redis://localhost:6379/0")
    {'type': 'single', 'host': 'localhost', 'port': 6379, 'db': 0, 'password': None, 'ssl': False}

    >>> parse_redis_url("redis://user:pass@localhost:6379/1?socket_timeout=5")
    {'type': 'single', 'host': 'localhost', 'port': 6379, 'db': 1, 'password': 'pass', 'ssl': False, 'socket_timeout': 5.0}

    >>> parse_redis_url("redis://node1:7000,node2:7001,node3:7002")
    {'type': 'cluster', 'nodes': [{'host': 'node1', 'port': 7000}, {'host': 'node2', 'port': 7001}, {'host': 'node3', 'port': 7002}], 'password': None, 'ssl': False}

    >>> parse_redis_url("redis+sentinel://mymaster/0?sentinels=host1:26379,host2:26379")
    {'type': 'sentinel', 'service_name': 'mymaster', 'sentinels': [('host1', 26379), ('host2', 26379)], 'db': 0, 'password': None, 'ssl': False}
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse


class RedisURLParseError(ValueError):
    """Raised when a Redis URL cannot be parsed."""


def parse_redis_url(url: str) -> dict[str, Any]:
    """Parse a Redis connection URL into configuration dict.

    Args:
        url: Redis connection URL string

    Returns:
        Dictionary with parsed configuration:
        - For single instance: {'type': 'single', 'host': ..., 'port': ..., 'db': ..., 'password': ..., 'ssl': ...}
        - For cluster: {'type': 'cluster', 'nodes': [...], 'password': ..., 'ssl': ...}
        - For sentinel: {'type': 'sentinel', 'service_name': ..., 'sentinels': [...], 'db': ..., 'password': ..., 'ssl': ...}

    Raises:
        RedisURLParseError: If URL format is invalid

    Examples:
        >>> config = parse_redis_url("redis://localhost:6379/0")
        >>> config['type']
        'single'
        >>> config['host']
        'localhost'
        >>> config['port']
        6379
    """
    if not url:
        raise RedisURLParseError("URL cannot be empty")

    parsed = urlparse(url)

    # Determine connection type and SSL
    scheme = parsed.scheme.lower()
    if scheme == "redis":
        ssl = False
    elif scheme == "rediss":
        ssl = True
    elif scheme == "redis+sentinel":
        return _parse_sentinel_url(parsed, ssl=False)
    elif scheme == "rediss+sentinel":
        return _parse_sentinel_url(parsed, ssl=True)
    else:
        raise RedisURLParseError(f"Unsupported scheme: {scheme}. Use 'redis', 'rediss', 'redis+sentinel', or 'rediss+sentinel'")

    # Parse query parameters
    query_params = parse_qs(parsed.query) if parsed.query else {}
    extra_params = _parse_query_params(query_params)

    # Parse username and password
    username = parsed.username
    password = parsed.password

    # Check if this is a cluster URL (multiple host:port pairs)
    if "," in parsed.netloc:
        return _parse_cluster_url(parsed, ssl, username, password, extra_params)

    # Single instance
    return _parse_single_url(parsed, ssl, username, password, extra_params)


def _parse_single_url(
    parsed: Any,
    ssl: bool,
    username: str | None,
    password: str | None,
    extra_params: dict[str, Any],
) -> dict[str, Any]:
    """Parse single Redis instance URL."""
    # Extract host and port
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379

    # Extract database number from path
    db = 0
    if parsed.path and parsed.path != "/":
        path = parsed.path.lstrip("/")
        if path:
            try:
                db = int(path)
            except ValueError as e:
                raise RedisURLParseError(f"Invalid database number: {path}") from e

    config: dict[str, Any] = {
        "type": "single",
        "host": host,
        "port": port,
        "db": db,
        "password": password,
        "ssl": ssl,
    }

    # Add username if provided (for ACL)
    if username:
        config["username"] = username

    # Merge extra parameters
    config.update(extra_params)

    return config


def _parse_cluster_url(
    parsed: Any,
    ssl: bool,
    username: str | None,
    password: str | None,
    extra_params: dict[str, Any],
) -> dict[str, Any]:
    """Parse Redis Cluster URL with multiple nodes."""
    # Parse nodes from netloc
    # Format: [user:password@]host1:port1,host2:port2,host3:port3
    netloc = parsed.netloc

    # Remove credentials if present
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]

    # Parse each node
    nodes = []
    for node_str in netloc.split(","):
        node_str = node_str.strip()
        if not node_str:
            continue

        # Parse host:port
        if ":" in node_str:
            node_host, port_str = node_str.rsplit(":", 1)
            try:
                node_port = int(port_str)
            except ValueError as e:
                raise RedisURLParseError(f"Invalid port in node: {node_str}") from e
        else:
            node_host = node_str
            node_port = 6379

        nodes.append({"host": node_host, "port": node_port})

    if not nodes:
        raise RedisURLParseError("No nodes found in cluster URL")

    config: dict[str, Any] = {
        "type": "cluster",
        "nodes": nodes,
        "password": password,
        "ssl": ssl,
    }

    # Add username if provided (for ACL)
    if username:
        config["username"] = username

    # Merge extra parameters
    config.update(extra_params)

    return config


def _parse_sentinel_url(parsed: Any, ssl: bool) -> dict[str, Any]:
    """Parse Redis Sentinel URL."""
    # Format: redis+sentinel://[:password@]service_name[/db]?sentinels=host1:port1,host2:port2

    # Service name is the hostname
    service_name = parsed.hostname
    if not service_name:
        raise RedisURLParseError("Service name (master name) is required for Sentinel URL")

    # Parse password
    password = parsed.password
    username = parsed.username

    # Parse database number
    db = 0
    if parsed.path and parsed.path != "/":
        path = parsed.path.lstrip("/")
        if path:
            try:
                db = int(path)
            except ValueError as e:
                raise RedisURLParseError(f"Invalid database number: {path}") from e

    # Parse sentinels from query string
    query_params = parse_qs(parsed.query) if parsed.query else {}

    if "sentinels" not in query_params:
        raise RedisURLParseError("Sentinel URL must include 'sentinels' query parameter")

    sentinels_str = query_params["sentinels"][0]
    sentinels = []

    for sentinel_str in sentinels_str.split(","):
        sentinel_str = sentinel_str.strip()
        if not sentinel_str:
            continue

        if ":" in sentinel_str:
            sentinel_host, port_str = sentinel_str.rsplit(":", 1)
            try:
                sentinel_port = int(port_str)
            except ValueError as e:
                raise RedisURLParseError(f"Invalid port in sentinel: {sentinel_str}") from e
        else:
            sentinel_host = sentinel_str
            sentinel_port = 26379  # Default Sentinel port

        sentinels.append((sentinel_host, sentinel_port))

    if not sentinels:
        raise RedisURLParseError("No sentinels found in Sentinel URL")

    # Parse extra parameters (excluding sentinels)
    extra_query_params = {k: v for k, v in query_params.items() if k != "sentinels"}
    extra_params = _parse_query_params(extra_query_params)

    config: dict[str, Any] = {
        "type": "sentinel",
        "service_name": service_name,
        "sentinels": sentinels,
        "db": db,
        "password": password,
        "ssl": ssl,
    }

    # Add username if provided
    if username:
        config["username"] = username

    # Merge extra parameters
    config.update(extra_params)

    return config


def _parse_query_params(query_params: dict[str, list[str]]) -> dict[str, Any]:
    """Parse query parameters into typed values."""
    extra: dict[str, Any] = {}

    # Known numeric parameters
    numeric_params = {
        "socket_timeout",
        "socket_connect_timeout",
        "socket_keepalive",
        "connection_pool_max_connections",
        "retry_on_timeout",
        "max_connections",
        "health_check_interval",
    }

    # Known boolean parameters
    boolean_params = {
        "retry_on_timeout",
        "decode_responses",
    }

    for key, values in query_params.items():
        if not values:
            continue

        value = values[0]  # Take first value

        # Convert to appropriate type
        if key in boolean_params:
            extra[key] = value.lower() in ("true", "1", "yes", "on")
        elif key in numeric_params:
            try:
                # Try float first (supports both int and float)
                extra[key] = float(value) if "." in value else int(value)
            except ValueError:
                extra[key] = value
        else:
            extra[key] = value

    return extra


def create_cache_from_url(url: str, **kwargs: Any) -> Any:
    """Create a cache instance from a Redis URL.

    Args:
        url: Redis connection URL
        **kwargs: Additional arguments to pass to the cache constructor
                 (e.g., namespace, serializer)

    Returns:
        Cache instance (RedisCache, RedisClusterCache, or RedisSentinelCache)

    Raises:
        RedisURLParseError: If URL format is invalid

    Examples:
        >>> from cachine.serializers import JSONSerializer
        >>> cache = create_cache_from_url(
        ...     "redis://localhost:6379/0",
        ...     namespace="myapp",
        ...     serializer=JSONSerializer()
        ... )
    """
    config = parse_redis_url(url)
    config_type = config.pop("type")

    # Merge with kwargs (kwargs take precedence)
    config.update(kwargs)

    if config_type == "single":
        from ..backends.redis.sync import RedisCache
        return RedisCache(**config)

    if config_type == "cluster":
        from ..backends.redis.cluster import RedisClusterCache
        return RedisClusterCache(**config)

    if config_type == "sentinel":
        from ..backends.redis.sentinel import RedisSentinelCache
        return RedisSentinelCache(**config)

    raise RedisURLParseError(f"Unknown connection type: {config_type}")


__all__ = [
    "parse_redis_url",
    "create_cache_from_url",
    "RedisURLParseError",
]