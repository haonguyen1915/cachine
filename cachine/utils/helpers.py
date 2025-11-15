from __future__ import annotations

from datetime import timedelta
from typing import Optional


def to_seconds(ttl: Optional[int | timedelta]) -> Optional[int]:
    if ttl is None:
        return None
    return int(ttl.total_seconds()) if isinstance(ttl, timedelta) else int(ttl)

