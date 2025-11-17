"""Redis configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RedisSingleConfig:
    """Configuration for a single Redis instance.

    Attributes:
        host: Redis server hostname or IP address
        port: Redis server port
        db: Database index (0-15 typically)
        password: Optional password for authentication
        username: Optional username for ACL authentication
        ssl: Whether to use SSL/TLS connection
        socket_timeout: Socket timeout in seconds
        socket_connect_timeout: Socket connect timeout in seconds
        retry_on_timeout: Whether to retry on timeout
        decode_responses: Whether to decode responses to strings
        extra: Additional configuration parameters

    Examples:
        >>> config = RedisSingleConfig(host="localhost", port=6379, db=0)
        >>> config.host
        'localhost'
        >>> config.port
        6379
    """

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    username: str | None = None
    ssl: bool = False
    socket_timeout: float | None = None
    socket_connect_timeout: float | None = None
    retry_on_timeout: bool = False
    decode_responses: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary format.

        Returns:
            Dictionary representation of the configuration

        Examples:
            >>> config = RedisSingleConfig(host="localhost", port=6379)
            >>> d = config.to_dict()
            >>> d["host"]
            'localhost'
        """
        result: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "ssl": self.ssl,
        }

        if self.password is not None:
            result["password"] = self.password

        if self.username is not None:
            result["username"] = self.username

        if self.socket_timeout is not None:
            result["socket_timeout"] = self.socket_timeout

        if self.socket_connect_timeout is not None:
            result["socket_connect_timeout"] = self.socket_connect_timeout

        if self.retry_on_timeout:
            result["retry_on_timeout"] = self.retry_on_timeout

        if self.decode_responses:
            result["decode_responses"] = self.decode_responses

        # Include extra parameters
        result.update(self.extra)

        return result


@dataclass(frozen=True)
class RedisNodeConfig:
    """Configuration for a single Redis cluster node.

    Attributes:
        host: Node hostname or IP address
        port: Node port

    Examples:
        >>> node = RedisNodeConfig(host="node1", port=7000)
        >>> node.host
        'node1'
    """

    host: str
    port: int = 6379

    def to_dict(self) -> dict[str, Any]:
        """Convert node config to dictionary.

        Returns:
            Dictionary with host and port

        Examples:
            >>> node = RedisNodeConfig(host="node1", port=7000)
            >>> node.to_dict()
            {'host': 'node1', 'port': 7000}
        """
        return {"host": self.host, "port": self.port}


@dataclass(frozen=True)
class RedisClusterConfig:
    """Configuration for Redis Cluster.

    Attributes:
        nodes: List of cluster node configurations
        password: Optional password for authentication
        username: Optional username for ACL authentication
        ssl: Whether to use SSL/TLS connection
        socket_timeout: Socket timeout in seconds
        socket_connect_timeout: Socket connect timeout in seconds
        retry_on_timeout: Whether to retry on timeout
        decode_responses: Whether to decode responses to strings
        extra: Additional configuration parameters

    Examples:
        >>> nodes = [RedisNodeConfig("node1", 7000), RedisNodeConfig("node2", 7001)]
        >>> config = RedisClusterConfig(nodes=nodes)
        >>> len(config.nodes)
        2
    """

    nodes: tuple[RedisNodeConfig, ...]
    password: str | None = None
    username: str | None = None
    ssl: bool = False
    socket_timeout: float | None = None
    socket_connect_timeout: float | None = None
    retry_on_timeout: bool = False
    decode_responses: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        nodes: list[RedisNodeConfig] | tuple[RedisNodeConfig, ...],
        password: str | None = None,
        username: str | None = None,
        ssl: bool = False,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
        retry_on_timeout: bool = False,
        decode_responses: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Initialize cluster configuration.

        Args:
            nodes: List or tuple of node configurations
            password: Optional password
            username: Optional username
            ssl: Whether to use SSL
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Socket connect timeout in seconds
            retry_on_timeout: Whether to retry on timeout
            decode_responses: Whether to decode responses to strings
            extra: Additional parameters
        """
        # Convert list to tuple for immutability
        object.__setattr__(self, "nodes", tuple(nodes))
        object.__setattr__(self, "password", password)
        object.__setattr__(self, "username", username)
        object.__setattr__(self, "ssl", ssl)
        object.__setattr__(self, "socket_timeout", socket_timeout)
        object.__setattr__(self, "socket_connect_timeout", socket_connect_timeout)
        object.__setattr__(self, "retry_on_timeout", retry_on_timeout)
        object.__setattr__(self, "decode_responses", decode_responses)
        object.__setattr__(self, "extra", extra or {})

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary format.

        Returns:
            Dictionary representation with nodes list

        Examples:
            >>> nodes = [RedisNodeConfig("node1", 7000)]
            >>> config = RedisClusterConfig(nodes=nodes)
            >>> d = config.to_dict()
            >>> d["nodes"][0]["host"]
            'node1'
        """
        result: dict[str, Any] = {
            "nodes": [node.to_dict() for node in self.nodes],
            "ssl": self.ssl,
        }

        if self.password is not None:
            result["password"] = self.password

        if self.username is not None:
            result["username"] = self.username

        if self.socket_timeout is not None:
            result["socket_timeout"] = self.socket_timeout

        if self.socket_connect_timeout is not None:
            result["socket_connect_timeout"] = self.socket_connect_timeout

        if self.retry_on_timeout:
            result["retry_on_timeout"] = self.retry_on_timeout

        if self.decode_responses:
            result["decode_responses"] = self.decode_responses

        # Include extra parameters
        result.update(self.extra)

        return result


