import asyncio
import time
import uuid
from threading import Thread
from typing import Any

import pytest

from cachine.backends.redis.async_ import AsyncRedisCache
from cachine.backends.redis.pubsub import RedisInvalidationBus
from cachine.backends.redis.sync import RedisCache
from cachine.models.redis_config import RedisSingleConfig


def test_pubsub_invalidation_roundtrip(redis_cache: RedisCache) -> None:
    """Test the legacy RedisInvalidationBus class for backward compatibility."""
    cache = redis_cache
    client = cache._require_client()  # internal, but fine for tests

    channel = f"cachine:invalidate:test:{uuid.uuid4().hex}"
    ns = "ut-ns"
    bus = RedisInvalidationBus(client, channel=channel, namespace=ns)

    events: list[dict[str, Any]] = []

    def handler(event: dict[str, Any]) -> None:
        events.append(event)

    t = Thread(target=bus.run_forever, args=(handler,), daemon=True)
    t.start()

    # Give subscriber time to connect
    time.sleep(0.1)

    tags = ["users", "user:1"]
    bus.publish_invalidation(tags)

    # Wait for event to be received (up to 2s)
    deadline = time.time() + 2.0
    while time.time() < deadline and not events:
        time.sleep(0.05)

    assert events, "Did not receive pub/sub invalidation event"
    evt = events[0]
    assert evt.get("type") == "invalidate_tags"
    assert evt.get("namespace") == ns
    assert evt.get("tags") == tags


def test_cache_publish_invalidation(redis_single_config: RedisSingleConfig) -> None:
    """Test publishing invalidation events directly from cache."""
    channel = f"cachine:invalidate:test:{uuid.uuid4().hex}"

    # Create publisher cache
    publisher = RedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
    )

    # Create subscriber cache
    subscriber = RedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
    )

    events: list[dict[str, Any]] = []

    def handler(event: dict[str, Any]) -> None:
        events.append(event)

    # Start subscriber in background thread
    t = Thread(target=subscriber.subscribe_invalidations, args=(handler,), kwargs={"channel": channel}, daemon=True)
    t.start()

    # Give subscriber time to connect
    time.sleep(0.1)

    # Publish invalidation event
    tags = ["user:123", "product:456"]
    publisher.publish_invalidation(tags)

    # Wait for event to be received (up to 2s)
    deadline = time.time() + 2.0
    while time.time() < deadline and not events:
        time.sleep(0.05)

    assert events, "Did not receive invalidation event from cache"
    evt = events[0]
    assert evt.get("type") == "invalidate_tags"
    assert evt.get("namespace") == "test-ns"
    assert evt.get("tags") == tags


def test_cache_auto_publish_invalidation(redis_single_config: RedisSingleConfig) -> None:
    """Test auto-publishing invalidation events when invalidate_tags is called."""
    channel = f"cachine:invalidate:test:{uuid.uuid4().hex}"

    # Create publisher cache with auto-publish enabled
    publisher = RedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
        auto_publish_invalidations=True,
    )

    # Create subscriber cache
    subscriber = RedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
    )

    events: list[dict[str, Any]] = []

    def handler(event: dict[str, Any]) -> None:
        events.append(event)

    # Start subscriber in background thread
    t = Thread(target=subscriber.subscribe_invalidations, args=(handler,), daemon=True)
    t.start()

    # Give subscriber time to connect
    time.sleep(0.1)

    # Set up tagged data
    publisher.set("user:123:profile", "data1")
    publisher.add_tags("user:123:profile", ["user:123"])

    # Invalidate tags - should auto-publish event
    tags = ["user:123"]
    publisher.invalidate_tags(tags)

    # Wait for event to be received (up to 2s)
    deadline = time.time() + 2.0
    while time.time() < deadline and not events:
        time.sleep(0.05)

    assert events, "Did not receive auto-published invalidation event"
    evt = events[0]
    assert evt.get("type") == "invalidate_tags"
    assert evt.get("namespace") == "test-ns"
    assert evt.get("tags") == tags


def test_cache_manual_publish_override(redis_single_config: RedisSingleConfig) -> None:
    """Test manually overriding publish behavior on invalidate_tags."""
    channel = f"caching:invalidate:test:{uuid.uuid4().hex}"

    # Create cache with auto-publish disabled
    cache = RedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
        auto_publish_invalidations=False,
    )

    # Create subscriber cache
    subscriber = RedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
    )

    events: list[dict[str, Any]] = []

    def handler(event: dict[str, Any]) -> None:
        events.append(event)

    # Start subscriber in background thread
    t = Thread(target=subscriber.subscribe_invalidations, args=(handler,), daemon=True)
    t.start()

    # Give subscriber time to connect
    time.sleep(0.1)

    # Set up tagged data
    cache.set("product:456", "data")
    cache.add_tags("product:456", ["product:456"])

    # Invalidate without publishing (auto_publish=False, publish not specified)
    cache.invalidate_tags(["product:456"])
    time.sleep(0.1)
    assert not events, "Should not have published event"

    # Invalidate with explicit publish=True override
    cache.set("product:789", "data2")
    cache.add_tags("product:789", ["product:789"])
    cache.invalidate_tags(["product:789"], publish=True)

    # Wait for event to be received (up to 2s)
    deadline = time.time() + 2.0
    while time.time() < deadline and not events:
        time.sleep(0.05)

    assert events, "Should have received event with publish=True override"
    evt = events[0]
    assert evt.get("type") == "invalidate_tags"
    assert evt.get("tags") == ["product:789"]


