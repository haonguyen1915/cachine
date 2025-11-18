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
    >>> config = parse_redis_url("redis://localhost:6379/0")
    >>> config.host
    'localhost'
    >>> config.port
    6379

    >>> config = parse_redis_url("redis://node1:7000,node2:7001,node3:7002")
    >>> len(config.nodes)
    3

    >>> config = parse_redis_url("redis+sentinel://mymaster/0?sentinels=host1:26379,host2:26379")
    >>> config.service_name
    'mymaster'
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from ..exceptions import RedisURLParseError
from ..models.redis_config import (
    RedisClusterConfig,
    RedisConfig,
    RedisNodeConfig,
    RedisSentinelConfig,
    RedisSingleConfig,
)


def parse_redis_url(url: str) -> RedisConfig:
    """Parse a Redis connection URL into configuration object.

    Args:
        url: Redis connection URL string

    Returns:
        RedisConfig object (RedisSingleConfig, RedisClusterConfig, or RedisSentinelConfig):
        - For single instance: RedisSingleConfig with host, port, db, password, ssl, etc.
        - For cluster: RedisClusterConfig with nodes, password, ssl, etc.
        - For sentinel: RedisSentinelConfig with service_name, sentinels, db, password, ssl, etc.

    Raises:
        RedisURLParseError: If URL format is invalid

    Examples:
        >>> config = parse_redis_url("redis://localhost:6379/0")
        >>> isinstance(config, RedisSingleConfig)
        True
        >>> config.host
        'localhost'
        >>> config.port
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
) -> RedisSingleConfig:
    """Parse single Redis instance URL.

    Returns:
        RedisSingleConfig object with parsed configuration
    """
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

    # Extract known timeout and config parameters from extra_params
    socket_timeout = extra_params.pop("socket_timeout", None)
    socket_connect_timeout = extra_params.pop("socket_connect_timeout", None)
    retry_on_timeout = extra_params.pop("retry_on_timeout", False)
    decode_responses = extra_params.pop("decode_responses", False)

    # Remaining params go into extra
    return RedisSingleConfig(
        host=host,
        port=port,
        db=db,
        password=password,
        username=username,
        ssl=ssl,
        socket_timeout=socket_timeout,
        socket_connect_timeout=socket_connect_timeout,
        retry_on_timeout=retry_on_timeout,
        decode_responses=decode_responses,
        extra=extra_params,
    )


def _parse_cluster_url(
    parsed: Any,
    ssl: bool,
    username: str | None,
    password: str | None,
    extra_params: dict[str, Any],
) -> RedisClusterConfig:
    """Parse Redis Cluster URL with multiple nodes.

    Returns:
        RedisClusterConfig object with parsed configuration
    """
    # Parse nodes from netloc
    # Format: [user:password@]host1:port1,host2:port2,host3:port3
    netloc = parsed.netloc

    # Remove credentials if present
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]

    # Parse each node
    nodes: list[RedisNodeConfig] = []
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

        nodes.append(RedisNodeConfig(host=node_host, port=node_port))

    if not nodes:
        raise RedisURLParseError("No nodes found in cluster URL")

    # Extract known timeout and config parameters from extra_params
    socket_timeout = extra_params.pop("socket_timeout", None)
    socket_connect_timeout = extra_params.pop("socket_connect_timeout", None)
    retry_on_timeout = extra_params.pop("retry_on_timeout", False)
    decode_responses = extra_params.pop("decode_responses", False)

    # Remaining params go into extra
    return RedisClusterConfig(
        nodes=nodes,
        password=password,
        username=username,
        ssl=ssl,
        socket_timeout=socket_timeout,
        socket_connect_timeout=socket_connect_timeout,
        retry_on_timeout=retry_on_timeout,
        decode_responses=decode_responses,
        extra=extra_params,
    )


def _parse_sentinel_url(parsed: Any, ssl: bool) -> RedisSentinelConfig:
    """Parse Redis Sentinel URL.

    Returns:
        RedisSentinelConfig object with parsed configuration
    """
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
    sentinels: list[tuple[str, int]] = []

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

    # Extract known timeout and config parameters from extra_params
    socket_timeout = extra_params.pop("socket_timeout", None)
    socket_connect_timeout = extra_params.pop("socket_connect_timeout", None)
    retry_on_timeout = extra_params.pop("retry_on_timeout", False)
    decode_responses = extra_params.pop("decode_responses", False)

    # Remaining params go into extra
    return RedisSentinelConfig(
        service_name=service_name,
        sentinels=sentinels,
        db=db,
        password=password,
        username=username,
        ssl=ssl,
        socket_timeout=socket_timeout,
        socket_connect_timeout=socket_connect_timeout,
        retry_on_timeout=retry_on_timeout,
        decode_responses=decode_responses,
        extra=extra_params,
    )


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
        **kwargs: Additional arguments (namespace, serializer) to pass to the cache constructor

    Returns:
        Cache instance (RedisCache with appropriate configuration)

    Raises:
        RedisURLParseError: If URL format is invalid

    Examples:
        >>> from cachine.serializers import JSONSerializer
        >>> cache = create_cache_from_url("redis://localhost:6379/0", namespace="myapp", serializer=JSONSerializer())
    """
    config = parse_redis_url(url)

    # Merge namespace and serializer from kwargs
    namespace = kwargs.pop("namespace", None)
    serializer = kwargs.pop("serializer", None)

    # Any remaining kwargs are warnings/errors
    if kwargs:
        import warnings

        warnings.warn(f"Unknown arguments ignored: {list(kwargs.keys())}", stacklevel=2)

    from ..backends.redis.sync import RedisCache

    return RedisCache(config, namespace=namespace, serializer=serializer)


__all__ = [
    "parse_redis_url",
    "create_cache_from_url",
    "RedisURLParseError",
]