@dataclass(frozen=True)
class RedisSentinelConfig:
    """Configuration for Redis Sentinel.

    Attributes:
        service_name: Sentinel service/master name
        sentinels: List of (host, port) tuples for sentinel nodes
        db: Database index
        password: Optional password for Redis authentication
        username: Optional username for ACL authentication
        ssl: Whether to use SSL/TLS connection
        socket_timeout: Socket timeout in seconds
        socket_connect_timeout: Socket connect timeout in seconds
        retry_on_timeout: Whether to retry on timeout
        decode_responses: Whether to decode responses to strings
        extra: Additional configuration parameters

    Examples:
        >>> sentinels = [("sentinel1", 26379), ("sentinel2", 26379)]
        >>> config = RedisSentinelConfig(service_name="mymaster", sentinels=sentinels)
        >>> config.service_name
        'mymaster'
        >>> len(config.sentinels)
        2
    """

    service_name: str
    sentinels: tuple[tuple[str, int], ...]
    db: int = 0
    password: str | None = None
    username: str | None = None
    ssl: bool = False
    socket_timeout: float | None = None
    socket_connect_timeout: float | None = None
    retry_on_timeout: bool = False
    decode_responses: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        service_name: str,
        sentinels: list[tuple[str, int]] | tuple[tuple[str, int], ...],
        db: int = 0,
        password: str | None = None,
        username: str | None = None,
        ssl: bool = False,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
        retry_on_timeout: bool = False,
        decode_responses: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Initialize sentinel configuration.

        Args:
            service_name: Sentinel service/master name
            sentinels: List or tuple of (host, port) tuples
            db: Database index
            password: Optional password
            username: Optional username
            ssl: Whether to use SSL
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Socket connect timeout in seconds
            retry_on_timeout: Whether to retry on timeout
            decode_responses: Whether to decode responses to strings
            extra: Additional parameters
        """
        object.__setattr__(self, "service_name", service_name)
        object.__setattr__(self, "sentinels", tuple(sentinels))
        object.__setattr__(self, "db", db)
        object.__setattr__(self, "password", password)
        object.__setattr__(self, "username", username)
        object.__setattr__(self, "ssl", ssl)
        object.__setattr__(self, "socket_timeout", socket_timeout)
        object.__setattr__(self, "socket_connect_timeout", socket_connect_timeout)
        object.__setattr__(self, "retry_on_timeout", retry_on_timeout)
        object.__setattr__(self, "decode_responses", decode_responses)
        object.__setattr__(self, "extra", extra or {})

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary format.

        Returns:
            Dictionary representation with sentinels list

        Examples:
            >>> sentinels = [("sentinel1", 26379)]
            >>> config = RedisSentinelConfig(service_name="mymaster", sentinels=sentinels)
            >>> d = config.to_dict()
            >>> d["service_name"]
            'mymaster'
        """
        result: dict[str, Any] = {
            "service_name": self.service_name,
            "sentinels": list(self.sentinels),
            "db": self.db,
            "ssl": self.ssl,
        }

        if self.password is not None:
            result["password"] = self.password

        if self.username is not None:
            result["username"] = self.username

        if self.socket_timeout is not None:
            result["socket_timeout"] = self.socket_timeout

        if self.socket_connect_timeout is not None:
            result["socket_connect_timeout"] = self.socket_connect_timeout

        if self.retry_on_timeout:
            result["retry_on_timeout"] = self.retry_on_timeout

        if self.decode_responses:
            result["decode_responses"] = self.decode_responses

        # Include extra parameters
        result.update(self.extra)

        return result


# Type alias for any Redis configuration
RedisConfig = RedisSingleConfig | RedisClusterConfig | RedisSentinelConfig


__all__ = [
    "RedisSingleConfig",
    "RedisNodeConfig",
    "RedisClusterConfig",
    "RedisSentinelConfig",
    "RedisConfig",
]
