"""Shared SQL schema and helpers for SQLite backends."""

from __future__ import annotations

import time

# DDL executed on connect; idempotent.
DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS cache_data (
        key TEXT PRIMARY KEY,
        value BLOB,
        expires_at REAL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_cache_data_expires ON cache_data(expires_at)",
    """
    CREATE TABLE IF NOT EXISTS cache_tags (
        tag TEXT NOT NULL,
        key TEXT NOT NULL,
        PRIMARY KEY (tag, key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_cache_tags_key ON cache_tags(key)",
)


def now_epoch() -> float:
    """Return the current UTC time as Unix epoch seconds."""
    return time.time()


def like_prefix_pattern(prefix: str) -> str:
    """Escape a namespace prefix for a ``LIKE ? ESCAPE '\\'`` clause.

    ``%`` and ``_`` are wildcards in SQL LIKE; ``\\`` is the escape character
    we declare via ``ESCAPE '\\'``. Escaping these lets a namespace containing
    them still match only its own keys.
    """
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped + "%"


__all__ = ["DDL_STATEMENTS", "now_epoch", "like_prefix_pattern"]
