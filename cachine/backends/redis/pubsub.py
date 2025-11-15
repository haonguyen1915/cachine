from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


class RedisInvalidationBus:
    """Pub/Sub bus for tag invalidation events using redis-py.

    Messages are JSON objects in the form::

        {"type": "invalidate_tags", "namespace": "ns", "tags": ["user:1"]}

    Args:
        client (Any): Redis client implementing ``publish`` and ``pubsub``.
        channel (str): Pub/Sub channel name.
        namespace (str | None): Namespace identifier included in events.
    """

    def __init__(
        self,
        client: Any,
        *,
        channel: str = "cachine:invalidate",
        namespace: Optional[str] = None,
    ) -> None:
        self._client = client
        self._channel = channel
        self._ns = namespace

    def publish_invalidation(self, tags: list[str]) -> None:
        """Publish an invalidate-tags event.

        Args:
            tags (list[str]): Tags to include in the event.

        Returns:
            None
        """
        payload = {
            "type": "invalidate_tags",
            "namespace": self._ns,
            "tags": list(tags),
        }
        try:
            data = json.dumps(payload)
            self._client.publish(self._channel, data)
        except Exception:
            pass

    def run_forever(self, handler: Callable[[dict[str, Any]], None]) -> None:  # pragma: no cover - requires live Redis
        """Blocking loop to process events.

        Subscribes to the channel and invokes ``handler`` for each valid message.

        Args:
            handler (Callable[[dict[str, Any]], None]): Function called with each event.
        """
        try:
            pubsub = self._client.pubsub()
            pubsub.subscribe(self._channel)
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


class AsyncRedisInvalidationBus:
    """Async Pub/Sub bus using redis.asyncio.

    Args:
        client (Any): Async Redis client implementing ``publish``/``pubsub``.
        channel (str): Pub/Sub channel name.
        namespace (str | None): Namespace identifier included in events.
    """

    def __init__(self, client: Any, *, channel: str = "cachine:invalidate", namespace: Optional[str] = None) -> None:
        self._client = client
        self._channel = channel
        self._ns = namespace

    async def publish_invalidation(self, tags: list[str]) -> None:
        """Publish an invalidate-tags event.

        Args:
            tags (list[str]): Tags to include.

        Returns:
            None
        """
        payload = {"type": "invalidate_tags", "namespace": self._ns, "tags": list(tags)}
        try:
            data = json.dumps(payload)
            await self._client.publish(self._channel, data)
        except Exception:
            pass

    async def run_forever(self, handler: Callable[[dict[str, Any]], Any]) -> None:  # pragma: no cover - requires live Redis
        """Blocking async loop to process events.

        Args:
            handler (Callable[[dict[str, Any]], Any]): Function called with each event. May be async.
        """
        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(self._channel)
            async for msg in pubsub.listen():
                if not msg or msg.get("type") != "message":
                    continue
                try:
                    event = json.loads(msg.get("data"))
                except Exception:
                    continue
                res = handler(event)
                if hasattr(res, "__await__"):
                    await res
        except Exception:
            pass
