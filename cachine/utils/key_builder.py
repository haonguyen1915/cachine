from __future__ import annotations

from typing import Any


def default_key_builder(func_name: str, *args: Any, **kwargs: Any) -> str:
    """Build a simple cache key from function name and arguments.

    Args:
        func_name (str): Fully qualified function name.
        *args (Any): Positional arguments.
        **kwargs (Any): Keyword arguments.

    Returns:
        str: Key of the form ``"func|arg1|arg2:kw1=v1|kw2=v2"``.
    """
    parts = [func_name]
    if args:
        parts.append("|".join(map(str, args)))
    if kwargs:
        parts.append("|".join(f"{k}={v}" for k, v in sorted(kwargs.items())))
    return ":".join(parts)
