import time
import uuid
from threading import Thread

import pytest

from cachine.backends.redis.pubsub import RedisInvalidationBus


def test_pubsub_invalidation_roundtrip(redis_sync_cache):
    cache = redis_sync_cache
    client = cache._require_client()  # internal, but fine for tests

    channel = f"cachine:invalidate:test:{uuid.uuid4().hex}"
    ns = "ut-ns"
    bus = RedisInvalidationBus(client, channel=channel, namespace=ns)

    events = []

    def handler(event: dict) -> None:
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

