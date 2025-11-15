from __future__ import annotations

from typing import Any, Optional


class TagBasedInvalidation:
    """Wrapper that provides tag-based invalidation against a cache.

    In practice, prefer calling ``cache.invalidate_tags(tags)`` directly when available.
    This strategy is provided for compatibility with the documented interface.

    Args:
        cache (Any): Underlying cache instance.
    """

    def __init__(self, cache: Any) -> None:
        self._cache = cache

    async def set(self, key: str, value: Any, *, ttl: Optional[int] = None, tags: Optional[list[str]] = None) -> None:
        """Set a value and optionally attach tags.

        Args:
            key (str): Cache key.
            value (Any): Value to store.
            ttl (int | None): Optional TTL seconds.
            tags (list[str] | None): Tags to associate with the key.
        """
        # Set the value and attach tags if the backend supports it.
        if hasattr(self._cache, "set"):
            res = self._cache.set(key, value, ttl=ttl)
            if hasattr(res, "__await__"):
                await res
        if tags and hasattr(self._cache, "add_tags"):
            out = self._cache.add_tags(key, tags)
            if hasattr(out, "__await__"):
                await out

    async def invalidate_tag(self, tag: str) -> int:
        """Invalidate all keys associated with a single tag.

        Args:
            tag (str): Tag to invalidate.

        Returns:
            int: Number of keys removed.
        """
        if hasattr(self._cache, "invalidate_tags"):
            res = self._cache.invalidate_tags([tag])
            if hasattr(res, "__await__"):
                result: int = await res
                return result
            return int(res) if res is not None else 0
        return 0
