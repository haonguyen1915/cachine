"""SQLite URL parsing utilities.

Supported URL forms::

    sqlite:///relative/path.db                   # relative to CWD
    sqlite:////absolute/path.db                  # absolute path
    sqlite:///:memory:                           # private in-memory DB
    sqlite:///file::memory:?cache=shared         # shared in-memory DB
    sqlite:///path/db?timeout=5&busy_timeout=3000

Query parameters:
    timeout (float)          -> sqlite3.connect timeout
    busy_timeout (int, ms)   -> PRAGMA busy_timeout
    journal_mode (str)       -> PRAGMA journal_mode (e.g. WAL, DELETE, OFF)
    synchronous (str)        -> PRAGMA synchronous
    check_same_thread (bool) -> forwarded to sqlite3.connect

Examples:
    >>> config = parse_sqlite_url("sqlite:///tmp/cache.db")
    >>> config.database
    'tmp/cache.db'
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from ..exceptions import CacheError
from ..models.sqlite_config import SQLiteConfig


class SQLiteURLParseError(CacheError):
    """Raised when a SQLite URL cannot be parsed."""


_BOOL_TRUE = {"true", "1", "yes", "on"}
_BOOL_FALSE = {"false", "0", "no", "off"}


def parse_sqlite_url(url: str) -> SQLiteConfig:
    """Parse a SQLite connection URL into a :class:`SQLiteConfig`."""
    if not url:
        raise SQLiteURLParseError("URL cannot be empty")

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme != "sqlite":
        raise SQLiteURLParseError(f"Unsupported scheme: {scheme}. Use 'sqlite'")

    # Reconstruct the database component. ``urlparse`` gives us netloc + path;
    # concatenating them preserves ``file::memory:?cache=shared`` forms. Strip
    # exactly one leading ``/`` so ``sqlite:///:memory:`` -> ``:memory:`` and
    # ``sqlite:////abs/path`` -> ``/abs/path`` (SQLAlchemy convention).
    raw = (parsed.netloc or "") + (parsed.path or "")
    if raw.startswith("/"):
        raw = raw[1:]
    if not raw:
        raise SQLiteURLParseError("Database path is required (use sqlite:///path or sqlite:///:memory:)")

    query_params = parse_qs(parsed.query) if parsed.query else {}
    params = _flatten_query(query_params)

    timeout = _pop_float(params, "timeout", 5.0)
    busy_timeout = _pop_int(params, "busy_timeout", 5000)
    journal_mode = _pop_str(params, "journal_mode", "WAL")
    synchronous = _pop_str(params, "synchronous", "NORMAL")
    check_same_thread = _pop_bool(params, "check_same_thread", False)

    return SQLiteConfig(
        database=raw,
        timeout=timeout,
        busy_timeout_ms=busy_timeout,
        journal_mode=journal_mode,
        synchronous=synchronous,
        check_same_thread=check_same_thread,
        extra=params,
    )


def _flatten_query(query_params: dict[str, list[str]]) -> dict[str, Any]:
    return {k: v[0] for k, v in query_params.items() if v}


def _pop_float(params: dict[str, Any], key: str, default: float) -> float:
    if key not in params:
        return default
    try:
        return float(params.pop(key))
    except (TypeError, ValueError) as e:
        raise SQLiteURLParseError(f"Invalid {key}: {params.get(key)!r}") from e


def _pop_int(params: dict[str, Any], key: str, default: int | None) -> int | None:
    if key not in params:
        return default
    try:
        return int(params.pop(key))
    except (TypeError, ValueError) as e:
        raise SQLiteURLParseError(f"Invalid {key}: {params.get(key)!r}") from e


def _pop_str(params: dict[str, Any], key: str, default: str | None) -> str | None:
    if key not in params:
        return default
    return str(params.pop(key))


def _pop_bool(params: dict[str, Any], key: str, default: bool) -> bool:
    if key not in params:
        return default
    val = str(params.pop(key)).lower()
    if val in _BOOL_TRUE:
        return True
    if val in _BOOL_FALSE:
        return False
    raise SQLiteURLParseError(f"Invalid boolean for {key}: {val!r}")


__all__ = ["parse_sqlite_url", "SQLiteURLParseError"]
