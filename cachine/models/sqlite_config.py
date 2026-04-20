"""SQLite configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SQLiteConfig:
    """Configuration for a SQLite-backed cache.

    Attributes:
        database: Filesystem path to the SQLite database. Use ``":memory:"``
            for a private in-process database, or ``"file::memory:?cache=shared"``
            for a shared in-memory database usable across connections in the
            same process.
        timeout: ``sqlite3.connect`` timeout in seconds (how long to wait when
            the database is locked by another writer). Maps to the
            ``timeout`` parameter of :func:`sqlite3.connect`.
        busy_timeout_ms: ``PRAGMA busy_timeout`` in milliseconds. Controls
            retry behavior inside SQLite's own locking layer.
        journal_mode: ``PRAGMA journal_mode`` value. Defaults to ``WAL`` so
            readers don't block writers (and vice versa). Set to ``None`` to
            skip the PRAGMA entirely (keep the database default).
        synchronous: ``PRAGMA synchronous`` value (``"OFF"``, ``"NORMAL"``,
            ``"FULL"``, ``"EXTRA"``). ``NORMAL`` pairs well with WAL for cache
            workloads.
        check_same_thread: Forwarded to :func:`sqlite3.connect`. The backend
            serializes access with its own lock, so this is ``False`` by
            default to allow the connection to be shared across threads.
        extra: Additional ``sqlite3.connect`` keyword arguments.

    Examples:
        >>> config = SQLiteConfig(database="/tmp/cache.db")
        >>> config.database
        '/tmp/cache.db'
    """

    database: str = ":memory:"
    timeout: float = 5.0
    busy_timeout_ms: int | None = 5000
    journal_mode: str | None = "WAL"
    synchronous: str | None = "NORMAL"
    check_same_thread: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary format.

        Returns:
            Dictionary representation of the configuration.
        """
        result: dict[str, Any] = {
            "database": self.database,
            "timeout": self.timeout,
            "check_same_thread": self.check_same_thread,
        }
        if self.busy_timeout_ms is not None:
            result["busy_timeout_ms"] = self.busy_timeout_ms
        if self.journal_mode is not None:
            result["journal_mode"] = self.journal_mode
        if self.synchronous is not None:
            result["synchronous"] = self.synchronous
        result.update(self.extra)
        return result


__all__ = ["SQLiteConfig"]
