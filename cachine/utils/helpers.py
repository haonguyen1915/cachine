from __future__ import annotations

from datetime import timedelta
from typing import Optional


def to_seconds(ttl: Optional[int | timedelta]) -> Optional[int]:
    """Convert a TTL to seconds.

    Args:
        ttl (int | timedelta | None): Time-to-live value.

    Returns:
        int | None: Seconds as an integer, or None when ``ttl`` is None.
    """
    if ttl is None:
        return None
    return int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)
