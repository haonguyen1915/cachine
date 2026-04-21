from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, cast, overload

from cachine.core.types import HealthStatus
from cachine.exceptions import RedisURLParseError
from cachine.models.redis_config import (
    RedisClusterConfig,
    RedisConfig,
    RedisSentinelConfig,
    RedisSingleConfig,
)
from cachine.utils._deprecations import (
    MISSING,
    resolve_renamed_kwarg,
    warn_deprecated_kwarg,
    warn_deprecated_method,
)
from cachine.utils.helpers import to_seconds

_MISSING = object()


class RedisCache:
    """Synchronous Redis-backed cache.

    Provides get/set, TTL management, counters, and tag invalidation using a
    Redis client. A default serializer can be configured for values.

    Construction supports two forms:
      - Kwargs shortcut (recommended for single instance)::

            RedisCache(host="localhost", port=6379, namespace="app")

      - Explicit config (Cluster/Sentinel or advanced tuning)::

            RedisCache(RedisClusterConfig(nodes=[...]), namespace="app")

    Args:
        config: Redis configuration object (``RedisSingleConfig``,
            ``RedisClusterConfig``, or ``RedisSentinelConfig``). Omit when
            using the kwargs shortcut.
        namespace: Optional key namespace prefix, e.g. ``"app"``.
        serializer: Default serializer for values supporting ``dumps``/``loads``.
        pubsub_channel: Pub/Sub channel for tag invalidation events.
            Defaults to ``"cachine:invalidate"``.
        auto_publish_invalidations: Automatically publish invalidation events.
    """

    @overload
    def __init__(
        self,
        config: RedisConfig,
        *,
        namespace: str | None = None,
        serializer: Any | None = None,
        pubsub_channel: str | None = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> None: ...

    @overload
    def __init__(
        self,
        *,
        host: str,
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        username: str | None = None,
        ssl: bool = False,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
        retry_on_timeout: bool = False,
        decode_responses: bool = False,
        namespace: str | None = None,
        serializer: Any | None = None,
        pubsub_channel: str | None = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> None: ...

    def __init__(
        self,
        config: RedisConfig | None = None,
        *,
        host: str | None = None,
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        username: str | None = None,
        ssl: bool = False,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
        retry_on_timeout: bool = False,
        decode_responses: bool = False,
        namespace: str | None = None,
        serializer: Any | None = None,
        pubsub_channel: str | None = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> None:
        if config is not None and host is not None:
            raise TypeError("RedisCache: pass either `config` or `host=...` kwargs, not both")
        if config is None:
            if host is None:
                host = "localhost"
            config = RedisSingleConfig(
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
            )

        self._client: Any
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

    # ---- URL constructor ----
    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        namespace: str | None = None,
        serializer: Any | None = None,
        pubsub_channel: str | None = "cachine:invalidate",
        auto_publish_invalidations: bool = False,
    ) -> RedisCache:
        """Construct a :class:`RedisCache` from a Redis connection URL.

        Supported schemes: ``redis://``, ``rediss://``,
        ``redis+sentinel://``, ``rediss+sentinel://``. Pass multiple
        host/port pairs separated by commas to create a cluster client.
        """
        from cachine.utils.redis_url import parse_redis_url

        scheme = url.split("://", 1)[0].lower() if "://" in url else ""
        if scheme and not scheme.startswith("redis"):
            raise RedisURLParseError(
                f"RedisCache.from_url received non-Redis URL ({scheme!r}); use SQLiteCache.from_url for sqlite:// URLs"
            )
        config = parse_redis_url(url)
        return cls(
            config,
            namespace=namespace,
            serializer=serializer,
            pubsub_channel=pubsub_channel,
            auto_publish_invalidations=auto_publish_invalidations,
        )

    # ---- Basic ops ----
    def get(self, key: str, default: Any = None, *, serializer: Any = MISSING) -> Any:
        """Get a value by key."""
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="RedisCache.get",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        client = self._require_client()
        raw = client.get(k)
        if raw is None:
            return default
        ser = serializer if serializer is not MISSING and serializer is not None else self._serializer
        if ser is not None:
            try:
                return ser.loads(raw)
            except Exception:
                return raw
        return raw

    def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | timedelta | None = None,
        serializer: Any = MISSING,
    ) -> None:
        """Set a value by key with optional TTL."""
        if serializer is not MISSING:
            warn_deprecated_kwarg(
                name="serializer",
                owner="RedisCache.set",
                replacement="configure serializer on the cache constructor",
            )
        k = self._ns + key
        client = self._require_client()
        ser = serializer if serializer is not MISSING and serializer is not None else self._serializer
        payload = ser.dumps(value) if ser is not None else value
        seconds = to_seconds(ttl)
        if seconds is not None:
            client.set(k, payload, ex=seconds)
        else:
            client.set(k, payload)

    def delete(self, key: str) -> bool:
        """Delete a key."""
        k = self._ns + key
        client = self._require_client()
        try:
            res = client.delete(k)
            return bool(res)
        except AttributeError:
            before = client.get(k) is not None
            client.set(k, None)
            return before

    def exists(self, key: str) -> bool:
        """Check key existence."""
        k = self._ns + key
        client = self._require_client()
        res = client.exists(k)
        if isinstance(res, bool):
            return res
        try:
            return bool(int(res))
        except Exception:
            return bool(res)

    def clear(self, *, all: bool = False, dangerously_clear_all: Any = MISSING) -> None:
        """Clear keys in the current namespace or flush the DB."""
        force = resolve_renamed_kwarg(
            old_name="dangerously_clear_all",
            new_name="all",
            old_value=dangerously_clear_all,
            new_value=all,
            owner="RedisCache.clear",
            new_default=False,
        )
        force = bool(force) if force is not None else False
        client = self._require_client()
        if force:
            try:
                client.flushdb()
            except Exception:
                pass
            return
        if not self._ns:
            raise RuntimeError("clear() requires a namespace or pass all=True")
        pattern = f"{self._ns}*"
        try:
            keys = list(client.scan_iter(match=pattern))
        except Exception:
            keys = []
        norm_keys = [k.decode("utf-8") if isinstance(k, bytes | bytearray) else k for k in keys]
        if norm_keys:
            try:
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

    # ---- Enrichment ----
    def get_or_set(  # pylint: disable=unused-argument
        self,
        key: str,
        factory: Any,
        *,
        ttl: int | timedelta | None = None,
        jitter: int | None = None,  # noqa: ARG002
    ) -> Any:
        """Get or compute-and-set a value."""
        val = self.get(key, default=_MISSING)
        if val is not _MISSING:
            return val
        computed = factory() if callable(factory) else factory
        self.set(key, computed, ttl=ttl)
        return computed

    # ---- TTL management ----
    def expire(self, key: str, *, ttl: int | timedelta) -> bool:
        """Set a relative expiration."""
        k = self._ns + key
        client = self._require_client()
        seconds = to_seconds(ttl)
        if seconds is None:
            return False
        return bool(client.expire(k, seconds))

    def expire_at(self, key: str, when: datetime) -> bool:
        """Set an absolute expiration."""
        k = self._ns + key
        client = self._require_client()
        ts = int(when.timestamp())
        return bool(client.expireat(k, ts))

    def touch(self, key: str, *, ttl: int | timedelta | None = None) -> bool:
        """Refresh presence or set a new TTL."""
        if ttl is None:
            client = self._require_client()
            try:
                return bool(client.touch(self._ns + key))
            except AttributeError:
                return self.exists(key)
        return self.expire(key, ttl=ttl)

    def ttl(self, key: str) -> int | None:
        """Get remaining TTL in seconds."""
        k = self._ns + key
        client = self._require_client()
        res = client.ttl(k)
        try:
            val = int(res)
        except Exception:
            return None
        return val if val >= 0 else None

    def persist(self, key: str) -> bool:
        """Remove expiration from a key."""
        k = self._ns + key
        client = self._require_client()
        try:
            return bool(client.persist(k))
        except AttributeError:
            ttl = client.ttl(k)
            if ttl is None or (isinstance(ttl, int) and ttl < 0):
                return False
            try:
                client.pexpire(k, 0)
            except Exception:
                pass
            return True

    # ---- Counters ----
    def incr(
        self,
        key: str,
        *,
        delta: int = 1,
        ttl_if_new: int | timedelta | None = None,
        ttl_on_create: Any = MISSING,
    ) -> int:
        """Increment an integer counter by ``delta``."""
        effective_ttl = resolve_renamed_kwarg(
            old_name="ttl_on_create",
            new_name="ttl_if_new",
            old_value=ttl_on_create,
            new_value=ttl_if_new,
            owner="RedisCache.incr",
        )
        k = self._ns + key
        client = self._require_client()
        if effective_ttl is None:
            return int(client.incrby(k, int(delta)))

        pexpire_seconds = to_seconds(effective_ttl)
        ms = 0 if pexpire_seconds is None else int(pexpire_seconds * 1000)
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
            existed = bool(client.exists(k))
            val = int(client.incrby(k, int(delta)))
            if not existed and ms > 0:
                try:
                    client.pexpire(k, ms)
                except Exception:
                    client.expire(k, max(ms // 1000, 1))
            return val

    def decr(self, key: str, *, delta: int = 1) -> int:
        """Decrement an integer counter."""
        return self.incr(key, delta=-int(delta))

    # ---- Tags ----
    def invalidate_tags(self, tags: list[str], publish: bool | None = None) -> int:
        """Invalidate keys by tags. Returns number of keys deleted."""
        client = self._require_client()
        deleted_keys: set[str] = set()
        for tag in tags:
            tkey = f"{self._ns}tag:{tag}"
            try:
                members = client.smembers(tkey)
            except Exception:
                members = set()
            for mk in list(members):
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

        should_publish = publish if publish is not None else self._auto_publish_invalidations
        if should_publish and self._pubsub_channel:
            self.publish_invalidation(tags)

        return len(deleted_keys)

    def add_tags(self, key: str, tags: list[str], *, ttl: int | timedelta | None = None) -> None:
        """Associate ``tags`` with a key."""
        client = self._require_client()
        k = self._ns + key
        ttl_seconds = to_seconds(ttl) if ttl is not None else None

        for tag in tags:
            tkey = f"{self._ns}tag:{tag}"
            try:
                client.sadd(tkey, k)
                if ttl_seconds is not None and ttl_seconds > 0:
                    client.expire(tkey, int(ttl_seconds))
            except Exception:
                pass

    # ---- Health / lifecycle ----
    def health(self) -> HealthStatus:
        """Return cache health status."""
        try:
            client = self._require_client()
            ok = bool(client.ping())
        except Exception:
            ok = False
        return {"healthy": ok, "latency_ms": 0.0, "backend": "redis"}

    def healthy(self) -> bool:
        """Return ``True`` if the cache is healthy."""
        return bool(self.health().get("healthy", False))

    # Deprecated aliases
    def ping(self) -> HealthStatus:
        """Deprecated alias for :meth:`health`."""
        warn_deprecated_method(name="ping", owner="RedisCache", replacement="health")
        return self.health()

    def ping_ok(self) -> bool:
        """Deprecated alias for :meth:`healthy`."""
        warn_deprecated_method(name="ping_ok", owner="RedisCache", replacement="healthy")
        return self.healthy()

    def close(self) -> None:
        """Close the underlying client if applicable."""
        try:
            close_fn = getattr(self._client, "close", None)
            if close_fn is not None:
                close_fn()
        except Exception:
            pass

    def get_stats(self) -> dict[str, Any] | None:
        """Return ``None``; middleware may override to provide stats."""
        return None

    # ---- Context manager ----
    def __enter__(self) -> RedisCache:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    # ---- Internal helpers ----
    def _require_client(self) -> Any:
        return self._client

    @staticmethod
    def _create_single_client(config: RedisSingleConfig) -> Any:
        try:
            from redis import Redis
        except Exception as e:
            raise RuntimeError("redis is not installed; install with: `pip install redis`") from e

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

        for k, v in config.extra.items():
            kwargs.setdefault(k, v)

        return Redis(**kwargs)

    @staticmethod
    def _create_cluster_client(config: RedisClusterConfig) -> Any:
        try:
            from redis import RedisCluster
            from redis.cluster import ClusterNode
        except Exception as e:
            raise RuntimeError("redis cluster client not available; install redis>=4 with cluster support") from e

        nodes = [{"host": node.host, "port": node.port} for node in config.nodes]
        cluster_nodes = [ClusterNode(n["host"], n["port"]) for n in nodes]
        kwargs: dict[str, Any] = {
            "username": config.username,
            "password": config.password,
            "ssl": config.ssl,
        }
        if getattr(config, "decode_responses", False):
            kwargs["decode_responses"] = True
        if getattr(config, "socket_timeout", None) is not None:
            kwargs["socket_timeout"] = float(config.socket_timeout)  # type: ignore[arg-type]
        if getattr(config, "socket_connect_timeout", None) is not None:
            kwargs["socket_connect_timeout"] = float(config.socket_connect_timeout)  # type: ignore[arg-type]
        if getattr(config, "retry_on_timeout", False):
            kwargs["retry_on_timeout"] = True

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
        try:
            from redis.sentinel import Sentinel
        except Exception as e:
            raise RuntimeError("redis.sentinel is not available; install redis>=4") from e

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

    # ---- Pub/Sub ----
    def publish_invalidation(self, tags: list[str]) -> None:
        """Publish a tag invalidation event."""
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
        channel: str | None = None,
    ) -> None:
        """Subscribe to tag invalidation events (blocking)."""
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
