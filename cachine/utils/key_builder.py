from __future__ import annotations

from typing import Any


def default_key_builder(func_name: str, *args: Any, **kwargs: Any) -> str:
    """Very simple default key builder placeholder."""
    parts = [func_name]
    if args:
        parts.append("|".join(map(str, args)))
    if kwargs:
        parts.append("|".join(f"{k}={v}" for k, v in sorted(kwargs.items())))
    return ":".join(parts)
