from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

_logger = logging.getLogger(__name__)


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


def template_key_builder(template: str) -> Callable[..., str]:
    """Create a template-based key builder.

    The returned builder supports Python's ``str.format`` syntax and can access:
    - positional arguments by index: ``{0}``, ``{1}``
    - keyword arguments by name: ``{uid}``, ``{slug}``
    - the key context via ``{ctx}``: ``{ctx.full_name}``, ``{ctx.version}``
    - attribute access on positional args: ``{0.attr}``

    Example:
        >>> kb = template_key_builder("{ctx.full_name}:{0}:{uid}:v={ctx.version}")
        >>> # used with @cached(key_builder=kb, version="2")

    Args:
        template (str): Format string template.

    Returns:
        callable: A key_builder function accepting ``(ctx, *args, **kwargs)``.
    """

    def kb(ctx: Any, *args: Any, **kwargs: Any) -> str:
        try:
            return template.format(*args, ctx=ctx, **kwargs)
        except Exception as e:  # pragma: no cover - logged and falls back
            _logger.warning(
                "template_key_builder failed for template %r with error %s; falling back to default key",
                template,
                e,
            )
            # Fallback to a stable default if template formatting fails
            return default_key_builder(getattr(ctx, "full_name", "fn"), *args, **kwargs)

    return kb
