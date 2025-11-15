from cachine import InMemoryCache, cached


def test_tags_full_invalidation_inmemory():
    cache = InMemoryCache()
    calls = {"n": 0}

    @cached(
        cache,
        ttl=60,
        stale_ttl=30,
        tags=lambda uid: ["users", f"user:{uid}"],
        tags_from_result=lambda u: [f"role:{u['role']}"] if u else [],
    )
    def get_user(uid: int):
        calls["n"] += 1
        # Assign role based on uid for test determinism
        return {"id": uid, "role": "admin" if uid == 1 else "member"}

    # Populate two entries
    assert get_user(1) == {"id": 1, "role": "admin"}
    assert get_user(2) == {"id": 2, "role": "member"}
    # Second calls hit cache
    assert get_user(1) == {"id": 1, "role": "admin"}
    assert get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 2

    # Invalidate by role tag (only user:1)
    removed = cache.invalidate_tags(["role:admin"])  # type: ignore[attr-defined]
    assert removed >= 1
    # user 1 should recompute; user 2 remains cached
    assert get_user(1) == {"id": 1, "role": "admin"}
    assert get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 3

    # Invalidate by multiple tags (users + user:2)
    removed = cache.invalidate_tags(["users", "user:2"])  # type: ignore[attr-defined]
    assert removed >= 1
    # Both should recompute now
    assert get_user(1) == {"id": 1, "role": "admin"}
    assert get_user(2) == {"id": 2, "role": "member"}
    assert calls["n"] == 5
