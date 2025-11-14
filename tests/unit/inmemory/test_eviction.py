from cachine import InMemoryCache
from cachine.strategies import LRUEviction, LFUEviction


def test_lru_eviction_basic():
    cache = InMemoryCache(max_size=2, eviction_policy=LRUEviction())
    cache.set("a", 1)
    cache.set("b", 2)
    # Access 'a' so 'b' becomes LRU
    assert cache.get("a") == 1
    cache.set("c", 3)  # should evict 'b'
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_lfu_eviction_basic():
    cache = InMemoryCache(max_size=2, eviction_policy=LFUEviction())
    cache.set("a", 1)
    cache.set("b", 2)
    # Increase frequency of 'a'
    assert cache.get("a") == 1
    assert cache.get("a") == 1
    cache.set("c", 3)  # 'b' has lower freq → evicted
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_lfu_tie_break_on_recency():
    cache = InMemoryCache(max_size=2, eviction_policy=LFUEviction())
    cache.set("x", 1)  # freq 1
    cache.set("y", 2)  # freq 1
    # Tie on freq, LRU among ties: 'x' older than 'y'
    cache.set("z", 3)
    assert cache.get("x") is None
    assert cache.get("y") == 2
    assert cache.get("z") == 3

