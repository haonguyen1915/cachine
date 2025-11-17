from typing import Any


def test_inmemory_basic_set_get(inmemory_cache: Any) -> None:
    inmemory_cache.set("k", 1)
    assert inmemory_cache.get("k") == 1


def test_inmemory_delete_exists(inmemory_cache: Any) -> None:
    inmemory_cache.set("x", 42)
    assert inmemory_cache.exists("x") is True
    assert inmemory_cache.delete("x") is True
    assert inmemory_cache.exists("x") is False