# ==================== Async Tests ====================


@pytest.mark.asyncio
async def test_async_cache_publish_invalidation(redis_single_config: RedisSingleConfig) -> None:
    """Test publishing invalidation events directly from async cache."""
    channel = f"cachine:invalidate:test:{uuid.uuid4().hex}"

    # Create publisher cache
    publisher = AsyncRedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
    )

    # Create subscriber cache
    subscriber = AsyncRedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
    )

    events: list[dict[str, Any]] = []

    async def handler(event: dict[str, Any]) -> None:
        events.append(event)

    # Start subscriber in background task
    async def run_subscriber() -> None:
        await subscriber.subscribe_invalidations(handler, channel=channel)

    subscriber_task = asyncio.create_task(run_subscriber())

    # Give subscriber time to connect
    await asyncio.sleep(0.2)

    # Publish invalidation event
    tags = ["user:123", "product:456"]
    await publisher.publish_invalidation(tags)

    # Wait for event to be received (up to 2s)
    deadline = asyncio.get_event_loop().time() + 2.0
    while asyncio.get_event_loop().time() < deadline and not events:
        await asyncio.sleep(0.05)

    # Cancel subscriber task
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass

    # Cleanup
    await publisher.close()
    await subscriber.close()

    assert events, "Did not receive invalidation event from async cache"
    evt = events[0]
    assert evt.get("type") == "invalidate_tags"
    assert evt.get("namespace") == "test-ns"
    assert evt.get("tags") == tags


@pytest.mark.asyncio
async def test_async_cache_auto_publish_invalidation(redis_single_config: RedisSingleConfig) -> None:
    """Test auto-publishing invalidation events when invalidate_tags is called on async cache."""
    channel = f"cachine:invalidate:test:{uuid.uuid4().hex}"

    # Create publisher cache with auto-publish enabled
    publisher = AsyncRedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
        auto_publish_invalidations=True,
    )

    # Create subscriber cache
    subscriber = AsyncRedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
    )

    events: list[dict[str, Any]] = []

    async def handler(event: dict[str, Any]) -> None:
        events.append(event)

    # Start subscriber in background task
    async def run_subscriber() -> None:
        await subscriber.subscribe_invalidations(handler)

    subscriber_task = asyncio.create_task(run_subscriber())

    # Give subscriber time to connect
    await asyncio.sleep(0.2)

    # Set up tagged data
    await publisher.set("user:123:profile", "data1")
    await publisher.add_tags("user:123:profile", ["user:123"])

    # Invalidate tags - should auto-publish event
    tags = ["user:123"]
    await publisher.invalidate_tags(tags)

    # Wait for event to be received (up to 2s)
    deadline = asyncio.get_event_loop().time() + 2.0
    while asyncio.get_event_loop().time() < deadline and not events:
        await asyncio.sleep(0.05)

    # Cancel subscriber task
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass

    # Cleanup
    await publisher.close()
    await subscriber.close()

    assert events, "Did not receive auto-published invalidation event from async cache"
    evt = events[0]
    assert evt.get("type") == "invalidate_tags"
    assert evt.get("namespace") == "test-ns"
    assert evt.get("tags") == tags


@pytest.mark.asyncio
async def test_async_cache_manual_publish_override(redis_single_config: RedisSingleConfig) -> None:
    """Test manually overriding publish behavior on invalidate_tags for async cache."""
    channel = f"cachine:invalidate:test:{uuid.uuid4().hex}"

    # Create cache with auto-publish disabled
    cache = AsyncRedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
        auto_publish_invalidations=False,
    )

    # Create subscriber cache
    subscriber = AsyncRedisCache(
        redis_single_config,
        namespace="test-ns",
        pubsub_channel=channel,
    )

    events: list[dict[str, Any]] = []

    async def handler(event: dict[str, Any]) -> None:
        events.append(event)

    # Start subscriber in background task
    async def run_subscriber() -> None:
        await subscriber.subscribe_invalidations(handler)

    subscriber_task = asyncio.create_task(run_subscriber())

    # Give subscriber time to connect
    await asyncio.sleep(0.2)

    # Set up tagged data
    await cache.set("product:456", "data")
    await cache.add_tags("product:456", ["product:456"])

    # Invalidate without publishing (auto_publish=False, publish not specified)
    await cache.invalidate_tags(["product:456"])
    await asyncio.sleep(0.1)
    assert not events, "Should not have published event"

    # Invalidate with explicit publish=True override
    await cache.set("product:789", "data2")
    await cache.add_tags("product:789", ["product:789"])
    await cache.invalidate_tags(["product:789"], publish=True)

    # Wait for event to be received (up to 2s)
    deadline = asyncio.get_event_loop().time() + 2.0
    while asyncio.get_event_loop().time() < deadline and not events:
        await asyncio.sleep(0.05)

    # Cancel subscriber task
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass

    # Cleanup
    await cache.close()
    await subscriber.close()

    assert events, "Should have received event with publish=True override on async cache"
    evt = events[0]
    assert evt.get("type") == "invalidate_tags"
    assert evt.get("tags") == ["product:789"]
