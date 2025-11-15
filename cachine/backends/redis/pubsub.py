from __future__ import annotations

import json
from typing import Any, Callable, Optional


class RedisInvalidationBus:
    """Simple Pub/Sub bus for tag invalidation events using redis-py.

    Event schema:
      {"type": "invalidate_tags", "namespace": "ns", "tags": ["user:1"]}
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

    def run_forever(self, handler: Callable[[dict], None]) -> None:  # pragma: no cover - requires live Redis
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
    """Async variant using redis.asyncio."""

    def __init__(self, client: Any, *, channel: str = "cachine:invalidate", namespace: Optional[str] = None) -> None:
        self._client = client
        self._channel = channel
        self._ns = namespace

    async def publish_invalidation(self, tags: list[str]) -> None:
        payload = {"type": "invalidate_tags", "namespace": self._ns, "tags": list(tags)}
        try:
            data = json.dumps(payload)
            await self._client.publish(self._channel, data)
        except Exception:
            pass

    async def run_forever(self, handler: Callable[[dict], Any]) -> None:  # pragma: no cover - requires live Redis
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

