from typing import Any


class BaseMiddleware:
    """Base middleware that forwards attribute access to the wrapped cache.

    Args:
        cache (Any): Wrapped cache instance.
    """

    def __init__(self, cache: Any) -> None:
        self._cache = cache

    def __getattr__(self, item: str) -> Any:  # delegate to underlying cache
        """Delegate attribute access to the wrapped cache.

        Args:
            item (str): Attribute name.

        Returns:
            Any: Attribute from the underlying cache.
        """
        return getattr(self._cache, item)
