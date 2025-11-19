from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Optional, cast

from cachine.core.types import HealthStatus
from cachine.models.redis_config import RedisClusterConfig, RedisConfig, RedisSentinelConfig, RedisSingleConfig
from cachine.utils.helpers import to_seconds

_MISSING = object()


class RedisCache:
    """Synchronous Redis-backed cache.

    Provides get/set, TTL management, counters, and tag invalidation using a
    Redis client. A default serializer can be configured for values.

    Args:
        config (RedisConfig): Redis configuration object (RedisSingleConfig, RedisClusterConfig, or RedisSentinelConfig).
        namespace (str | None): Optional key namespace prefix, e.g. ``"app:"``.
        serializer (Any | None): Default serializer for values supporting ``dumps``/``loads``.
        pubsub_channel (str | None): Pub/Sub channel for tag invalidation events. Defaults to "cachine:invalidate".
        auto_publish_invalidations (bool): Automatically publish tag invalidation events. Defaults to False.

    Examples:
        >>> from cachine.models.redis_config import RedisSingleConfig
        >>> config = RedisSingleConfig(host="localhost", port=6379, db=0)
        >>> cache = RedisCache(config, namespace="myapp")
        >>> cache.set("key", "value", ttl=60)
        >>> cache.get("key")
        'value'
    """

    def __init__(
        self,
        config: RedisConfig,
        *,
        namespace: Optional[str] = None,
        serializer: Optional[Any] = None,
        pubsub_channel: Optional[str] = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> None:
        # Client attribute (runtime redis client)
        self._client: Any
        # Create appropriate client based on config type
        if isinstance(config, RedisSingleConfig):
            self._client = self._create_single_client(config)
        elif isinstance(config, RedisClusterConfig):
            self._client = self._create_cluster_client(config)
        elif isinstance(config, RedisSentinelConfig):
            self._client = self._create_sentinel_client(config)
        else:
            raise TypeError(f"Unsupported config type: {type(config)}")

        self._config = config
        self._ns = f"{namespace}:" if namespace else ""
        self._serializer = serializer
        self._pubsub_channel = pubsub_channel
        self._auto_publish_invalidations = auto_publish_invalidations

    # Basic ops (stubs)
    def get(self, key: str, default: Any = None, serializer: Any = None) -> Any:
        """Get a value by key.

        Args:
            key (str): Cache key.
            default (Any, optional): Value to return when key is missing.
            serializer (Any, optional): Serializer to decode bytes; defaults to
                the instance serializer.

        Returns:
            Any: Decoded value from Redis or ``default`` if missing.
        """
        k = self._ns + key
        client = self._require_client()
        raw = client.get(k)
        if raw is None:
            return default
        ser = serializer or self._serializer
        if ser is not None:
            try:
                return ser.loads(raw)
            except Exception:
                # Fall back to raw if serializer fails
                return raw
        return raw

    def set(self, key: str, value: Any, ttl: Optional[int | timedelta] = None, serializer: Any = None) -> None:
        """Set a value by key.

        Args:
            key (str): Cache key.
            value (Any): Value to store.
            ttl (int | timedelta | None): Optional time-to-live.
            serializer (Any, optional): Serializer to encode value; defaults to instance serializer.

        Returns:
            None
        """
        k = self._ns + key
        client = self._require_client()
        ser = serializer or self._serializer
        payload = ser.dumps(value) if ser is not None else value
        seconds = to_seconds(ttl)
        if seconds is not None:
            client.set(k, payload, ex=seconds)
        else:
            client.set(k, payload)

    def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if the key existed and was removed.
        """
        k = self._ns + key
        client = self._require_client()
        try:
            res = client.delete(k)
            # redis-py returns int count of removed keys
            return bool(res)
        except AttributeError:
            # Some clients may use del
            before = client.get(k) is not None
            client.set(k, None)
            return before

    def exists(self, key: str) -> bool:
        """Check key existence.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if the key exists.
        """
        k = self._ns + key
        client = self._require_client()
        res = client.exists(k)
        if isinstance(res, bool):
            return res
        try:
            return bool(int(res))
        except Exception:
            return bool(res)

    def clear(self, dangerously_clear_all: bool = False) -> None:
        """Clear keys in the current namespace or flush the DB.

        Args:
            dangerously_clear_all (bool): When True, flushes the entire database.
                When False, requires a configured namespace and removes only keys
                in that namespace using SCAN/DEL.

        Returns:
            None
        """
        client = self._require_client()
        if dangerously_clear_all:
            try:
                client.flushdb()
            except Exception:
                pass
            return
        if not self._ns:
            raise RuntimeError("clear() requires a namespace or set dangerously_clear_all=True")
        # Delete keys with this namespace prefix
        pattern = f"{self._ns}*"
        try:
            keys = list(client.scan_iter(match=pattern))
        except Exception:
            keys = []
        # client may return bytes
        norm_keys = [k.decode("utf-8") if isinstance(k, bytes | bytearray) else k for k in keys]
        if norm_keys:
            try:
                # Prefer bulk delete when available; fall back to one-by-one
                del_many = getattr(client, "delete_many", None)
                if del_many is not None:
                    del_many(*norm_keys)
                else:
                    client.delete(*norm_keys)
            except Exception:
                for k in norm_keys:
                    try:
                        client.delete(k)
                    except Exception:
                        pass

    # Enrichment
    def get_or_set(self, key: str, factory: Any, ttl: Optional[int | timedelta] = None, jitter: Optional[int] = None) -> Any:  # pylint: disable=unused-argument
        """Get or compute-and-set a value.

        Args:
            key (str): Cache key.
            factory (Any): Callable or value used to compute the value when missing.
            ttl (int | timedelta | None): Optional TTL for the stored value.
            jitter (int | None): Ignored by this implementation.

        Returns:
            Any: Existing value if present; otherwise the computed value.

        Note:
            This implementation is non-atomic and may compute twice under races.
            For strict single-flight behavior consider using the decorator-based API.
        """
        sentinel = _MISSING
        val = self.get(key, default=sentinel)
        if val is not sentinel:
            return val
        computed = factory() if callable(factory) else factory
        self.set(key, computed, ttl=ttl)
        return computed

    # TTL management
    def expire(self, key: str, ttl: int | timedelta) -> bool:
        """Set a relative expiration.

        Args:
            key (str): Cache key.
            ttl (int | timedelta): Relative TTL.

        Returns:
            bool: True if the key existed and TTL was set.
        """
        k = self._ns + key
        client = self._require_client()
        seconds = to_seconds(ttl)
        if seconds is None:
            return False
        res = client.expire(k, seconds)
        return bool(res)

    def expire_at(self, key: str, when: datetime) -> bool:
        """Set an absolute expiration.

        Args:
            key (str): Cache key.
            when (datetime): Absolute UTC expiration time.

        Returns:
            bool: True if the key existed and expiration was set.
        """
        k = self._ns + key
        client = self._require_client()
        # redis-py accepts unix time seconds for expireat
        ts = int(when.timestamp())
        res = client.expireat(k, ts)
        return bool(res)

    def touch(self, key: str, ttl: Optional[int | timedelta] = None) -> bool:
        """Refresh presence or set a new TTL.

        Args:
            key (str): Cache key.
            ttl (int | timedelta | None): Optional TTL to set. When None, attempts
                a Redis TOUCH or falls back to existence check.

        Returns:
            bool: True if key exists (and TTL was updated when provided).
        """
        # Redis TOUCH does not change TTL; emulate by setting expire when ttl is provided.
        if ttl is None:
            # If client supports TOUCH, use it; else return exists
            client = self._require_client()
            try:
                res = client.touch(self._ns + key)
                return bool(res)
            except AttributeError:
                return self.exists(key)
        else:
            return self.expire(key, ttl=ttl)

    def ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL.

        Args:
            key (str): Cache key.

        Returns:
            int | None: Remaining seconds; None if no TTL or missing.
        """
        k = self._ns + key
        client = self._require_client()
        res = client.ttl(k)
        try:
            val = int(res)
        except Exception:
            return None
        if val < 0:
            # -2 key does not exist, -1 no expiry
            return None
        return val

    def persist(self, key: str) -> bool:
        """Remove expiration from a key.

        Args:
            key (str): Cache key.

        Returns:
            bool: True if a TTL existed and was removed.
        """
        k = self._ns + key
        client = self._require_client()
        try:
            res = client.persist(k)
            return bool(res)
        except AttributeError:
            # Fallback: emulate via TTL check
            ttl = client.ttl(k)
            if ttl is None or (isinstance(ttl, int) and ttl < 0):
                return False
            # Try to remove expiry via PERSIST equivalent
            try:
                client.pexpire(k, 0)  # not correct; placeholder if no persist
            except Exception:
                pass
            return True

    # Counters
    def incr(self, key: str, delta: int = 1, ttl_on_create: Optional[int | timedelta] = None) -> int:
        """Increment an integer value by ``delta``.

        Args:
            key (str): Cache key.
            delta (int): Increment amount.
            ttl_on_create (int | timedelta | None): TTL set only when the key is first created.

        Returns:
            int: The new integer value.
        """
        k = self._ns + key
        client = self._require_client()
        if ttl_on_create is None:
            return int(client.incrby(k, int(delta)))

        # Use Lua for atomic set-ttl-on-create behavior
        pexpire_ms = to_seconds(ttl_on_create)
        ms = 0 if pexpire_ms is None else int(pexpire_ms * 1000)
        script = (
            "local exists = redis.call('EXISTS', KEYS[1])\n"
            "local val = redis.call('INCRBY', KEYS[1], ARGV[1])\n"
            "if exists == 0 and tonumber(ARGV[2]) and tonumber(ARGV[2]) > 0 then\n"
            "  redis.call('PEXPIRE', KEYS[1], ARGV[2])\n"
            "end\n"
            "return val\n"
        )
        try:
            return int(client.eval(script, 1, k, int(delta), ms))
        except AttributeError:
            # Fallback non-atomic path for limited clients
            existed = bool(client.exists(k))
            val = int(client.incrby(k, int(delta)))
            if not existed and ms > 0:
                try:
                    client.pexpire(k, ms)
                except Exception:
                    # try seconds if pexpire not available
                    client.expire(k, max(ms // 1000, 1))
            return val

    def decr(self, key: str, delta: int = 1) -> int:
        """Decrement an integer value.

        Args:
            key (str): Cache key.
            delta (int): Decrement amount.

        Returns:
            int: The new integer value.
        """
        return self.incr(key, delta=-int(delta))

    # Tags
    def invalidate_tags(self, tags: list[str], publish: Optional[bool] = None) -> int:
        """Invalidate keys by tags.

        Args:
            tags (list[str]): Tags to invalidate.
            publish (bool | None): Whether to publish invalidation event. If None, uses auto_publish_invalidations setting.

        Returns:
            int: Number of unique keys deleted across all tags.
        """
        client = self._require_client()
        deleted_keys: set[str] = set()
        for tag in tags:
            tkey = f"{self._ns}tag::{tag}"
            try:
                members = client.smembers(tkey)
            except Exception:
                members = set()
            for mk in list(members):
                # mk may be bytes
                key_name = mk.decode("utf-8") if isinstance(mk, bytes | bytearray) else mk
                try:
                    client.delete(key_name)
                except Exception:
                    pass
                deleted_keys.add(key_name)
            try:
                client.delete(tkey)
            except Exception:
                pass

        # Publish invalidation event if enabled
        should_publish = publish if publish is not None else self._auto_publish_invalidations
        if should_publish and self._pubsub_channel:
            self.publish_invalidation(tags)

        return len(deleted_keys)

    # Health / lifecycle
    def ping(self) -> HealthStatus:
        """Check health.

        Returns:
            dict[str, Any]: Health payload with ``healthy``, ``latency_ms``, and ``backend``.
        """
        return {"healthy": True, "latency_ms": 0.0, "backend": "redis"}

    def ping_ok(self) -> bool:
        """Return a boolean health indicator.

        Returns:
            bool: True if the cache is considered healthy.
        """
        s = self.ping()
        return bool(s.get("healthy", False))

    def close(self) -> None:
        """Close the underlying client if applicable."""
        return None

    def get_stats(self) -> Optional[dict[str, Any]]:
        """Get cache statistics.

        Returns:
            Optional[dict[str, Any]]: None for base cache (no stats collected).
                Middleware may override to return collected metrics.
        """
        return None

    # Context manager
    def __enter__(self) -> RedisCache:
        """Enter context manager.

        Returns:
            RedisCache: This cache instance.
        """
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit context manager; no explicit cleanup required."""
        return None

    # Internal helpers
    def _require_client(self) -> Any:
        """Return the Redis client wrapper.

        Returns:
            SyncRedisClientProto: A client implementing the subset of redis-py used here.
        """
        return self._client

    @staticmethod
    def _create_single_client(config: RedisSingleConfig) -> Any:
        """Create client for single Redis instance.

        Args:
            config (RedisSingleConfig): Single instance configuration.

        Returns:
            Any: RedisClient wrapper instance.
        """
        try:
            from redis import Redis
        except Exception as e:
            raise RuntimeError("redis cluster client not available; install redis>=4 with cluster support") from e

        # Build kwargs from config, keeping bytes-oriented responses by default
        kwargs: dict[str, Any] = {
            "host": config.host,
            "port": int(config.port),
            "db": int(config.db),
            "ssl": bool(config.ssl),
            "decode_responses": bool(config.decode_responses),
        }
        if config.username is not None:
            kwargs["username"] = config.username
        if config.password is not None:
            kwargs["password"] = config.password
        if config.socket_timeout is not None:
            kwargs["socket_timeout"] = float(config.socket_timeout)
        if config.socket_connect_timeout is not None:
            kwargs["socket_connect_timeout"] = float(config.socket_connect_timeout)

        # Allow passing through any additional supported parameters
        for k, v in config.extra.items():
            kwargs.setdefault(k, v)

        return Redis(**kwargs)

    @staticmethod
    def _create_cluster_client(config: RedisClusterConfig) -> Any:
        """Create client for Redis Cluster.

        Args:
            config (RedisClusterConfig): Cluster configuration.

        Returns:
            SyncRedisClientProto: RedisCluster-compatible client instance.

        Raises:
            RuntimeError: If redis cluster client is not available.
        """
        try:
            from redis import RedisCluster
            from redis.cluster import ClusterNode
        except Exception as e:
            raise RuntimeError("redis cluster client not available; install redis>=4 with cluster support") from e

        # Convert nodes to dict format for redis-py
        nodes = [{"host": node.host, "port": node.port} for node in config.nodes]

        # Try different redis-py API versions

        cluster_nodes = [ClusterNode(n["host"], n["port"]) for n in nodes]
        kwargs: dict[str, Any] = {
            "username": config.username,
            "password": config.password,
            "ssl": config.ssl,
        }
        # Optional timeouts/flags
        if getattr(config, "decode_responses", False):
            kwargs["decode_responses"] = True
        if getattr(config, "socket_timeout", None) is not None:
            kwargs["socket_timeout"] = float(config.socket_timeout)  # type: ignore[arg-type]
        if getattr(config, "socket_connect_timeout", None) is not None:
            kwargs["socket_connect_timeout"] = float(config.socket_connect_timeout)  # type: ignore[arg-type]
        if getattr(config, "retry_on_timeout", False):
            kwargs["retry_on_timeout"] = True

        # Avoid deprecated retry_on_timeout on redis>=6
        try:  # pragma: no cover
            import redis as _redis

            ver = getattr(_redis, "__version__", "")
            head = ver.split(".", maxsplit=1)[0] if ver else ""
            major = int(head) if head.isdigit() else None
            if major is not None and major >= 6:
                kwargs.pop("retry_on_timeout", None)
        except Exception:
            pass

        return RedisCluster(startup_nodes=cluster_nodes, **kwargs)

    @staticmethod
    def _create_sentinel_client(config: RedisSentinelConfig) -> Any:
        """Create client for Redis Sentinel.

        Args:
            config (RedisSentinelConfig): Sentinel configuration.

        Returns:
            SyncRedisClientProto: Redis master client from Sentinel.

        Raises:
            RuntimeError: If redis.sentinel is not available.
        """
        try:
            from redis.sentinel import Sentinel
        except Exception as e:
            raise RuntimeError("redis.sentinel is not available; install redis>=4") from e

        # Use configured socket_timeout when provided
        st = 2 if config.socket_timeout is None else float(config.socket_timeout)
        sentinel = Sentinel(list(config.sentinels), socket_timeout=st, ssl=config.ssl)
        return cast(
            Any,
            sentinel.master_for(
                config.service_name,
                db=config.db,
                password=config.password,
                ssl=config.ssl,
            ),
        )

    # Tag helpers
    def add_tags(self, key: str, tags: list[str], ttl: Optional[int | timedelta] = None) -> None:
        """Associate tags with a key.

        Args:
            key (str): Cache key (without namespace).
            tags (list[str]): Tags to associate.
            ttl (int | timedelta | None): Optional TTL for tag associations.
                If provided, tag sets will expire after this duration.

        Returns:
            None
        """
        client = self._require_client()
        k = self._ns + key
        ttl_seconds = to_seconds(ttl) if ttl is not None else None

        for tag in tags:
            tkey = f"{self._ns}tag::{tag}"
            try:
                client.sadd(tkey, k)
                # Set TTL on tag set if provided
                if ttl_seconds is not None and ttl_seconds > 0:
                    client.expire(tkey, int(ttl_seconds))
            except Exception:
                pass

    # Pub/Sub
    def publish_invalidation(self, tags: list[str]) -> None:
        """Publish a tag invalidation event to the Pub/Sub channel.

        Args:
            tags (list[str]): Tags to include in the invalidation event.

        Returns:
            None

        Examples:
            >>> cache.publish_invalidation(["user:123", "product:456"])
        """
        if not self._pubsub_channel:
            return

        payload = {
            "type": "invalidate_tags",
            "namespace": self._ns.rstrip(":") if self._ns else None,
            "tags": list(tags),
        }
        try:
            data = json.dumps(payload)
            client = self._require_client()
            client.publish(self._pubsub_channel, data)
        except Exception:
            pass

    def subscribe_invalidations(
        self,
        handler: Callable[[dict[str, Any]], None],
        *,
        channel: Optional[str] = None,
    ) -> None:
        """Subscribe to tag invalidation events and process them with a handler.

        This is a blocking operation that listens for invalidation events on the
        Pub/Sub channel and invokes the handler for each valid event.

        Args:
            handler (Callable[[dict[str, Any]], None]): Function called with each event.
                Receives event dict with keys: type, namespace, tags.
            channel (str | None): Override the Pub/Sub channel. Uses instance channel if None.

        Returns:
            None

        Examples:
            >>> def handle_event(event):
            ...     tags = event.get("tags", [])
            ...     print(f"Invalidating tags: {tags}")
            >>> cache.subscribe_invalidations(handle_event)
        """
        target_channel = channel or self._pubsub_channel
        if not target_channel:
            return

        try:
            client = self._require_client()
            pubsub: Any = client.pubsub()
            pubsub.subscribe(target_channel)
            for msg in pubsub.listen():
                if not msg or msg.get("type") != "message":
                    continue
                try:
                    event = json.loads(msg.get("data"))
                except Exception:
                    continue
                handler(event)
        except Exception:
            pass
