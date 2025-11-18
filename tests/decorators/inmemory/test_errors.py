import time

import pytest

from cachine import InMemoryCache
from cachine.decorators import cached


def test_exception_not_cached_and_propagates_inmemory() -> None:
    cache = InMemoryCache()
    state = {"fail": True, "calls": 0}

    @cached(cache, ttl=60)
    def compute(x: int) -> int:
        state["calls"] += 1
        if state["fail"]:
            raise ValueError("boom")
        return x * 2

    # First call raises and should not cache
    with pytest.raises(ValueError):
        compute(2)

    assert state["calls"] == 1

    # Next call succeeds and caches
    state["fail"] = False
    assert compute(2) == 4
    assert compute(2) == 4
    assert state["calls"] == 2


def test_stale_ttl_refresh_error_inmemory() -> None:
    cache = InMemoryCache()
    state = {"fail": False, "n": 0}

    @cached(cache, ttl=1, stale_ttl=3, singleflight=True)
    def expensive() -> int:
        state["n"] += 1
        if state["fail"]:
            raise RuntimeError("refresh failed")
        return state["n"]

    # Initial compute
    assert expensive() == 1
    # Let fresh TTL expire
    time.sleep(1.2)
    # Fail refresh; should still serve stale
    state["fail"] = True
    v = expensive()
    assert v == 1
    # Stop failing; trigger refresh and allow thread to run
    state["fail"] = False
    _ = expensive()  # returns stale again, triggers refresh
    time.sleep(0.2)
    # Now value updated (note: failed refresh incremented counter before raising)
    assert expensive() == 3
