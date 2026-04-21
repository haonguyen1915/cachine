"""Internal helpers for deprecating parameters and methods.

These utilities keep deprecation paths consistent across the codebase. They
are not part of the public API and may change between releases.
"""

from __future__ import annotations

import warnings
from typing import Any

_SENTINEL: Any = object()


def resolve_renamed_kwarg(
    *,
    old_name: str,
    new_name: str,
    old_value: Any,
    new_value: Any,
    owner: str,
    since: str = "v0.2",
    new_default: Any = None,
) -> Any:
    """Resolve a kwarg that has been renamed.

    Accept both old and new names during a deprecation window. Emit a
    :class:`DeprecationWarning` when the old name is used. Raise
    :class:`TypeError` when both are passed with conflicting values.

    Args:
        old_name: Deprecated kwarg name (e.g., ``"ttl_on_create"``).
        new_name: Preferred kwarg name (e.g., ``"ttl_if_new"``).
        old_value: Value received for ``old_name``. ``None`` or
            :data:`MISSING` means "not passed".
        new_value: Value received for ``new_name``. A value equal to
            ``new_default`` is treated as "not explicitly passed" so the old
            kwarg can override it.
        owner: Qualified name of the owner (``"RedisCache.incr"``) for the
            warning message.
        since: Version where deprecation began.
        new_default: Default value of the new kwarg. When ``new_value ==
            new_default``, the resolver assumes the user did not explicitly
            supply it and the deprecated kwarg (if present) wins.
    """
    has_old = old_value is not _SENTINEL and old_value is not None
    has_new = new_value is not _SENTINEL and new_value is not None and new_value != new_default
    if has_old and has_new:
        raise TypeError(f"{owner}: pass either {new_name!r} (preferred) or {old_name!r} (deprecated), not both")
    if has_old:
        warnings.warn(
            f"{owner}: kwarg {old_name!r} is deprecated since {since}; use {new_name!r} instead",
            DeprecationWarning,
            stacklevel=3,
        )
        return old_value
    if has_new:
        return new_value
    return new_default


def warn_deprecated_kwarg(
    *,
    name: str,
    owner: str,
    replacement: str | None = None,
    since: str = "v0.2",
) -> None:
    """Emit a deprecation warning for a kwarg that is being removed."""
    hint = f"; use {replacement}" if replacement else ""
    warnings.warn(
        f"{owner}: kwarg {name!r} is deprecated since {since} and will be removed in v0.3{hint}",
        DeprecationWarning,
        stacklevel=3,
    )


def warn_deprecated_method(
    *,
    name: str,
    owner: str,
    replacement: str | None = None,
    since: str = "v0.2",
) -> None:
    """Emit a deprecation warning for a method that is being renamed or removed."""
    hint = f"; use {replacement}()" if replacement else ""
    warnings.warn(
        f"{owner}.{name}() is deprecated since {since} and will be removed in v0.3{hint}",
        DeprecationWarning,
        stacklevel=3,
    )


# Re-export sentinel for consumers that need to detect "kwarg not passed"
MISSING = _SENTINEL


__all__ = [
    "MISSING",
    "resolve_renamed_kwarg",
    "warn_deprecated_kwarg",
    "warn_deprecated_method",
]
