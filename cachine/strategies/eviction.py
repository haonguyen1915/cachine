from __future__ import annotations

from collections import OrderedDict, defaultdict
from typing import Optional


class LRUEviction:
    """Least-Recently-Used eviction policy.

    Tracks key access order. ``evict_one()`` returns the least recently used key.
    """

    def __init__(self) -> None:
        self._order: OrderedDict[str, None] = OrderedDict()

    def note_access(self, key: str) -> None:
        """Record access for a key.

        Args:
            key (str): Fully qualified internal key.
        """
        # Move key to the end (most recently used)
        if key in self._order:
            self._order.move_to_end(key)
        else:
            self._order[key] = None

    def note_remove(self, key: str) -> None:
        """Remove a key from internal tracking.

        Args:
            key (str): Fully qualified internal key.
        """
        self._order.pop(key, None)

    def evict_one(self) -> Optional[str]:
        """Choose one key to evict.

        Returns:
            str | None: The least recently used key, or None if empty.
        """
        try:
            k, _ = self._order.popitem(last=False)
            return k
        except KeyError:
            return None


class LFUEviction:
    """Least-Frequently-Used eviction policy with LRU tie-break.

    Keeps frequency counters and an OrderedDict per frequency bucket. Evicts
    from the lowest frequency; among ties, evicts the oldest.
    """

    def __init__(self) -> None:
        self._freq: dict[str, int] = {}
        self._buckets: dict[int, OrderedDict[str, None]] = defaultdict(OrderedDict)
        self._min_freq: Optional[int] = None

    def note_access(self, key: str) -> None:
        """Record access for a key and update its frequency bucket.

        Args:
            key (str): Fully qualified internal key.
        """
        if key not in self._freq:
            # New key starts at frequency 1
            self._freq[key] = 1
            self._buckets[1][key] = None
            if self._min_freq is None or self._min_freq > 1:
                self._min_freq = 1
            return

        # Increase frequency
        f = self._freq[key]
        self._buckets[f].pop(key, None)
        if not self._buckets[f]:
            del self._buckets[f]
            if self._min_freq == f:
                self._min_freq = f + 1
        nf = f + 1
        self._freq[key] = nf
        self._buckets[nf][key] = None

    def note_remove(self, key: str) -> None:
        """Remove a key from internal structures.

        Args:
            key (str): Fully qualified internal key.
        """
        f = self._freq.pop(key, None)
        if f is not None:
            b = self._buckets.get(f)
            if b is not None:
                b.pop(key, None)
                if not b:
                    self._buckets.pop(f, None)
                    if self._min_freq == f:
                        # Recompute min_freq
                        self._min_freq = min(self._buckets.keys(), default=None)

    def evict_one(self) -> Optional[str]:
        """Choose one key to evict from the lowest frequency bucket.

        Returns:
            str | None: The evicted key, or None if there are no keys.
        """
        if self._min_freq is None:
            return None
        bucket = self._buckets.get(self._min_freq)
        if not bucket:
            # Recompute min_freq if bucket disappeared
            self._min_freq = min(self._buckets.keys(), default=None)
            if self._min_freq is None:
                return None
            bucket = self._buckets[self._min_freq]
        try:
            k, _ = bucket.popitem(last=False)
        except KeyError:
            return None
        # Remove from freq map
        self._freq.pop(k, None)
        if not bucket:
            self._buckets.pop(self._min_freq, None)
            self._min_freq = min(self._buckets.keys(), default=None)
        return k
